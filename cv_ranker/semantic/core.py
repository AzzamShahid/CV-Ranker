"""Read-only, candidate-scoped evidence retrieval; no matching or hiring judgments."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

import numpy as np

from .cache import SQLiteVectorCache
from .embedding import EmbeddingError, normalize


@dataclass(frozen=True)
class EvidenceSegment:
    candidate_id: str
    segment_id: str
    text: str
    admissible: bool  # Caller must explicitly decide admissibility upstream.
    section: str = "other"
    parent_context: str = ""  # Display to verifier, not embedded by default.

    def __post_init__(self):
        if not self.candidate_id or not self.segment_id or not self.text.strip():
            raise ValueError("Source segment needs nonblank candidate, ID and text")


@dataclass(frozen=True)
class CapabilityQuery:
    requirement_id: str
    capability_id: str
    text: str

    def __post_init__(self):
        if not self.requirement_id or not self.capability_id or not self.text.strip():
            raise ValueError("Query needs requirement ID, capability ID and text")


@dataclass(frozen=True)
class RetrievalHit:
    source: EvidenceSegment
    similarity: float
    lexical_exact: bool
    capability_ids: tuple[str, ...]


class Encoder(Protocol):
    @property
    def fingerprint(self) -> str: ...
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


def literal_phrase_present(needle: str, haystack: str) -> bool:
    """Boundary-safe literal substring search, without skill aliases or substring leakage.

    This preserves exact phrases but doesn't decide the semantics of their claims.
    """
    phrase = re.escape(" ".join(needle.split()))
    if not phrase:
        return False
    # +/# are retained as token characters to avoid C matching C++ or C#.
    pattern = rf"(?<![\w+#]){phrase}(?![\w+#])"
    return bool(re.search(pattern, " ".join(haystack.split()), flags=re.IGNORECASE))


class ShadowRetriever:
    def __init__(self, encoder: Encoder, cache: SQLiteVectorCache, top_k: int = 5):
        if top_k < 1:
            raise ValueError("top_k must be positive")
        self.encoder, self.cache, self.top_k = encoder, cache, top_k
        self.repaired_cache_entries = 0

    def _encode_cached(self, texts: list[str], role: str) -> np.ndarray:
        fingerprint = self.encoder.fingerprint
        keys = [SQLiteVectorCache.key(fingerprint, role, text) for text in texts]
        vectors: list[np.ndarray | None] = []
        for key in keys:
            try:
                vectors.append(self.cache.get(key))
            except EmbeddingError:
                # The original source and model digest still identify this
                # key, so recompute the one derived vector and replace it.
                # Do not delete the entire cache or suppress a live API error.
                vectors.append(None)
                self.repaired_cache_entries += 1
        missing = [i for i, v in enumerate(vectors) if v is None]
        if missing:
            wanted = [texts[i] for i in missing]
            raw = (self.encoder.embed_queries(wanted) if role == "query" else self.encoder.embed_documents(wanted))
            generated = normalize(raw, len(wanted))
            for position, vector in zip(missing, generated):
                self.cache.put(keys[position], vector)
                vectors[position] = vector
        assert all(v is not None for v in vectors)
        dimensions = {int(v.shape[0]) for v in vectors if v is not None}
        if len(dimensions) != 1:
            raise EmbeddingError("Inconsistent embedding dimensions; clear or upgrade cache")
        return np.stack(vectors).astype(np.float32)

    def retrieve_by_query(
        self, candidate_id: str, sources: list[EvidenceSegment], queries: list[CapabilityQuery]
    ) -> dict[str, list[RetrievalHit]]:
        """Retrieve with query-local scores and lexical flags (no JD requirement leakage).

        One encoder batch is shared across all queries; the output is keyed by
        unique capability ID. Retrieval values must NOT be globally maximized
        before being attributed to an individual JD requirement.
        """
        if not candidate_id.strip():
            raise ValueError("candidate_id is required")
        if len({q.capability_id for q in queries}) != len(queries):
            raise ValueError("Duplicate capability IDs")
        if not queries:
            return {}
        approved = [s for s in sources if s.candidate_id == candidate_id and s.admissible]
        if len({s.segment_id for s in approved}) != len(approved):
            raise ValueError("Duplicate source IDs within candidate")
        if not approved:
            return {q.capability_id: [] for q in queries}
        documents = self._encode_cached([s.text for s in approved], "document")
        query_vectors = self._encode_cached([q.text for q in queries], "query")
        if documents.shape[1] != query_vectors.shape[1]:
            raise EmbeddingError("Query/document embedding dimension mismatch")
        similarities = query_vectors @ documents.T
        result: dict[str, list[RetrievalHit]] = {}
        for row, query in enumerate(queries):
            order = sorted(range(len(approved)), key=lambda col: (
                -float(similarities[row, col]), approved[col].segment_id
            ))
            dense = set(order[:self.top_k])
            literal = {col for col, src in enumerate(approved)
                       if literal_phrase_present(query.text, src.text)}
            result[query.capability_id] = sorted([
                RetrievalHit(approved[col], float(similarities[row, col]),
                             col in literal, (query.capability_id,))
                for col in dense | literal
            ], key=lambda hit: (-int(hit.lexical_exact), -hit.similarity, hit.source.segment_id))
        return result

    def retrieve(self, candidate_id: str, sources: list[EvidenceSegment], queries: list[CapabilityQuery]) -> list[RetrievalHit]:
        """Backward-compatible aggregated view for diagnostic-only consumers.

        For JD-specific scores use retrieve_by_query. Aggregated maximum cosine
        and any-query literal hit have no single-requirement interpretation.
        """
        by_query = self.retrieve_by_query(candidate_id, sources, queries)
        combined: dict[str, dict] = {}
        for hits in by_query.values():
            for hit in hits:
                value = combined.setdefault(hit.source.segment_id, {
                    "source": hit.source, "similarity": -float("inf"),
                    "lexical_exact": False, "capability_ids": set(),
                })
                value["similarity"] = max(value["similarity"], hit.similarity)
                value["lexical_exact"] |= hit.lexical_exact
                value["capability_ids"].update(hit.capability_ids)
        return sorted([
            RetrievalHit(v["source"], v["similarity"], v["lexical_exact"],
                         tuple(sorted(v["capability_ids"])))
            for v in combined.values()
        ], key=lambda hit: (-int(hit.lexical_exact), -hit.similarity, hit.source.segment_id))

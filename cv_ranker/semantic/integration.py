"""Bridge the real Phase 7F.2 frozen-JD + segmented-CV pipeline to 7G shadow search.

No semantic inference, score mutation, or implicit automatic evidence credit.
The eligibility filter is for RETRIEVAL ONLY, not evidence acceptance for scoring.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..documents import extract_text
from ..assessor import _literal_initialism
from ..schemas import RankingReport
from ..segments import ResumeSegment, segment_resume
from ..text_utils import (instruction_like_evidence, non_candidate_requirement_copy,
                          phrase_present, requirement_options)
from .adapters import from_resume_segments
from .cache import SQLiteVectorCache
from .core import CapabilityQuery, Encoder, ShadowRetriever
from .decomposition import JDSearchPlan
from .embedding import OllamaEmbeddingGemma


def retrieval_eligible_ids(segments: list[ResumeSegment]) -> set[str]:
    """Conservative, generic source filter. NOT a claim that evidence is positive.

    Retain negative and learning evidence for later contradictory-context review.
    The existing segmenter marks copied job requirements as non_candidate.
    """
    denied_sections = {"non_candidate", "metadata"}
    return {
        segment.segment_id
        for segment in segments
        if segment.section not in denied_sections
        and not instruction_like_evidence(segment.text)
        and not non_candidate_requirement_copy(segment.text)
        and segment.text.strip()
    }


def run_shadow_retrieval(
    report: RankingReport,
    *,
    cache_path: str | Path,
    encoder: Encoder | None = None,
    top_k: int = 5,
    model: str = "embeddinggemma-2:latest",
    dimensions: int | None = None,
    capability_plan: JDSearchPlan | None = None,
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 180.0,
    batch_size: int = 16,
) -> dict[str, Any]:
    """Run semantic evidence discovery using the *already frozen* requirements.

    The returned diagnostic is separate from `RankingReport`, preserving every
    score/rank/status and the existing JSON report contract. On an Ollama error
    fail visibly rather than secretly using some other embedding model.
    """
    if encoder is None:
        provisional = OllamaEmbeddingGemma(model=model, base_url=base_url,
                                           timeout=timeout, batch_size=batch_size,
                                           expected_dimensions=dimensions)
        digest = provisional.get_remote_digest()
        encoder = OllamaEmbeddingGemma(model=model, base_url=base_url,
                                       timeout=timeout, batch_size=batch_size,
                                       expected_dimensions=dimensions, model_digest=digest)

    req_ids = [r.requirement_id for r in report.requirements]
    if not req_ids or len(req_ids) != len(set(req_ids)):
        raise ValueError("Shadow search requires uniquely identified frozen JD requirements")

    if capability_plan is not None:
        parents = {r.requirement_id: r for r in report.requirements}
        if capability_plan.parent_count != len(parents):
            raise ValueError("Capability plan does not match frozen JD denominator")
        if any(c.parent_requirement_id not in parents for c in capability_plan.capabilities):
            raise ValueError("Capability plan references a foreign JD requirement")
        if {c.capability_id for c in capability_plan.capabilities if c.provenance == "source_preserved"} != set(parents):
            raise ValueError("Capability plan must preserve every original JD query")
        if any(c.provenance == "source_preserved" and
               (c.description != parents[c.parent_requirement_id].name or
                c.source_quote != parents[c.parent_requirement_id].jd_evidence)
               for c in capability_plan.capabilities):
            raise ValueError("Capability plan mutated frozen JD source text")
        cap_ids = [c.capability_id for c in capability_plan.capabilities]
        if len(cap_ids) != len(set(cap_ids)):
            raise ValueError("Duplicate capability search IDs")
        queries = [CapabilityQuery(c.parent_requirement_id, c.capability_id, c.description)
                   for c in capability_plan.capabilities]
    else:
        queries = [CapabilityQuery(r.requirement_id, r.requirement_id, r.name) for r in report.requirements]
    output: dict[str, Any] = {
        "schema_version": 2,
        "mode": "semantic_shadow_read_only",
        "scoring_unchanged": True,
        "decomposition_enabled": capability_plan is not None,
        "decomposition_complete": capability_plan.complete if capability_plan is not None else None,
        "capability_search_plan": capability_plan.model_dump() if capability_plan is not None else None,
        "model_fingerprint": encoder.fingerprint,
        "top_k": top_k,
        "requirements": [{"requirement_id": r.requirement_id, "name": r.name, "priority": r.priority}
                         for r in report.requirements],
        "candidates": [],
    }
    seen_candidates: set[str] = set()
    with SQLiteVectorCache(cache_path) as cache:
        searcher = ShadowRetriever(encoder, cache, top_k=top_k)
        for candidate in report.candidates:
            source_path = Path(candidate.candidate_source)
            candidate_id = hashlib.sha256(str(source_path.resolve()).encode("utf-8")).hexdigest()[:24]
            # Deduplicate to avoid ambiguity when inputs use the same path twice.
            if candidate_id in seen_candidates:
                raise ValueError(f"Repeated candidate source: {source_path.name}")
            seen_candidates.add(candidate_id)
            entry: dict[str, Any] = {
                "candidate_name": candidate.candidate_name,
                "candidate_id": candidate_id,
                "direct_primary_score": candidate.primary_score,
                "ranking_position": candidate.rank,
                "retrieval_status": "not_evaluated",
                "hits_by_requirement": {},
            }
            output["candidates"].append(entry)
            if candidate.primary_score is None:
                entry["retrieval_status"] = "skipped_failed_assessment"
                continue
            # Reuse *exactly* the base 7F.2 text extraction and segmentation.
            resume_text = extract_text(source_path)
            segments = segment_resume(resume_text)
            allowed = retrieval_eligible_ids(segments)
            sources = from_resume_segments(candidate_id, segments, allowed)
            source_by_id = {source.segment_id: source for source in sources}
            repaired_before = searcher.repaired_cache_entries
            hits_by_query = searcher.retrieve_by_query(candidate_id, sources, queries)
            entry["retrieval_status"] = "completed" if allowed else "no_eligible_segments"
            entry["cache_repaired_entries"] = searcher.repaired_cache_entries - repaired_before
            entry["segment_count"] = len(segments)
            entry["retrieval_eligible_count"] = len(allowed)
            for requirement in report.requirements:
                # Aggregate ONLY within the frozen parent requirement, never
                # across other requirements. Each query hit has its own cosine
                # and literal match provenance from the actual query text.
                scoped: dict[str, dict[str, Any]] = {}
                for query in queries:
                    if query.requirement_id != requirement.requirement_id:
                        continue
                    for hit in hits_by_query[query.capability_id]:
                        sid = hit.source.segment_id
                        row = scoped.setdefault(sid, {
                            "source": hit.source,
                            "similarity": -float("inf"),
                            "lexical_exact": False,
                            "matched_query_ids": set(),
                        })
                        row["similarity"] = max(row["similarity"], hit.similarity)
                        row["lexical_exact"] |= hit.lexical_exact
                        row["matched_query_ids"].add(query.capability_id)
                # Single-CV accuracy: never let top-k embedding retrieval erase
                # an *explicitly named* CV source. Exact JD terms and strictly
                # derived initials (Natural Language Processing -> NLP) are
                # included as read-only retrieval context, not as scored proof.
                # There is no fabricated cosine value for these additional hits.
                literal_terms = list(requirement_options(requirement.name))
                initialism = _literal_initialism(requirement)
                if initialism:
                    literal_terms.append(initialism)
                order = {"skills": 0, "experience": 1, "projects": 2,
                         "summary": 3, "inferred_skills": 4}
                literal_sources = sorted((segment for segment in segments
                    if segment.segment_id in allowed and any(
                        phrase_present(term, segment.text) for term in literal_terms)),
                    key=lambda item: (order.get(item.section, 5), item.segment_id))
                for segment in literal_sources[:3]:
                    sid = segment.segment_id
                    source = source_by_id.get(sid)
                    if source is None:
                        continue
                    if sid not in scoped:
                        scoped[sid] = {
                            "source": source, "similarity": None,
                            "lexical_exact": False, "matched_query_ids": {requirement.requirement_id},
                            "literal_source_inclusion": True,
                        }
                selected = sorted(scoped.values(), key=lambda hit: (
                    -int(hit["lexical_exact"]), -int(hit.get("literal_source_inclusion", False)),
                    -(hit["similarity"] if hit["similarity"] is not None else -1),
                    hit["source"].segment_id,
                ))
                entry["hits_by_requirement"][requirement.requirement_id] = [
                    {
                        "segment_id": hit["source"].segment_id,
                        "section": hit["source"].section,
                        "original_text": hit["source"].text,
                        "cosine_similarity": (round(hit["similarity"], 6)
                                              if hit["similarity"] is not None else None),
                        "lexical_exact": hit["lexical_exact"],
                        "literal_source_inclusion": hit.get("literal_source_inclusion", False),
                        "matched_query_ids": sorted(hit["matched_query_ids"]),
                        "candidate_id": hit["source"].candidate_id,
                    }
                    for hit in selected
                ]
    return output

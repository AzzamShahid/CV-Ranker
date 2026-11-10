"""Asymmetric EmbeddingGemma 2 search embeddings through Ollama /api/embed.

This module deliberately does not interpret similarity as skill competence.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import numpy as np


class EmbeddingError(RuntimeError):
    """A model, transport, or vector validation failure."""


def normalize(vectors: object, expected_count: int, expected_dimensions: int | None = None) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] != expected_count or arr.shape[1] == 0:
        raise EmbeddingError(f"Unexpected embedding shape {arr.shape}; expected {expected_count} nonempty rows")
    if expected_dimensions is not None and arr.shape[1] != expected_dimensions:
        raise EmbeddingError(f"Dimension mismatch: got {arr.shape[1]}, expected {expected_dimensions}")
    if not np.isfinite(arr).all():
        raise EmbeddingError("Embedding contains NaN or infinity")
    magnitudes = np.linalg.norm(arr, axis=1)
    if np.any(~np.isfinite(magnitudes)) or np.any(magnitudes <= 0):
        raise EmbeddingError("Embedding has zero or invalid length")
    return (arr / magnitudes[:, None]).astype(np.float32)


@dataclass(frozen=True)
class OllamaEmbeddingGemma:
    model: str = "embeddinggemma-2:latest"
    base_url: str = "http://127.0.0.1:11434"
    timeout: float = 120.0
    expected_dimensions: int | None = None
    model_digest: str | None = None
    batch_size: int = 16

    @property
    def fingerprint(self) -> str:
        # For reliable cache invalidation, require a model content digest.
        # Caller should obtain it from Ollama `ollama list` or /api/tags.
        if not self.model_digest:
            raise EmbeddingError("Model digest required for persistent cache; obtain /api/tags digest")
        return f"ollama|{self.model}|{self.model_digest}|embeddinggemma2-search-v1|{self.expected_dimensions or 'native'}"

    def get_remote_digest(self) -> str:
        data = self._request("/api/tags", None)
        for item in data.get("models", []):
            if item.get("name") == self.model or item.get("model") == self.model:
                digest = item.get("digest")
                if isinstance(digest, str) and digest:
                    return digest
        raise EmbeddingError(f"Model {self.model!r} not found in Ollama /api/tags. Run: ollama pull {self.model}")

    def _request(self, route: str, body: dict | None) -> dict:
        url = self.base_url.rstrip("/") + route
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(url, data=payload, headers={"Content-Type": "application/json"} if body is not None else {}, method="POST" if body is not None else "GET")
        for attempt in range(2):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    result = json.load(response)
                break
            except HTTPError as exc:
                if exc.code in {408, 429, 500, 502, 503} and attempt == 0:
                    time.sleep(2)
                    continue
                raise EmbeddingError(f"Ollama {route} returned HTTP {exc.code} for model {self.model!r}") from None
            except (URLError, OSError) as exc:
                raise EmbeddingError(f"Cannot reach Ollama at {self.base_url} ({type(exc).__name__}). "
                                     "Confirm Ollama is running and OLLAMA_BASE_URL is correct.") from None
            except (ValueError, UnicodeError) as exc:
                raise EmbeddingError(f"Ollama {route} returned invalid JSON ({type(exc).__name__})") from None
        if not isinstance(result, dict):
            raise EmbeddingError("Unexpected Ollama response type")
        return result

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            raise EmbeddingError("Cannot embed an empty batch")
        if self.batch_size < 1:
            raise EmbeddingError("Embedding batch_size must be positive")
        # A single 40+ segment request may exceed local memory, context, or
        # server request limits even though the same model works for one text.
        # Smaller independent batches preserve source order and identity.
        vectors = []
        for offset in range(0, len(texts), self.batch_size):
            chunk = texts[offset:offset + self.batch_size]
            body = {"model": self.model, "input": chunk, "truncate": False}
            if self.expected_dimensions is not None:
                body["dimensions"] = self.expected_dimensions
            result = self._request("/api/embed", body)
            vectors.append(normalize(result.get("embeddings"), len(chunk), self.expected_dimensions))
        return normalize(np.concatenate(vectors, axis=0), len(texts), self.expected_dimensions)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"task: search result | query: {text}" for text in texts])

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode([f"title: none | text: {text}" for text in texts])

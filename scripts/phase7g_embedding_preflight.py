"""Test a real EmbeddingGemma 2 /api/embed call on the local Ollama server.

Run: python -m scripts.phase7g_embedding_preflight
"""
from __future__ import annotations

import argparse
import sys
import numpy as np
from cv_ranker.config import Settings
from cv_ranker.semantic.embedding import OllamaEmbeddingGemma, EmbeddingError


def main() -> int:
    settings = Settings(llm_provider="ollama")
    parser = argparse.ArgumentParser(description="Verify installed Ollama EmbeddingGemma 2 runs and returns usable vectors")
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--url", default=settings.ollama_base_url)
    args = parser.parse_args()
    print(f"Checking Ollama model: {args.model}")
    try:
        unverified = OllamaEmbeddingGemma(model=args.model, base_url=args.url, expected_dimensions=args.dimensions,
                                         timeout=settings.embedding_timeout_seconds, batch_size=settings.embedding_batch_size)
        digest = unverified.get_remote_digest()
        client = OllamaEmbeddingGemma(model=args.model, base_url=args.url, expected_dimensions=args.dimensions,
                                     timeout=settings.embedding_timeout_seconds, batch_size=settings.embedding_batch_size,
                                     model_digest=digest)
        query = client.embed_queries(["API endpoint development"])
        document = client.embed_documents(["Implemented backend routes to handle HTTP requests."])
        if query.shape != document.shape:
            raise EmbeddingError(f"Query/document shapes differ: {query.shape} / {document.shape}")
        score = float(query[0] @ document[0])
        if not np.isfinite(score):
            raise EmbeddingError("Cosine score is not finite")
        print(f"PASS: model digest={digest[:16]}... dimensions={query.shape[1]} cosine={score:.5f}")
        print("Ollama generated embeddings successfully. Semantic shadow search can use this model.")
        return 0
    except (EmbeddingError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("NOTE: 'ollama list' confirms the model is stored, not that the Windows runtime supports it.", file=sys.stderr)
        print("If the error mentions MLX or unknown model architecture, update Ollama and check supported GGUF tags;", file=sys.stderr)
        print("do not change the CV Ranker's scoring or silently substitute another embedding model.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

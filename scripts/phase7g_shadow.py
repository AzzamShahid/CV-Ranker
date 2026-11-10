"""Phase 7G read-only semantic retrieval after the unchanged ranking run.

Run as: python -m scripts.phase7g_shadow --jd ... --resumes ... [--no-llm]
Note: this writes original candidate text in diagnostic output. Store securely.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cv_ranker import CVRanker, Settings
from cv_ranker.documents import collect_resume_paths
from cv_ranker.report import write_json
from cv_ranker.semantic.embedding import EmbeddingError


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7G read-only semantic retrieval; scores unchanged")
    parser.add_argument("--jd", required=True, type=Path)
    parser.add_argument("--resumes", required=True, nargs="+", help="Resume files or folders")
    parser.add_argument("--no-llm", action="store_true", help="Use original conservative fallback instead of Qwen")
    parser.add_argument("--decompose", action="store_true", help="Use configured LLM JD functional search hints; NEVER changes scoring")
    parser.add_argument("--model", default=None, help="Configured JD/CV assessment model (default from .env)")
    parser.add_argument("--embedding-model", default=None, help="Optional diagnostic override; default EMBEDDING_MODEL in .env")
    parser.add_argument("--dimensions", type=int, default=None, help="Optional experiment; default model-native")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--cache", type=Path, default=Path("outputs/phase7g_shadow/embeddings.db"))
    parser.add_argument("--ranking-output", type=Path, default=Path("outputs/phase7g_shadow/ranking.json"))
    parser.add_argument("--shadow-output", type=Path, default=Path("outputs/phase7g_shadow/retrieval.json"))
    args = parser.parse_args()
    if args.top_k < 1 or (args.dimensions is not None and args.dimensions < 1):
        parser.error("top-k and explicit dimensions must be positive")
    if args.cache.resolve() == args.shadow_output.resolve() or args.ranking_output.resolve() == args.shadow_output.resolve():
        parser.error("cache and outputs must be different file paths")
    if args.decompose and args.no_llm:
        parser.error("--decompose needs a configured LLM; cannot combine with --no-llm")
    resumes = collect_resume_paths(args.resumes)
    if not resumes:
        parser.error("No supported resume files found")
    print(f"JD input: {args.jd}", flush=True)
    print(f"CV input count: {len(resumes)}", flush=True)
    print("Step 1/3: frozen JD and baseline ranking...", flush=True)
    try:
        ranker = CVRanker(Settings(model_name=args.model) if args.model else Settings(), use_llm=not args.no_llm)
        report = ranker.run(args.jd, resumes)
        # Rankings are materialized first and never replaced by semantic retrieval.
        write_json(report, args.ranking_output)
        print(f"Step 1/3 complete: {len(report.requirements)} frozen criteria; "
              f"{len(report.candidates)} candidates", flush=True)
        print("Step 2/3: optional JD decomposition...", flush=True)
        plan = ranker.plan_jd_capabilities(report) if args.decompose else None
        print("Step 3/3: local semantic retrieval...", flush=True)
        diagnostics = ranker.run_semantic_shadow(
            report, cache_path=args.cache, top_k=args.top_k,
            model=args.embedding_model, dimensions=args.dimensions, capability_plan=plan,
        )
        args.shadow_output.parent.mkdir(parents=True, exist_ok=True)
        args.shadow_output.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    except (ValueError, RuntimeError, OSError, EmbeddingError) as exc:
        print(f"Phase 7G shadow retrieval failed (ranking never changed): {exc}", file=sys.stderr)
        return 2
    print(f"Existing frozen requirements: {len(report.requirements)}")
    print(f"Candidates: {len(report.candidates)}")
    if args.decompose:
        print(f"JD decomposition complete: {plan.complete}; total search queries: {len(plan.capabilities)}")
        for warning in plan.warnings:
            print(f"Decomposition notice: {warning}")
    print("The existing YAKE / Qwen / Python scores were not changed by semantic retrieval.")
    print(f"Baseline ranking: {args.ranking_output}")
    print(f"Semantic evidence diagnostics (sensitive): {args.shadow_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

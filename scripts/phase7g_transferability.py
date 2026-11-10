"""Use existing read-only Phase 7G outputs; no ranking or embedding rerun.

Requires a live configured LLM provider and original resume files at their saved paths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cv_ranker import CVRanker, Settings
from cv_ranker.schemas import RankingReport


def main() -> int:
    ap = argparse.ArgumentParser(description="Source-audited, provisional CV transferability; no scoring changes")
    ap.add_argument("--ranking", type=Path, default=Path("outputs/phase7g_shadow/ranking.json"))
    ap.add_argument("--retrieval", type=Path, default=Path("outputs/phase7g_shadow/retrieval.json"))
    ap.add_argument("--output", type=Path, default=Path("outputs/phase7g_shadow/transferability.json"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--batch-size", type=int, default=3,
                    help="Maximum frozen requirements per structured model call (default: 3; 1 disables batching)")
    args = ap.parse_args()
    if args.output.resolve() in {args.ranking.resolve(), args.retrieval.resolve()}:
        ap.error("Never overwrite the original ranking/retrieval outputs")
    try:
        report = RankingReport.model_validate_json(args.ranking.read_text(encoding="utf-8"))
        retrieval = json.loads(args.retrieval.read_text(encoding="utf-8"))
        print(f"Reading ranking: {args.ranking}; retrieval: {args.retrieval}", flush=True)
        print(f"Running provisional relationship assessment (adaptive batches up to {args.batch_size} requirements)...", flush=True)
        ranker = CVRanker(Settings(model_name=args.model) if args.model else Settings(), use_llm=True)
        if ranker.llm is None:
            raise ValueError("Configured LLM provider failed to initialize")
        result = ranker.assess_transferability_shadow(report, retrieval, batch_size=args.batch_size)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"Mode: {result.mode}")
        print(f"Adaptive batching diagnostics: {result.batching}")
        print(f"Ranking input JD: {report.job_description_source}")
        print(f"Frozen requirements: {result.frozen_required_count}")
        print(f"Candidates: {result.candidate_count}")
        print(f"Structurally complete with no execution warnings: {result.complete}")
        print(f"Potential relationship label inconsistencies: {result.relationship_consistency_flag_count}")
        counts = {name: sum(a.relationship == name for candidate in result.candidates
                            for a in candidate.assessments)
                  for name in ("direct", "transferable", "related_only", "uncertain", "not_evidenced")}
        print(f"Relationship proposals by type: {counts}")
        for candidate in result.candidates:
            possible = [a for a in candidate.assessments if a.relationship == "transferable"]
            overlap_reviews = sum(a.functional_review_candidate for a in candidate.assessments)
            print(f"  {candidate.candidate_name}: transferable={len(possible)}, "
                  f"functional_review={overlap_reviews}, "
                  f"review_flags={candidate.relationship_consistency_flag_count}")
        audit_failures = sum(a.citation_audit == "audit_failed" for candidate in result.candidates
                             for a in candidate.assessments)
        print(f"Per-capability citation audit failures: {audit_failures}")
        alternatives = sum(a.functional_review_candidate for candidate in result.candidates
                           for a in candidate.assessments)
        print(f"Named-tool functional-overlap cases requiring manual review: {alternatives}")
        if not counts["transferable"]:
            print("NOTE: No transferable proposals. This is a model outcome, not a successful transferability benchmark.")
        print("All relationship proposals REQUIRE independent semantic review; a source citation is not competence verification.")
        print("Direct ranking and existing scores unchanged.")
        print(f"Sensitive output: {args.output}")
        for c in result.candidates:
            for warning in c.warnings:
                print(f"NOTICE {c.candidate_name}: {warning}")
        return 0 if result.complete else 3
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Transferability shadow assessment failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only, retrospective quality review of Phase 7G provisional labels.

Can be run on existing JSON outputs without re-calling Qwen/Ollama. Checks
consistency of JSON diagnostics, NOT independent CV authorship or competence.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cv_ranker.semantic.relationship_consistency import relationship_consistency_flags


def audit_reports(transferability: dict, retrieval: dict) -> dict:
    if transferability.get("mode") != "qwen_transferability_shadow_not_scoring":
        raise ValueError("Not a Phase 7G transferability shadow report")
    if retrieval.get("schema_version") != 2:
        raise ValueError("Require corrected, candidate-scoped retrieval schema v2")
    if not transferability.get("scoring_unchanged") or not retrieval.get("scoring_unchanged"):
        raise ValueError("A score-changing execution must not be described as a shadow run")
    plans = {p["capability_id"]: p for p in retrieval["capability_search_plan"]["capabilities"]}
    req_names = {r["requirement_id"]: r["name"] for r in retrieval["requirements"]}
    retrieved_candidates = {c["candidate_id"]: c for c in retrieval["candidates"]}
    if len(retrieved_candidates) != len(retrieval["candidates"]):
        raise ValueError("Duplicated candidate identity")
    if len(retrieved_candidates) != len(transferability["candidates"]):
        raise ValueError("Candidate inventory mismatch")
    rows = []
    totals = Counter()
    for c in transferability["candidates"]:
        matched = retrieved_candidates.get(c["candidate_id"])
        if matched is None or matched["candidate_name"] != c["candidate_name"]:
            raise ValueError("Missing or foreign candidate in retrieval")
        if matched["direct_primary_score"] != c["original_primary_score"] or matched["ranking_position"] != c["original_rank"]:
            raise ValueError("Shadow report differs from original ranking")
        flags_by_candidate = Counter()
        proposals = []
        for a in c["assessments"]:
            rid, cid = a["requirement_id"], a["capability_id"]
            plan = plans.get(cid)
            if plan is None or plan["parent_requirement_id"] != rid or rid not in req_names:
                raise ValueError("Proposal has an unknown or foreign frozen requirement")
            source_by_id = {h["segment_id"]: (h["original_text"], h["section"])
                            for h in matched["hits_by_requirement"][rid]}
            citations = [(x["segment_id"], x["exact_quote"]) for x in a.get("citations", [])]
            if a["citation_audit"] == "source_validated":
                for sid, quote in citations:
                    if sid not in source_by_id or quote.strip() not in source_by_id[sid][0]:
                        raise ValueError("Quotation is not supported by the supplied retrieval JSON")
            flags = relationship_consistency_flags(
                requirement_name=req_names[rid], capability_description=plan["description"],
                relationship=a["relationship"], citations=citations,
                original_sources=source_by_id, retrieved_sources=source_by_id,
            ) if a["citation_audit"] in {"source_validated", "not_cited"} else []
            flags_by_candidate.update(flags)
            if flags:
                proposals.append({"requirement_id": rid, "capability_id": cid,
                                  "model_relationship": a["relationship"], "flags": flags})
        totals.update(flags_by_candidate)
        rows.append({"candidate_name": c["candidate_name"], "original_rank": c["original_rank"],
                     "structural_status": c["status"], "classification_flags": sum(flags_by_candidate.values()),
                     "flag_types": dict(flags_by_candidate), "flagged_proposals": proposals})
    return {"mode": "relationship_consistency_diagnostics_only", "ranking_unchanged": True,
            "independent_semantic_verification": False,
            "meaning": "Possible model label inconsistencies, not confirmed hiring errors or corrected scores",
            "flag_count": sum(totals.values()), "flag_types": dict(totals), "candidates": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transferability", type=Path,
                        default=Path("outputs/phase7g_shadow/transferability.json"))
    parser.add_argument("--retrieval", type=Path,
                        default=Path("outputs/phase7g_shadow/retrieval.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("outputs/phase7g_shadow/relationship_quality.json"))
    args = parser.parse_args()
    if args.output.resolve() in {args.transferability.resolve(), args.retrieval.resolve()}:
        parser.error("Output must not overwrite the source diagnostics")
    result = audit_reports(json.loads(args.transferability.read_text(encoding="utf8")),
                           json.loads(args.retrieval.read_text(encoding="utf8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(f"Relationship quality audit: {result['flag_count']} potential issues")
    for c in result["candidates"]:
        print(f"  {c['candidate_name']}: {c['classification_flags']} flags")
    print("This is a diagnostic, not human adjudication. Existing ranks and scores are unchanged.")
    print(f"Sensitive diagnostic: {args.output}")


if __name__ == "__main__":
    main()

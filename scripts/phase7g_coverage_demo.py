"""Standalone synthetic audit fixture: no Ollama and no real applicant data.

Usage: python -m scripts.phase7g_coverage_demo
Do not treat synthetic relationships as actual assessed candidate evidence.
"""
from __future__ import annotations
import json

from cv_ranker.schemas import CandidateResult, ValidatedRequirement
from cv_ranker.semantic.coverage_scoring import (
    AdjudicatedCapability, CapabilityPlan, score_verified_capability_coverage,
)


def main():
    candidate = CandidateResult(candidate_name="Synthetic Example", primary_score=50.0, evaluation_mode="llm_assessed")
    requirements = [
        ValidatedRequirement(requirement_id="R1", name="Build API endpoints", priority="required", jd_evidence="Build API endpoints"),
        ValidatedRequirement(requirement_id="R2", name="Validate incoming requests", priority="required", jd_evidence="Validate incoming requests"),
    ]
    plan = [
        CapabilityPlan(requirement_id="R1", capability_id="C1", description="HTTP endpoint implementation"),
        CapabilityPlan(requirement_id="R2", capability_id="C2", description="Input validation"),
        CapabilityPlan(requirement_id="R2", capability_id="SEARCH-1", description="Web API", origin="search_hint"),
    ]
    # Labels in this file simulate verified, cited evidence; no actual LLM calls.
    decisions = [
        AdjudicatedCapability(capability_id="C1", relationship="transferable", evidence_ids=["S1"],
                                verification="verified", constraint_status="satisfied"),
        AdjudicatedCapability(capability_id="C2", relationship="not_evidenced", verification="verified", constraint_status="satisfied"),
        AdjudicatedCapability(capability_id="SEARCH-1", relationship="related_only", verification="verified", constraint_status="satisfied"),
    ]
    result = score_verified_capability_coverage(
        candidate=candidate, requirements=requirements, plan=plan, decisions=decisions,
        admissible_source_ids={"S1"},
    )
    print(json.dumps(result.model_dump(), indent=2))
    print("Primary score unchanged:", candidate.primary_score)


if __name__ == "__main__":
    main()

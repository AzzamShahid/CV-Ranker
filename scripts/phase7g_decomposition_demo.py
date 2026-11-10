"""Offline Phase 7G decomposition contract demo — no model call and no CV evaluation.

Real model: python -m scripts.phase7g_shadow --jd ... --resumes ... --decompose
"""
from __future__ import annotations
import json
from cv_ranker.schemas import ValidatedRequirement, RequirementConstraint
from cv_ranker.semantic.decomposition import (
    ProposedCapability, RequirementProposal, DecompositionResponse, create_shadow_search_plan,
)

class MockQwen:
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        # Mock STRUCTURE only; this is not a live LLM output and is not validated
        # as an HR assessment. We intentionally never assign verified scoring.
        return DecompositionResponse(requirements=[RequirementProposal(
            requirement_id="R001", capabilities=[
                ProposedCapability(description="API endpoint development", source_quote="Develop APIs", origin="explicit"),
                ProposedCapability(description="Request validation", source_quote="validate requests", origin="explicit"),
                ProposedCapability(description="Web services", source_quote="Develop APIs", origin="search_hint"),
            ])])


def main():
    reqs = [
        ValidatedRequirement(requirement_id="R001", name="Develop APIs and validate requests",
                             jd_evidence="Develop APIs and validate requests", priority="required"),
        ValidatedRequirement(requirement_id="R002", name="TensorFlow or PyTorch",
                             jd_evidence="TensorFlow or PyTorch", priority="required",
                             constraint=RequirementConstraint(operator="any_of", options=["TensorFlow", "PyTorch"])),
    ]
    plan = create_shadow_search_plan(reqs, MockQwen())
    print(json.dumps(plan.model_dump(), indent=2))
    assert plan.complete and plan.parent_count == 2
    assert {c.parent_requirement_id for c in plan.capabilities} == {"R001", "R002"}
    assert all(c.requires_human_review for c in plan.capabilities if c.provenance == "model_proposed")
    print('PASS: Original requirements preserved, candidate search hints flagged, scoring untouched.')

if __name__ == '__main__':
    main()

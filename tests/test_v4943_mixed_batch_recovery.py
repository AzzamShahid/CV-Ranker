"""Mixed invalid-row recovery must not lose or falsely repair an omitted ID.

Source checks, corrective calls and the final independent review are simulated;
these tests never contact an assessment provider or send applicant data away.
"""

import json
from types import SimpleNamespace

import pytest

from cv_ranker.config import Settings
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse,
                               _repair_nonatomic_source_metadata)


@pytest.mark.parametrize("requirement_name,source,kind,section,should_strip", [
    ("LLM integrations", "Hosted LLM API integrations", "skill", "skills", True),
    ("Supplier negotiations", "Supplier and vendor negotiations", "skill", "skills", True),
    ("LLM integrations", "No hosted LLM API integrations", "skill", "skills", False),
    ("LLM integrations", "Learning hosted LLM API integrations", "skill", "skills", False),
    ("LLM integrations", "LLM, hosted API integrations", "skill", "skills", False),
    ("LLM integrations", "Built with hosted LLM API integrations", "skill", "projects", False),
    ("Supplier negotiations", "Supplier and vendor negotiations", "experience", "skills", False),
])
def test_optional_highlight_repair_only_for_positive_split_source_label(
    requirement_name, source, kind, section, should_strip,
):
    req = ValidatedRequirement(requirement_id="R001", name=requirement_name,
                               priority="required", jd_evidence=requirement_name,
                               constraint=RequirementConstraint(kind=kind))
    segment = ResumeSegment(segment_id="S001", section=section,
                            text=source, source_lines=(1,))
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status="matched", evidence_ids=["S001"],
        matched_term="fabricated highlighted phrase",
        reason="The cited original entry declares the requested capability.",
    )])
    repaired = _repair_nonatomic_source_metadata(
        response, [req], {"S001": segment}, semantic_grounded_ids=set())
    assert (repaired.assessments[0].matched_term is None) is should_strip


@pytest.mark.parametrize("independent_source_valid", [True, False])
def test_grouped_correction_does_not_erase_highlight_only_unverified_row(independent_source_valid):
    requirements = [
        ValidatedRequirement(requirement_id="R001", name="LLM integrations",
                             priority="required", jd_evidence="LLM integrations"),
        ValidatedRequirement(requirement_id="R002", name="Docker",
                             priority="required", jd_evidence="Docker"),
    ]
    segments = [
        ResumeSegment(segment_id="S001", section="experience",
                      text="Integrated a hosted LLM API into a document review service.", source_lines=(1,)),
        ResumeSegment(segment_id="S002", section="skills",
                      text="Docker containers.", source_lines=(2,)),
    ]

    class Model:
        disabled_reason = None

        def __init__(self):
            self.requests = []

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.requests.append(json.loads(user_prompt))
            if len(self.requests) == 1:
                return UnifiedResponse(assessments=[
                    UnifiedItem(requirement_id="R001", decision="found", relation="direct",
                                evidence_ids=["S001"], matched_term="LLM integrations",
                                reason="Integrated a hosted LLM API into a document review service."),
                    UnifiedItem(requirement_id="R002", decision="found", relation="direct",
                                evidence_ids=["S999"], matched_term="Docker",
                                reason="Docker is named in the skills."),
                ])
            if len(self.requests) == 2:
                # Only the second criterion was sent for grouped correction.
                return UnifiedResponse(assessments=[
                    UnifiedItem(requirement_id="R002", decision="found", relation="direct",
                                evidence_ids=["S002"], matched_term="Docker",
                                reason="Docker is explicitly listed in the skills."),
                ])
            return schema.model_validate({"R001": {
                "decision": "found", "relation": "direct",
                "evidence_ids": ["S001"] if independent_source_valid else ["S999"],
                "proof_excerpt": None,
                "reason": "The candidate integrated a hosted LLM API into a document review service.",
            }})

    llm = Model()
    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama", assessment_batch_size=3)
    engine.llm = llm
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R001": [SimpleNamespace(source=SimpleNamespace(segment_id="S001"))],
        "R002": [SimpleNamespace(source=SimpleNamespace(segment_id="S002"))],
    })

    rows, metrics = engine.assess(
        requirements, segments, "Integrated a hosted LLM API into a document review service. Docker containers.",
        candidate_id="synthetic")

    assert rows[1].unified_status == "Found"
    assert rows[1].assessment_state == "verified"
    if independent_source_valid:
        assert rows[0].unified_status == "Found"
        assert rows[0].assessment_state == "verified"
        assert metrics.unresolved_ids == []
    else:
        assert rows[0].unified_status == "Unverified"
        assert rows[0].assessment_state == "unverified"
        assert metrics.unresolved_ids == ["R001"]
    assert metrics.correction_calls == 1
    assert metrics.final_verification_calls == 1
    assert len(llm.requests) == 3
    assert {entry["id"] for entry in llm.requests[1]["requirements"]} == {"R002"}
    assert not any("Grouped correction failed" in notice for notice in metrics.warnings)

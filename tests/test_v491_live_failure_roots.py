"""Generic regressions extracted from real failures, without matching exceptions."""

import json
from pathlib import Path

import numpy as np
import pytest

from cv_ranker.assessor import _validate_rows
from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.evidence_bridge import performed_functional_bridge
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               RequirementAssessment, RequirementConstraint,
                               ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.text_utils import classify_requirement_tone
from cv_ranker.unified import UnifiedEvidenceEngine


FIXTURES = Path(__file__).resolve().parents[1] / "sample_data/applied_ai_documents/pdf"


def requirement(name, *, kind="skill", rid="R001", **constraint):
    return ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority="required",
        constraint=RequirementConstraint(kind=kind, origin="source_rules", **constraint))


@pytest.mark.parametrize("role,phrase", [
    ("Google Cloud", "Plans to learn LangGraph, Google Cloud and PyTorch next year"),
    ("Inventory planning", "Plans to learn quality control, inventory planning and payroll next year"),
    ("Emergency routing", "I am learning patient intake and emergency routing"),
    ("Logistics tracking", "Currently exploring accounting, logistics tracking, and training"),
])
def test_future_list_covers_all_coordinated_targets(role, phrase):
    assert classify_requirement_tone(phrase, role) == "uncertain"
    segment = ResumeSegment("S001", "projects", phrase)
    row = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status="matched", evidence_ids=["S001"],
        reason="The applicant lists the requested item in a future learning plan.")])
    checked, invalid, warnings, _ = _validate_rows(
        response=row, requirements=[requirement(role)], resume_text=phrase,
        segments=[segment])
    assert invalid == set(), warnings
    assert checked["R001"].status == "uncertain"


def test_learning_domain_noun_and_independent_work_are_not_tentative():
    for claim in (
        "Managed deep learning and inventory planning projects.",
        "Delivered machine learning and quality assurance evaluations.",
        "Plans to learn payroll but built logistics tracking reports.",
    ):
        required = ("inventory planning" if "inventory planning" in claim else
                    "quality assurance" if "quality assurance" in claim else
                    "logistics tracking")
        assert classify_requirement_tone(claim, required) == "positive"


def test_pdf_future_learning_statement_is_review_not_failed_citation():
    segments = segment_resume(extract_text(FIXTURES / "12_salman_copied_jd_negations.pdf"))
    source = next(s for s in segments if "Learning roadmap:" in s.text)
    req = requirement("Google Cloud", rid="R015")
    proposal = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R015", status="matched", evidence_ids=[source.segment_id],
        reason="The CV mentions this item only in a future learning list.")])
    checked, invalid, warnings, _ = _validate_rows(
        response=proposal, requirements=[req],
        resume_text="\n".join(s.text for s in segments), segments=segments)
    assert not invalid, warnings
    assert checked["R015"].status == "uncertain"


def test_relevant_deep_learning_experience_is_not_a_coursework_claim():
    name = ("Minimum 3 years of relevant professional experience developing or "
            "delivering AI, machine-learning, deep-learning, or LLM-powered software.")
    req = requirement(name, kind="experience", minimum_years=3,
                      operator="complex", requires_review=True)
    text = extract_text(FIXTURES / "08_taimoor_research_transfer.pdf")
    checked = check_experience(req, text)
    assert checked.outcome == "sufficient"
    assert checked.claims[0].lower_years > 3.5
    assert all(claim.tone == "positive" for claim in checked.claims)
    source = RequirementAssessment(requirement_id="R001", status="matched")
    fixed, warnings, changed = apply_experience_checks(
        requirements=[req], assessments=[source], resume_text=text)
    assert not changed and not warnings
    assert fixed[0].status == "matched"


def test_actual_learning_only_duration_still_cannot_claim_professional_tenure():
    req = requirement("3 years of professional warehouse operations experience",
                      kind="experience", minimum_years=3)
    check = check_experience(req, "Experience:\nCurrently learning warehouse operations for 4 years.")
    assert check.outcome in {"ambiguous", "not_evidenced"}
    assert check.outcome != "sufficient"


def test_functional_comparison_requires_distinct_completed_work():
    req = requirement("DispatchFramework")
    original = {
        "S001": ResumeSegment("S001", "projects",
                               "Our custom route chaining demonstrates transferable orchestration "
                               "design, not explicit DispatchFramework use."),
        "S002": ResumeSegment("S002", "experience",
                               "Built route chaining and orchestration in a delivery service."),
    }
    assert performed_functional_bridge(req, original) is not None
    original["S002"] = ResumeSegment("S002", "education",
                                     "Only planning to learn route chaining and orchestration.")
    assert performed_functional_bridge(req, original) is None


class FlatEncoder:
    fingerprint = "final-verifier-contract-test"

    def embed_documents(self, texts):
        return np.ones((len(texts), 3), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 3), dtype=np.float32)


class PersistentlyBadCitationLLM:
    disabled_reason = None

    def __init__(self, valid_last=True):
        self.settings = Settings(llm_provider="ollama")
        self.calls = 0
        self.valid_last = valid_last

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        data = json.loads(user_prompt)
        independent = "IndependentSemantic" in schema.__name__
        final_absent = independent and self.valid_last
        return schema.model_validate({item["id"]: {
            "decision": "not_found" if final_absent else "found",
            "evidence_ids": [] if final_absent else ["S001"],
            "reason": "No candidate statement supports this duty." if
                      final_absent else "The referenced degree is a positive operational skill.",
            **({"relation": "absent" if final_absent else "entailed",
                "proof_excerpt": None if final_absent else "Invented quote"}
               if independent else {}),
        } for item in data["requirements"]})


@pytest.mark.parametrize("final_valid", [True, False])
def test_single_bounded_final_verification_never_invents_credit(tmp_path, final_valid):
    req = requirement("Warehouse scheduling")
    text = "Bachelor of Arts in Studio Photography, awarded 2024."
    source = ResumeSegment("S001", "education", text)
    provider = PersistentlyBadCitationLLM(valid_last=final_valid)
    with UnifiedEvidenceEngine(provider.settings, provider, encoder=FlatEncoder(),
                               cache_path=tmp_path / "final.db") as engine:
        rows, metrics = engine.assess([req], [source], text, candidate_id="generic-worker")
    assert provider.calls == 3
    assert metrics.final_verification_calls == 1
    assert metrics.correction_calls == 1
    assert rows[0].unified_status == ("Not Found" if final_valid else "Unverified")
    assert rows[0].assessment_state == ("verified" if final_valid else "unverified")
    assert metrics.unresolved_criteria == (0 if final_valid else 1)
    result = score_candidate(candidate_name="Generic worker", requirements=[req],
                             assessments=rows, evaluation_mode="llm_assessed", errors=[])
    assert (result.primary_score is None) is not final_valid

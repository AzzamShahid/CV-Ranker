"""Source-integrity and generic negation contracts across departments."""
import json

import numpy as np

from cv_ranker.assessor import _unanchored_semantic_tone, _validate_rows
from cv_ranker.documents import extract_text
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               ValidatedRequirement)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.semantic.integration import retrieval_eligible_ids
from cv_ranker.unified import UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse, _map_response


def _req(name):
    return ValidatedRequirement(requirement_id="R007", name=name,
                                jd_evidence=name, priority="required")


def test_wrapped_copied_job_post_is_never_promoted_to_project_work():
    text = ("PROJECTS\n"
            "- TARGET JOB DESCRIPTION - NOT A CLAIM OF EXPERIENCE: Required skills: stocktaking,\n"
            "  financial analysis, customer interviews, service scheduling,\n"
            "  business process management. These are copied job requirements.\n"
            "- Implemented a real customer ticket tracker for the team.\n")
    segments = segment_resume(text)
    copies = [s for s in segments if "financial analysis" in s.text
              or "customer interviews" in s.text or "TARGET JOB" in s.text]
    assert copies and all(seg.section == "non_candidate" for seg in copies)
    allowed = retrieval_eligible_ids(segments)
    assert not any(seg.segment_id in allowed for seg in copies)
    assert any(seg.section == "projects" and seg.segment_id in allowed
               and "ticket tracker" in seg.text for seg in segments)


def test_wrapped_copied_jd_in_bundled_pdf_is_also_quarantined():
    from pathlib import Path
    pdf = (Path(__file__).resolve().parents[1] / "sample_data" /
           "applied_ai_documents" / "pdf" / "12_salman_copied_jd_negations.pdf")
    segments = segment_resume(extract_text(pdf))
    copies = [s for s in segments
              if "TARGET JOB DESCRIPTION" in s.text or
              s.text.startswith("Learning, TensorFlow or PyTorch")]
    assert len(copies) == 2
    assert all(s.section == "non_candidate" for s in copies)
    assert all(s.segment_id not in retrieval_eligible_ids(segments) for s in copies)
    assert any(s.section == "projects" and "Learning roadmap" in s.text
               for s in segments)


def test_denials_in_normal_grammar_are_negative_not_invalid_positive_evidence():
    phrases = [
        "I have not developed operational reporting applications.",
        "We have no hands-on inspection experience.",
        "No field-audit planning or verification has been performed.",
        "The applicant has not built completed logistics forecasts.",
    ]
    assert all(_unanchored_semantic_tone(text) == "negated" for text in phrases)
    assert _unanchored_semantic_tone("Developed inspection reports with no production downtime.") == "positive"


def test_denial_citation_yields_valid_not_found_without_extra_model_retries():
    req = _req("Operational forecasting application development")
    source = ResumeSegment("S001", "education",
                           "I have not developed operational forecasting applications.")
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R007", status="matched", evidence_ids=["S001"],
        reason="The applicant mentioned the corresponding operational task.")])
    valid, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req], resume_text=source.text,
        segments=[source])
    assert not invalid, warnings
    assert valid["R007"].status == "not_matched"
    assert valid["R007"].evidence_ids == ["S001"]


def test_citation_preflight_explains_rejection_instead_of_blame_on_missing_id():
    req = _req("Workforce schedule planning")
    raw = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R007", decision="found", evidence_ids=["S999"],
        reason="An unrelated source ID was proposed by the model response.")])
    reasons = {}
    converted, _, invalid = _map_response(raw, [req], {"S001"},
                                          rejection_errors=reasons)
    assert not converted.assessments
    assert invalid == {"R007"}
    assert "not among the supplied eligible CV segments" in reasons["R007"]


def test_negative_only_applicant_can_finish_without_retry_or_fabricated_credit(tmp_path):
    """A false positive grounded in an explicit denial is a valid negative."""
    from cv_ranker.config import Settings

    class Encoder:
        fingerprint = "generic-denial-run"

        def embed_documents(self, texts):
            return np.ones((len(texts), 2), dtype=np.float32)

        def embed_queries(self, texts):
            return np.ones((len(texts), 2), dtype=np.float32)

    class MisreadingLLM:
        disabled_reason = None
        settings = Settings(llm_provider="ollama")

        def __init__(self):
            self.calls = 0

        def prompt_fits(self, system_prompt, user_prompt):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.calls += 1
            requirements = json.loads(user_prompt)["requirements"]
            return schema.model_validate({r["id"]: {
                "decision": "found", "evidence_ids": ["S001"],
                "reason": "The cited line appears to discuss the requested work."
            } for r in requirements})

    source = ResumeSegment("S001", "experience",
                           "I have not developed warehouse forecasting applications.")
    llm = MisreadingLLM()
    with UnifiedEvidenceEngine(llm.settings, llm, encoder=Encoder(),
                               cache_path=tmp_path / "deny.db") as engine:
        rows, metrics = engine.assess([_req("Warehouse forecasting application development")],
                                      [source], source.text, candidate_id="worker")
    assert llm.calls == 1 and metrics.correction_calls == 0
    assert metrics.unresolved_criteria == 0
    assert rows[0].unified_status == "Not Found"
    assert rows[0].assessment_state == "verified"

"""v49 follow-up: frozen JD coverage, evidence modality, typed technical gaps.

All synthetic names and provider responses, no external provider calls.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.failure_diagnostics import classify_failure
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.jd_coverage import explicit_clause_coverage, coverage_warning
from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
from cv_ranker.pipeline import CVRanker
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (JDRequirement, JDReviewDraft, JDValidationResponse,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.unified import _payload
from cv_ranker.segments import ResumeSegment


def requirement(text: str, rid="R001", priority="required"):
    old = ValidatedRequirement(requirement_id=rid, name=text, priority=priority,
                               jd_evidence=text)
    return old.model_copy(update={"constraint": classify_requirement(old, text)})


def test_source_coverage_exactly_identifies_unmapped_explicit_clause():
    jd = "Required Skills:\n- Python\n- SQL\n\nPreferred Skills:\n- Tableau\n"
    ledger = explicit_clause_coverage(jd, [requirement("Python")])
    assert [(x["source_quote"], x["disposition"]) for x in ledger] == [
        ("Python", "covered"), ("SQL", "unmapped_review_required"),
        ("Tableau", "unmapped_review_required")]
    assert ledger[1]["source_line_numbers"] == [3]
    assert coverage_warning(ledger).startswith("JD source-coverage review: 2")


def test_pipeline_draft_exposes_original_clause_coverage_without_inventing_rows(tmp_path):
    jd = "Required Skills:\n- Python\n- SQL\nPreferred Skills:\n- Tableau\n"
    file = tmp_path/"jd.txt"
    file.write_text(jd)
    ranker = CVRanker(settings=Settings(), use_llm=False)
    draft = ranker.prepare_jd_review(file)
    assert len(draft.requirements) == 3
    recorded = [x for x in draft.diagnostics
                if x.get("stage") == "explicit_jd_clause_coverage"]
    assert len(recorded) == 3
    assert all(x["disposition"] == "covered" for x in recorded)
    assert draft.diagnostics[-1]["stage"] == "final_denominator"


def test_review_recalculates_mapping_after_deleting_a_row():
    jd = "Required Skills:\n- Python\n- SQL\n"
    initial = [requirement("Python"), requirement("SQL", "R002")]
    draft = JDReviewDraft(jd_sha256="fixture", yake_candidates=[],
                          requirements=initial, jd_validation_mode="manual",
                          diagnostics=explicit_clause_coverage(jd, initial))
    approved = approve_jd_rows(draft=draft, rows=editable_jd_rows(draft)[:1],
                               jd_text=jd, max_requirements=20)
    assert approved.approved
    review = [x for x in approved.diagnostics
              if x.get("stage") == "explicit_jd_clause_coverage"]
    assert len(review) == 2
    assert review[1]["mapped_requirement_ids"] == []
    assert "JD source-coverage review:" in approved.warnings[0]


@pytest.mark.parametrize("text,modality,duration", [
    ("Knowledge of Excel", "knowledge_claim", "none"),
    ("Prepare supplier invoices", "performed_work", "none"),
    ("At least 5 years of experience in accounting", "dated_professional_tenure", "candidate_tenure"),
    ("Maintain records for at least 7 years", "performed_work", "non_tenure_timeframe_review"),
    ("Bachelor's degree in Textile Engineering", "completed_qualification", "none"),
])
def test_modality_is_independent_from_priority_and_elapsed_time(text, modality, duration):
    result = requirement(text).constraint
    assert result.evidence_modality == modality
    assert result.duration_subject == duration


def test_modality_goes_into_unified_wire_packet():
    req = requirement("Prepare supplier invoices")
    packet = json.loads(_payload(
        [req], {"S001": ResumeSegment("S001", "experience", "Prepared supplier invoices")},
        {"R001": ["S001"]}, limit=1))
    assert packet["requirements"][0]["evidence_modality"] == "performed_work"
    assert packet["requirements"][0]["constraint"]["duration_subject"] == "none"
    assert "assessment_as_of_date" not in packet


def test_invalid_schema_may_not_invent_candidate_negative():
    record = classify_failure(interruption="ModelStructuredResponseError: structured JSON did not validate",
                              rejected_model_ids=[], selected_ids=["S001"], cited_review_ids=[])
    assert record["failure_code"] == "MODEL_SCHEMA_INVALID"
    assert record["technical_not_candidate_failure"]
    assert "S001" in record["selected_source_ids"]
    assert "Not Found" not in record["next_useful_action"]


def test_rejected_citation_is_not_source_absence():
    record = classify_failure(interruption=None, rejected_model_ids=["S012"],
                              selected_ids=["S002", "S012"], cited_review_ids=["S002"])
    assert record["failure_code"] == "REJECTED_MODEL_CITATION"
    assert record["rejected_model_ids"] == ["S012"]
    assert record["review_source_ids_not_verified"] == ["S002"]


@pytest.mark.parametrize("reason,code", [
    ("OpenRouter HTTP 429", "PROVIDER_RATE_LIMIT"),
    ("OpenRouter HTTP 503", "PROVIDER_UNAVAILABLE"),
    ("ModelOutputTruncatedError: completion token limit reached", "OUTPUT_TRUNCATED"),
    ("LLMError: context budget exceeded", "CONTEXT_OVERFLOW"),
    ("LLMError: provider network/timeout failure", "PROVIDER_TRANSPORT"),
    ("LLMError: cloud request budget reached", "REQUEST_BUDGET_EXHAUSTED"),
])
def test_failure_codes_are_specific_and_source_text_free(reason, code):
    result = classify_failure(interruption=reason, rejected_model_ids=[],
                              selected_ids=[], cited_review_ids=[])
    assert result["failure_code"] == code
    assert set(result) == {"failure_code", "next_useful_action", "rejected_model_ids",
                           "selected_source_ids", "review_source_ids_not_verified",
                           "technical_not_candidate_failure"}


class _ScriptedJDModel:
    def __init__(self, initial, corrected):
        self.answers = [initial, corrected]
        self.prompts = []

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.prompts.append(user_prompt)
        return self.answers.pop(0)


def test_invalid_jd_source_correction_has_machine_readable_reason():
    m = _ScriptedJDModel(
        JDValidationResponse(requirements=[JDRequirement(name="FictitiousCloudSomething",priority="required",
                                                        evidence="invented unsourced phrase")]),
        JDValidationResponse(requirements=[]))
    rows, mode, warnings = validate_jd_requirements(
        jd_text="Required Skills:\n- Python\n", candidates=[], settings=Settings(),
        llm=m)
    assert len(m.prompts) == 2
    assert "evidence_absent_or_explicitly_excluded" in m.prompts[1]
    assert rows and rows[0].jd_evidence == "Python"


def test_empty_jd_response_gets_distinct_source_coverage_objective():
    m = _ScriptedJDModel(JDValidationResponse(requirements=[]),
                         JDValidationResponse(requirements=[]))
    validate_jd_requirements(jd_text="Required Skills:\n- Python", candidates=[],
                             settings=Settings(), llm=m)
    assert len(m.prompts) == 2
    from cv_ranker import prompt_fragments as pf
    assert pf.JD_FULL_REPLACEMENT_CORRECTION_OBJECTIVE in m.prompts[1]
    assert "complete corrected extraction" in m.prompts[1]


def test_typed_schema_rejects_inconsistent_tenure_modality():
    with pytest.raises(ValueError):
        RequirementConstraint(kind="skill", evidence_modality="dated_professional_tenure")


def test_cross_domain_actual_supervisor_pipeline_blocks_grossly_unrelated_actions():
    from evaluation.evaluate_supervisor import CROSS_DOMAIN_CASES, run_suite
    result = run_suite(CROSS_DOMAIN_CASES)
    assert result["count"] == 15
    assert result["correct"] == result["count"]
    assert all(row["model_calls"] <= 3 for row in result["cases"])
    assert all(row["score"] in {0.0, 100.0} for row in result["cases"])
    assert any(row["case"] == "finance_unrelated_logistics"
               and row["observed"] == "Not Found" for row in result["cases"])


def test_unrelated_work_with_authentic_citation_does_not_score_found():
    from cv_ranker.assessor import _validate_rows
    from cv_ranker.schemas import LLMCandidateAssessmentResponse, LLMAssessmentItem
    required = requirement("Reconcile monthly general ledger entries.")
    cv = "Operated warehouse forklift machinery for monthly shipments."
    evidence = ResumeSegment("S001", "experience", cv)
    proposal = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001",status="matched",evidence_ids=["S001"],
                          reason="Model says this unrelated action is direct.")])
    valid, invalid, notices, _ = _validate_rows(
        response=proposal, requirements=[required], resume_text=cv, segments=[evidence],
        semantic_grounded=True)
    assert "R001" in invalid
    assert not valid
    assert any("no substantive shared JD subject anchor" in notice for notice in notices)


def test_inflected_completed_multiaction_work_is_not_compound_demoted():
    from cv_ranker.compound_validation import apply_compound_checks
    from cv_ranker.schemas import RequirementAssessment, EvidenceCitation
    req = requirement("Investigate flaky CI tests and document root causes.")
    source = "Investigated flaky CI tests and documented root causes."
    citation = EvidenceCitation(segment_id="S001", section="experience", text=source)
    assessment = RequirementAssessment(requirement_id="R001",status="matched",
                                        unified_status="Found", evidence_ids=["S001"],
                                        evidence_segments=[citation],evidence=source)
    checked, reasons, changed = apply_compound_checks(
        requirements=[req], assessments=[assessment], resume_text=source)
    assert checked[0].status == "matched"
    assert checked[0].unified_status == "Found"
    assert checked[0].compound_check and checked[0].compound_check.outcome == "matched"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("location", [
    "https://example.invalid/capture",
    "http://example.invalid/downgrade",
    "https://openrouter.ai:8443/alternate-port",
    "/same-origin-redirect",
])
def test_authenticated_provider_redirect_never_forwards_key_or_cv(status, location, monkeypatch):
    """Exercise the real configured urllib opener with intercepted transport."""
    import email.message
    import io
    from urllib.error import HTTPError
    from urllib.request import BaseHandler, ProxyHandler, build_opener
    from urllib.response import addinfourl
    import cv_ranker.llm as llm

    calls = []

    class Intercept(BaseHandler):
        handler_order = 100

        def https_open(self, request):
            calls.append((request.full_url, request.get_header("Authorization"),
                          request.data or b""))
            msg = email.message.Message()
            msg["Location"] = location
            out = addinfourl(io.BytesIO(b""), msg, request.full_url, status)
            out.msg = "test redirect"
            return out

        def http_open(self, request):
            raise AssertionError("Unsafe HTTP downgrade attempted")

    monkeypatch.setattr(llm, "_SAFE_CLOUD_OPENER",
                        build_opener(ProxyHandler({}), llm._RejectProviderRedirects(), Intercept()))
    client = llm.OpenRouterStructuredLLM(Settings(llm_provider="openrouter",
                                                openrouter_api_key="fictional-only"))
    with pytest.raises(llm.OpenRouterHTTPError) as error:
        client._post_chat({"model": "fixture", "messages": [
            {"role": "user", "content": "Fictional CV for testing only"}]})
    assert error.value.status_code == status
    assert len(calls) == 1
    assert calls[0][0].startswith("https://openrouter.ai/")
    assert client.http_attempts == 1

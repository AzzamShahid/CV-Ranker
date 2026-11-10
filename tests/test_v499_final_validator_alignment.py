"""End-to-end deterministic regression of the reported post-LLM overrides.

The LLM controls semantic overlap. Python still verifies original credential
claims, literal options and duration; no similarity score awards Found.
"""

from pathlib import Path

import pytest

from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.documents import extract_text
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.qualification_validation import apply_qualification_checks
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement,
                               CandidateResult, RankingReport)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate


SOURCE_PDFS = Path(__file__).resolve().parents[1] / "sample_data/applied_ai_documents/pdf"
EXPERIENCE = ("Minimum 3 years of relevant professional experience developing or "
              "delivering AI, machine-learning, deep-learning, or LLM-powered software.")
DEGREE = "Completed Bachelor's degree in Computer Science."


def requirement(rid, name, kind="skill", **kwargs):
    return ValidatedRequirement(
        requirement_id=rid, priority="required", name=name, jd_evidence=name,
        constraint=RequirementConstraint(kind=kind, origin="source_rules", **kwargs))


def source_row(rid, sources, *, status="matched", unified="Found", reason="Evidence supports the model's decision."):
    return RequirementAssessment(
        requirement_id=rid, status=status, unified_status=unified,
        evidence_ids=[s.segment_id for s in sources],
        evidence_segments=[EvidenceCitation(
            segment_id=s.segment_id, section=s.section, text=s.text)
            for s in sources],
        evidence=" ".join(s.text for s in sources), reason=reason)


@pytest.mark.parametrize("degree", [
    "BS Software Engineering | City College of Technology (fictional), 2021",
    "BS Information Technology | North City Institute (fictional), 2021",
    "MSc Artificial Intelligence | University of Example (fictional), 2021",
])
def test_related_completed_degree_cannot_end_not_found_beside_positive_overlap_reason(degree):
    req = requirement("R002", DEGREE, "education", degree_level="bachelor",
                      field_of_study="Computer Science")
    cv = f"Education\n{degree}"
    source = segment_resume(cv)
    submitted = source_row("R002", source, status="matched", unified="Found",
                           reason=(f"{degree.split('|')[0].strip()} is a closely "
                                   "related completed academic field to Computer Science, "
                                   "but the major is not identical."))
    checked, notices, changed = apply_qualification_checks(
        requirements=[req], assessments=[submitted], resume_text=cv)
    assert changed and notices
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.status != "matched"
    assert final.unified_status == "Transferable"
    assert "no direct requirement point" in final.reason
    assert final.qualification_check.outcome in {"mismatch", "ambiguous"}


def test_unrelated_or_incomplete_degree_cannot_transfer_from_label_alone():
    req = requirement("R002", DEGREE, "education", degree_level="bachelor",
                      field_of_study="Computer Science")
    for degree, reason in (
        ("BA Music Performance | College, 2021", "The degree is unrelated to the subject."),
        ("Expected BS Software Engineering, 2027", "A related degree is only planned."),
    ):
        cv = f"Education\n{degree}"
        submitted = source_row("R002", segment_resume(cv), unified="Found", reason=reason)
        checked, _, _ = apply_qualification_checks(
            requirements=[req], assessments=[submitted], resume_text=cv)
        final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
        assert final.unified_status != "Transferable", (degree, final)
        assert final.status != "matched"


def test_exact_named_degree_still_earns_direct_point():
    req = requirement("R002", DEGREE, "education", degree_level="bachelor",
                      field_of_study="Computer Science")
    cv = "Education\nBS Computer Science | University of Example, 2021"
    row = source_row("R002", segment_resume(cv))
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.status == "matched" and final.unified_status == "Found"


def test_fictional_cloud_engineer_has_related_experience_but_not_proven_three_ai_years():
    req = requirement("R001", EXPERIENCE, "experience", minimum_years=3,
                      operator="complex", requires_review=True)
    cv = extract_text(SOURCE_PDFS / "09_amal_cloud_integrations.pdf")
    segments = segment_resume(cv)
    assert check_experience(req, cv, segments).outcome == "role_semantic"
    cited = [s for s in segments if s.segment_id in {"S005", "S023"}]
    assert any("4 years 9 months" in s.text for s in cited)
    row = source_row("R001", cited, reason=(
        "Four years of backend and cloud application development substantially "
        "overlaps with the JD, but the LLM-specific work is more recent."))
    checked, _, changed = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    assert changed and checked[0].status == "uncertain"
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status == "Transferable"
    assert "not established" in final.reason
    assert {"S005", "S023"}.issubset(final.evidence_ids)
    assert final.review_recommended


def test_fictional_negative_cv_remains_not_found_for_professional_ai_tenure():
    req = requirement("R001", EXPERIENCE, "experience", minimum_years=3,
                      operator="complex", requires_review=True)
    cv = extract_text(SOURCE_PDFS / "12_salman_copied_jd_negations.pdf")
    segments = segment_resume(cv)
    cited = [s for s in segments if s.segment_id in {"S009", "S010"}]
    row = source_row("R001", cited, status="not_matched", unified="Not Found",
                     reason="This IT operations work is unrelated to the JD's AI tenure.")
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status == "Not Found" and final.status != "matched"


def test_fictional_four_year_ai_software_experience_retains_found_status():
    req = requirement("R001", EXPERIENCE, "experience", minimum_years=3,
                      operator="complex", requires_review=True)
    cv = extract_text(SOURCE_PDFS / "03_sara_functional_transfer.pdf")
    original = segment_resume(cv)
    claim = next(s for s in original if "four years of professional" in s.text.casefold())
    row = source_row("R001", [claim], reason="Four years of professional LLM software development.")
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.status == "matched" and final.unified_status == "Found"


def test_ui_uses_final_reconciled_reason_instead_of_overwriting_it_with_validator_diagnostic():
    req = requirement("R002", DEGREE, "education", degree_level="bachelor",
                      field_of_study="Computer Science")
    cv = "Education\nBS Software Engineering | City College (fictional), 2021"
    source = segment_resume(cv)
    original = source_row("R002", source, reason=(
        "BS Software Engineering is a closely related degree to Computer Science, "
        "but not identical."))
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[original], resume_text=cv)
    row = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    report = RankingReport(
        job_description_source="fictional.jd", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[req], candidates=[CandidateResult(
            candidate_name="fictional.pdf", primary_score=0.0,
            evaluation_mode="llm_assessed", assessments=[row])])
    ledger = segment_ledger(source)
    display = reconcile_unified_candidate(report, 0, ledger)
    assert display["Criteria"][0]["Result"] == "Transferable"
    assert display["Criteria"][0]["Why"] == row.reason
    assert "no direct requirement point" in display["Criteria"][0]["Why"]


def test_future_learning_is_not_accepted_as_one_of_two_named_frameworks():
    name = "TensorFlow or PyTorch"
    req = requirement("R006", name, "skill", operator="any_of",
                      options=["TensorFlow", "PyTorch"])
    cv = "Projects\nLearning roadmap: Plans to learn TensorFlow or PyTorch next year."
    row = source_row("R006", segment_resume(cv), status="uncertain", unified="Not Found",
                     reason="The candidate describes only a future learning plan.")
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].compound_check.outcome in {"uncertain", "not_matched"}

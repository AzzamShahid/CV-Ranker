"""Source-grounded counterexamples spanning different disciplines.

These regressions test JD literal alternatives and original-source review
leads; none of the extra review passages may silently earn a ranking point.
"""

import pytest

from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.qualification_validation import apply_qualification_checks, check_qualification
from cv_ranker.requirement_typing import add_requirement_types
from cv_ranker.schemas import RequirementAssessment, ValidatedRequirement
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import segment_resume
from cv_ranker.unified import _retain_negative_review_checkpoints


def _requirement(jd):
    return add_requirement_types([
        ValidatedRequirement(requirement_id="R777", name=jd,
                             jd_evidence=jd, priority="required")
    ], jd)[0]


@pytest.mark.parametrize("field_a,field_b", [
    ("Textile Engineering", "Textile Technology"),
    ("Computer Science", "Software Engineering"),
    ("Civil Engineering", "Environmental Engineering"),
    ("Accounting", "Finance"),
])
def test_explicit_bachelor_or_fields_support_multiple_industries(field_a, field_b):
    jd = f"Completed Bachelor's degree in {field_a} or {field_b}."
    check = check_qualification(_requirement(jd),
                                f"Education\nBS {field_b}, Fictional University, 2021")
    assert check.outcome == "satisfied", (jd, check)


def test_typographic_apostrophe_does_not_lose_a_valid_degree_claim():
    jd = "Completed Bachelor’s degree in Computer Science or Software Engineering."
    resume = "Education\nBachelor’s degree in Software Engineering, Fictional University, 2020"
    check = check_qualification(_requirement(jd), resume)
    assert check.outcome == "satisfied", check


def test_typographic_apostrophe_does_not_invent_an_unlisted_major():
    jd = "Completed Bachelor’s degree in Computer Science or Software Engineering."
    resume = "Education\nBachelor’s degree in Marketing, Fictional University, 2020"
    assert check_qualification(_requirement(jd), resume).outcome != "satisfied"


@pytest.mark.parametrize("credential,field", [
    ("DAE", "Textile Technology"),
    ("HND", "Electrical Engineering"),
])
def test_exact_named_alternative_diploma_from_frozen_jd(credential, field):
    jd = ("Completed Bachelor's degree in Mechanical Engineering or Industrial "
          f"Engineering, or a three-year {credential} diploma in {field}.")
    cv = f"Education\nCompleted three-year {credential} diploma in {field}, Fictional Institute, 2020"
    check = check_qualification(_requirement(jd), cv)
    assert check.outcome == "satisfied", check


def test_named_diploma_without_exact_name_or_field_is_not_accepted():
    jd = ("Completed Bachelor's degree in Mechanical Engineering or Industrial "
          "Engineering, or a three-year DAE diploma in Textile Technology.")
    assert check_qualification(_requirement(jd),
                               "Education\nDiploma in Textile Technology, 2020").outcome != "satisfied"
    assert check_qualification(_requirement(jd),
                               "Education\nDAE diploma in Civil Engineering, 2020").outcome != "satisfied"
    assert check_qualification(_requirement(jd),
                               "Education\nDAE diploma in Textile Technology, expected 2027").outcome != "satisfied"
    assert check_qualification(_requirement(jd),
                               "Education\nDAE diploma in Textile Technology, 2020").outcome != "satisfied"


def test_named_alternative_can_rescue_a_negative_model_with_true_source_citation():
    jd = ("Completed Bachelor's degree in Mechanical Engineering or Industrial "
          "Engineering, or a three-year DAE diploma in Textile Technology.")
    req = _requirement(jd)
    cv = "Education\nCompleted three-year DAE diploma in Textile Technology, Fictional College, 2020"
    row = RequirementAssessment(requirement_id=req.requirement_id,
                                status="not_matched", unified_status="Not Found",
                                reason="Could not establish the first Bachelor's degree option.")
    assessed, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=assessed)[0]
    assert final.status == "matched"
    assert final.unified_status == "Found"
    assert final.evidence_segments and "DAE" in final.evidence_segments[0].text
    assert "explicitly accepted JD qualification" in final.reason


@pytest.mark.parametrize("jd,source", [
    ("Troubleshooting warp or weft breaks and recurring loom stoppages.",
     "Investigated recurring loom stops, warp and weft break trends; documented root causes."),
    ("Fabric defect identification and corrective action during weaving.",
     "Investigated fabric defects during weaving and documented corrective actions."),
    ("Customer incident investigation and corrective action documentation.",
     "Investigated customer incidents and recorded completed corrective actions."),
])
def test_negative_without_model_citations_shows_relevant_original_review_leads(jd, source):
    req = _requirement(jd)
    resume = f"Professional experience\n- {source}"
    originals = {s.segment_id: s for s in segment_resume(resume)}
    empty = RequirementAssessment(requirement_id=req.requirement_id,
                                  status="not_matched", unified_status="Not Found",
                                  reason="No evidence was cited by the assessor.")
    result = _retain_negative_review_checkpoints(req, empty, originals, [])
    assert result.unified_status == "Not Found"
    assert result.status == "not_matched"
    assert result.evidence_ids
    assert any(source in c.text for c in result.evidence_segments)
    assert result.review_recommended
    assert "not scoring proof" in result.reason
    reconciled = reconcile_final_assessments(requirements=[req], assessments=[result])[0]
    assert reconciled.status == "not_matched"
    ranked = score_candidate(candidate_name="Synthetic Test Candidate",
                             requirements=[req], assessments=[reconciled],
                             evaluation_mode="mixed", errors=[])
    assert ranked.matched_required == 0
    assert ranked.primary_score == 0.0


def test_unrelated_resume_is_not_fabricated_as_relevant_source():
    req = _requirement("Fabric defect identification and corrective action during weaving.")
    originals = {s.segment_id: s for s in segment_resume(
        "Professional experience\n- Managed regional sales visits and invoicing.")}
    empty = RequirementAssessment(requirement_id=req.requirement_id,
                                  status="not_matched", unified_status="Not Found",
                                  reason="No direct work evidence.")
    result = _retain_negative_review_checkpoints(req, empty, originals, [])
    assert not result.evidence_ids
    assert result.status == "not_matched"

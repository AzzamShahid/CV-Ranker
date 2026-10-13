import pytest

from cv_ranker.assessor import _validate_rows
from cv_ranker.constraints import explicitly_below_minimum
from cv_ranker.schemas import (
    LLMAssessmentItem, LLMCandidateAssessmentResponse, RequirementAssessment, ValidatedRequirement,
)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment, resolve_segment_ids


def req(id="R001", name="Python"):
    return ValidatedRequirement(requirement_id=id, name=name, priority="required", jd_evidence=name)


def match(id="R001"):
    return RequirementAssessment(requirement_id=id, status="matched", evidence="Python")


def score(requirements, assessments):
    return score_candidate(candidate_name="A", requirements=requirements,
                           assessments=assessments, evaluation_mode="llm_assessed", errors=[])


def test_duplicate_assessments_cannot_exceed_100():
    with pytest.raises(ValueError, match="Duplicate assessment"):
        score([req()], [match(), match()])


def test_unknown_and_missing_ids_cannot_produce_plausible_scores():
    with pytest.raises(ValueError, match="missing=.*R002"):
        score([req(), req("R002", "Docker")], [match()])
    with pytest.raises(ValueError, match="unexpected=.*R002"):
        score([req()], [match(), match("R002")])


def test_duplicate_frozen_requirements_rejected():
    with pytest.raises(ValueError, match="Duplicate frozen"):
        score([req(), req()], [match()])


def test_valid_scores_remain_unchanged():
    result = score([req()], [match()])
    assert result.primary_score == 100


def test_evidence_list_cannot_hide_a_fourth_bad_id():
    segments = [ResumeSegment(f"S{i:03d}", "skills", f"Skill {i}") for i in range(1, 5)]
    text, ids = resolve_segment_ids(["S001", "S002", "S003", "S999"], segments)
    assert text is None
    assert "S999" in ids


def test_duplicate_evidence_ids_rejected():
    segments = [ResumeSegment("S001", "skills", "Python")]
    text, _ = resolve_segment_ids(["S001", "S001"], segments)
    assert text is None


def test_numeric_understatement_is_not_accepted_as_five_years():
    assert explicitly_below_minimum("5+ years of Python experience", ["2 years of Python experience."])
    assert not explicitly_below_minimum("5+ years of Python experience", ["6 years of Python experience."])
    assert not explicitly_below_minimum("5+ years of Python experience", ["2 years Python. 6 years Python."])


def test_numeric_guard_does_not_confuse_unrelated_subjects():
    assert not explicitly_below_minimum("5+ years of Python experience", ["2 years of Java experience."])
    assert not explicitly_below_minimum("5+ years of experience", ["2 years in a role."])


def test_invalid_under_threshold_match_goes_to_correction_not_credit():
    r = req(name="5+ years of Python experience")
    text = "Work Experience:\n2 years of Python experience."
    segments = [ResumeSegment("S001", "experience", "2 years of Python experience.")]
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="matched", evidence_ids=["S001"])
    ])
    valid, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[r], resume_text=text, segments=segments
    )
    assert "R001" in invalid
    assert "R001" not in valid
    assert any("below the JD minimum" in w for w in warnings)


def test_fractional_year_claims_preserve_decimal_point():
    assert explicitly_below_minimum("5+ years of Python experience", ["2.5 years of Python experience."])
    assert not explicitly_below_minimum("2+ years of Python experience", ["2.5 years of Python experience."])

"""Regression for a missing exact bachelor's degree masking a related MSc."""

from cv_ranker.qualification_validation import apply_qualification_checks
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import segment_resume
from cv_ranker.unified import (FINAL_ADJUDICATION_PROMPT, UNIFIED_PROMPT,
                               _needs_independent_overlap_review)


def _requirement():
    return ValidatedRequirement(
        requirement_id="R002", priority="required",
        name="Completed Bachelor's degree in Computer Science.",
        jd_evidence="Completed Bachelor's degree in Computer Science.",
        constraint=RequirementConstraint(kind="education", origin="source_rules",
                                         degree_level="bachelor",
                                         field_of_study="Computer Science"),
    )


def _llm_row(segment, *, status="Not Found", reason="No BS Computer Science stated."):
    return RequirementAssessment(
        requirement_id="R002", status="not_matched", unified_status=status,
        evidence_ids=[segment.segment_id],
        evidence_segments=[EvidenceCitation(
            segment_id=segment.segment_id, section=segment.section,
            text=segment.text)],
        reason=reason,
    )


def test_msc_ai_not_found_requires_separate_subject_overlap_adjudication():
    cv = "Education\nMSc Artificial Intelligence | West Research Academy (fictional), 2022"
    segment = next(s for s in segment_resume(cv) if "MSc" in s.text)
    row = _llm_row(segment, reason=(
        "The candidate has an MSc in Artificial Intelligence but no "
        "Bachelor's degree in Computer Science is mentioned."))
    assert _needs_independent_overlap_review(
        _requirement(), row, {segment.segment_id: segment}, cv)


def test_source_cited_related_msc_is_transferable_but_not_direct_bachelor_credit():
    cv = "Education\nMSc Artificial Intelligence | West Research Academy (fictional), 2022"
    segment = next(s for s in segment_resume(cv) if "MSc" in s.text)
    row = _llm_row(segment, status="Transferable", reason=(
        "A completed master's degree in Artificial Intelligence is a related "
        "higher-level computing qualification to Computer Science, but the "
        "particular Bachelor's degree is not reported."))
    checked, _, _ = apply_qualification_checks(
        requirements=[_requirement()], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].unified_status == "Transferable"
    assert checked[0].evidence_ids == [segment.segment_id]
    assert checked[0].review_recommended


def test_unrelated_higher_degree_does_not_transfer_just_because_its_higher():
    cv = "Education\nPhD Classical Archaeology | College, 2022"
    segment = next(s for s in segment_resume(cv) if "PhD" in s.text)
    row = _llm_row(segment, reason=(
        "The completed archaeology doctorate is unrelated to the named field."))
    checked, _, _ = apply_qualification_checks(
        requirements=[_requirement()], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].unified_status == "Not Found"


def test_both_model_prompts_require_independent_field_relationship_judgment():
    assert "TWO SEPARATE determinations" in FINAL_ADJUDICATION_PROMPT
    assert "not sufficient reasoning for not_found" in FINAL_ADJUDICATION_PROMPT
    assert "Do NOT stop degree analysis" in UNIFIED_PROMPT
    assert "never automatically" in UNIFIED_PROMPT.casefold()

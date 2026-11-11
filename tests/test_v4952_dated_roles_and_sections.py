"""Regression: dated work must not require the literal phrase 'N years'."""

from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.requirement_typing import add_requirement_types
from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.qualification_validation import check_qualification


JD = "At least 3 years of full-time professional experience in native Android development."


def _req(jd=JD):
    return add_requirement_types([ValidatedRequirement(
        requirement_id="R001", name=jd, priority="required", jd_evidence=jd,
    )], jd)[0]


def _candidate(segments):
    cited = [s for s in segments if "Sep 2018" in s.text or "Mar 2022" in s.text]
    return RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence_ids=[s.segment_id for s in cited],
        evidence_segments=[EvidenceCitation(
            segment_id=s.segment_id, section=s.section, text=s.text) for s in cited],
        reason="The CV reports completed native Android engineering work in dated full-time positions.",
    )


def test_android_calendar_role_ranges_are_numeric_tenure_without_year_words():
    resume = (
        "Professional summary\n"
        "Sep 2018 - Feb 2022 | Full time Delivered native Android checklists for inspection teams. "
        "Paired with field trainers, supported device rollouts and diagnosed failures on handsets.\n"
        "Senior Android Engineer | Ochre Route Mar 2022 - Oct 2026 | Full time "
        "I replayed event histories, agreed with the API engineer which changes could merge "
        "and added a visible review state for conflicting signatures.\n"
    )
    req = _req()
    segments = segment_resume(resume)
    assert all(s.section == 'summary' for s in segments)
    duration = check_experience(req, resume, segments)
    assert duration.outcome == 'role_semantic', duration
    assert duration.role_groups
    assert len(duration.role_groups[0]) >= 1
    assessed, _, _ = apply_experience_checks(
        requirements=[req], assessments=[_candidate(segments)], resume_text=resume)
    assert assessed[0].status == 'matched'
    assert assessed[0].unified_status == 'Found'


def test_summary_project_timeline_is_not_employment():
    resume = (
        "Summary\n"
        "Offline maps benchmark Jan 2020 - Dec 2024; deployed a demo prototype "
        "but never held a full-time Android engineering position.\n"
    )
    checked = check_experience(_req(), resume)
    assert checked.outcome != 'role_semantic'


def test_years_from_unrelated_employment_cannot_be_transferred_to_android():
    resume = (
        "Work history\n"
        "Cashier | Market Co Jan 2018 - Dec 2025\n"
        "- Managed checkout operators and daily tills.\n"
        "Skills\n"
        "Native Android development\n"
    )
    checked = check_experience(_req(), resume)
    assert checked.outcome == 'role_semantic' or checked.outcome == 'not_evidenced'
    candidates = _candidate(segment_resume(resume))
    candidates = candidates.model_copy(update={'evidence_ids': [], 'evidence_segments': []})
    assessed, _, _ = apply_experience_checks(
        requirements=[_req()], assessments=[candidates], resume_text=resume)
    assert assessed[0].status != 'matched'


def test_dated_job_title_alone_cannot_prove_professional_duty():
    resume = "Summary\nSenior Android Engineer | Fictional Co Jan 2018 - Dec 2023\n"
    checked = check_experience(_req(), resume)
    assert checked.outcome != 'role_semantic'


def test_future_end_date_cannot_supply_completed_experience():
    resume = (
        "Work experience\n"
        "Senior Android Engineer | Fictional Co Jan 2025 - Dec 2030 | Full time "
        "Developed native Android application workflows.\n")
    assert check_experience(_req(), resume).outcome != 'role_semantic'


def test_missing_education_heading_does_not_hide_source_documented_degree():
    jd = "Completed Bachelor's degree in Software Engineering."
    resume = ("Professional summary\n"
              "BS Software Engineering | Central City University, 2022\n"
              "Built offline scheduling workflows for mobile teams.\n")
    req = _req(jd)
    result = check_qualification(req, resume)
    assert result.outcome == 'satisfied', result


def test_skills_heading_and_academic_qualifications_are_layout_not_skill_aliases():
    resume = ("Tools & Frameworks\n"
              "Container orchestration\n"
              "Observability tooling\n"
              "Academic Qualifications\n"
              "BS Computer Science, Central City University, 2021\n")
    segments = segment_resume(resume)
    assert [s.section for s in segments] == ['skills', 'skills', 'education']
    jd = "Completed Bachelor's degree in Computer Science."
    assert check_qualification(_req(jd), resume).outcome == 'satisfied'


def test_unheaded_bs_abbreviation_in_skill_list_is_not_automatically_a_degree():
    jd = "Completed Bachelor's degree in Software Engineering."
    resume = "Technical skills\nBS Software Engineering\n"
    assert check_qualification(_req(jd), resume).outcome != 'satisfied'

"""Source-frozen years and degrees across professions, with safe degree transfer."""

from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.fallback import fallback_requirements, structural_hints
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.qualification_validation import check_qualification
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (
    CandidateResult, JDRequirement, JDValidationResponse, RankingReport,
    RequirementAssessment,
)
from cv_ranker.segments import segment_resume
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.final_decisions import FocusedJudgment, SourceJudgment, reconcile_candidate


def test_required_years_and_degree_survive_blank_lines_and_llm_omission():
    jd = ("REQUIRED EXPERIENCE:\n\n"
          "Minimum 3 years of professional experience delivering software solutions.\n\n"
          "REQUIRED EDUCATION:\n\n"
          "Bachelor's degree in Computer Science required.\n\n"
          "REQUIRED SKILLS:\n- Python\n")

    class LLMOnlyNoticedPython:
        def invoke_structured(self, **kwargs):
            return JDValidationResponse(requirements=[JDRequirement(
                name="Python", priority="required", evidence="Python")])

    requirements, _, warnings = validate_jd_requirements(
        jd_text=jd, candidates=[], settings=Settings(), llm=LLMOnlyNoticedPython())
    assert len(requirements) == 3
    assert [r.name for r in requirements] == [
        "Minimum 3 years of professional experience delivering software solutions.",
        "Bachelor's degree in Computer Science required.", "Python"]
    typed = [classify_requirement(req, jd) for req in requirements]
    assert typed[0].minimum_years == 3
    assert typed[1].kind == "education"
    assert typed[1].degree_level == "bachelor"
    assert typed[1].field_of_study == "Computer Science"
    assert any("source completeness" in warning for warning in warnings)


def test_headings_and_jd_qualifications_are_not_confused_with_benefits():
    jd = ("BASIC QUALIFICATIONS:\n\n"
          "At least 4 years of professional accounting experience.\n"
          "BSc Accounting\n"
          "BENEFITS:\n- 25 days annual leave\n")
    hints = structural_hints(jd)
    assert [h.name for h in hints] == [
        "At least 4 years of professional accounting experience.", "BSc Accounting"]
    assert classify_requirement(fallback_requirements(jd, [], 30)[1], jd).field_of_study == "Accounting"


@pytest.mark.parametrize("extension", ["txt", "docx", "pdf"])
def test_fictional_applied_ai_jd_has_same_tenure_and_skill_counts_in_every_format(extension):
    path = Path("sample_data/applied_ai_documents/jd") / f"Applied_AI_ML_Engineer_Updated_JD.{extension}"
    jd = extract_text(path)
    requirements = fallback_requirements(jd, [], 30)
    assert len([r for r in requirements if r.priority == "required"]) == 10
    assert len([r for r in requirements if r.priority == "preferred"]) == 7
    years = [(r, classify_requirement(r, jd)) for r in requirements
             if "3 years" in r.name]
    assert len(years) == 1
    assert years[0][1].kind == "experience"
    assert years[0][1].minimum_years == 3
    assert years[0][1].source_line_numbers
    assert not any("Academic coursework" in r.name and "3 years" not in r.name
                   for r in requirements)
    assert not any(classify_requirement(r, jd).kind == "education" for r in requirements)


@pytest.mark.parametrize("education_line", [
    "Bachelor's degree in Computer Science.",
    "BSc Computer Science.",
    "BS Software Engineering.",
])
def test_degree_criterion_stays_required_without_repeating_the_word_required(education_line):
    jd = "REQUIRED EDUCATION:\n\n" + education_line + "\n\nREQUIRED SKILLS:\n- Python\n"
    rows = fallback_requirements(jd, [], 30)
    assert [r.name for r in rows] == [education_line, "Python"]
    assert rows[0].priority == "required"
    assert classify_requirement(rows[0], jd).field_of_study is not None


def test_explicit_education_and_project_headings_leave_experience_section():
    cv = ("PROFESSIONAL EXPERIENCE\nBuilt client applications.\n"
          "SELECTED PROJECT OUTCOMES\nDesigned a personal demo.\n"
          "EDUCATION AND NOTES\nBS Software Engineering | Example University, 2024\n")
    segments = segment_resume(cv)
    assert next(s.section for s in segments if "Designed a personal demo" in s.text) == "projects"
    assert next(s.section for s in segments if "BS Software Engineering" in s.text) == "education"


def _degree_assessment(cv_degree: str, result: str, reason: str):
    jd = "REQUIRED EDUCATION:\nBachelor's degree in Computer Science\n"
    req = fallback_requirements(jd, [], 30)[0]
    req = req.model_copy(update={"constraint": classify_requirement(req, jd)})
    cv = "EDUCATION AND NOTES\n" + cv_degree + " | Example University, 2024\n"
    segments = segment_resume(cv)
    qualification = check_qualification(req, cv, segments)
    report = RankingReport(job_description_source="synthetic", jd_validation_mode="test",
                           yake_candidates=[], requirements=[req], candidates=[
                               CandidateResult(candidate_name="Applicant", assessments=[
                                   RequirementAssessment(requirement_id=req.requirement_id,
                                                         status="not_matched",
                                                         qualification_check=qualification)
                               ])])

    class Judgment:
        calls = 0

        def invoke_structured(self, **kwargs):
            self.calls += 1
            sid = next(c.segment_id for c in qualification.claims if c.state == "claimed")
            return FocusedJudgment(result=result, explanation=reason,
                                   supporting_sources=[SourceJudgment(
                                       segment_id=sid,
                                       why="The named completed degree is recorded in the CV.",
                                       highlight_terms=[cv_degree])])

    llm = Judgment()
    final = reconcile_candidate(report, 0, segment_ledger(segments), llm=llm)
    return req, qualification, final, llm.calls


def test_exact_computer_science_degree_found_without_semantic_call():
    _, check, final, calls = _degree_assessment(
        "BS Computer Science", "not_evidenced", "irrelevant test response")
    assert check.outcome == "satisfied"
    assert final["Criteria"][0]["Result"] == "Found"
    assert final["Required matched"] == 1
    assert calls == 0


def test_related_software_engineering_degree_transferable_with_cited_llm_decision():
    _, check, final, calls = _degree_assessment(
        "BS Software Engineering", "transferable",
        "Software Engineering is a related computing discipline with overlapping "
        "software design, algorithms and systems coursework, but is not the "
        "exact Computer Science field requested by the JD.")
    assert check.outcome == "mismatch"
    assert calls == 1
    assert final["Criteria"][0]["Result"] == "Transferable"
    assert final["Transferable"] == 1
    assert final["Required matched"] == 0
    assert final["Criteria"][0]["Review recommended"]
    assert any(row["Validated against CV"] for row in final["Criteria"][0]["Checkpoints"])


def test_unrelated_arts_degree_not_found_and_not_equal_score():
    _, check, final, calls = _degree_assessment(
        "BS Fine Arts", "not_evidenced",
        "A Fine Arts degree does not establish the computing-field education requested.")
    assert check.outcome == "mismatch"
    assert calls == 1
    assert final["Criteria"][0]["Result"] == "Not Found"
    assert final["Required matched"] == 0
    assert final["Transferable"] == 0


def test_cloud_cannot_upgrade_wrong_degree_field_to_direct_found():
    _, check, final, calls = _degree_assessment(
        "BS Fine Arts", "matched",
        "Incorrectly proposes that any bachelor's degree equals the required field.")
    assert check.outcome == "mismatch"
    assert calls == 1
    assert final["Criteria"][0]["Result"] == "Not Found"
    assert final["Required matched"] == 0

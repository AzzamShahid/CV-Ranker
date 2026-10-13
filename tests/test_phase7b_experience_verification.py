"""Phase 7B: source-grounded explicit experience, no date arithmetic."""
from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.pipeline import CVRanker
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import RequirementAssessment, ValidatedRequirement


def requirement(name='5+ years of Python experience', id='R001'):
    req = ValidatedRequirement(requirement_id=id, name=name, priority='required', jd_evidence=name)
    return req.model_copy(update={'constraint': classify_requirement(req, 'Required Experience:\n' + name)})


def evaluate(statement, name='5+ years of Python experience'):
    req = requirement(name)
    return check_experience(req, 'Experience:\n' + statement)


@pytest.mark.parametrize('source,outcome', [
    ('6 years of Python experience.', 'sufficient'),
    ('5+ years of Python experience.', 'sufficient'),
    ('at least 5 years of Python experience.', 'sufficient'),
    ('2 years of Python experience.', 'insufficient'),
    ('2.5 years of Python experience.', 'insufficient'),
    ('2-4 years of Python experience.', 'insufficient'),
    ('2–4 years of Python experience.', 'insufficient'),
    ('4-6 years of Python experience.', 'ambiguous'),
    ('2+ years of Python experience.', 'ambiguous'),
    ('6 years of Java experience.', 'not_evidenced'),
    ('Python\n6 years of professional experience.', 'ambiguous'),
    ('2019–2026 Python developer.', 'not_evidenced'),
    ('Currently learning Python for 6 years.', 'ambiguous'),
    ('6 years of Python experience. 2 years of Python experience.', 'ambiguous'),
    ('6 years of Java and 2 years of Python experience.', 'insufficient'),
    ('No Python experience. 6 years of Java experience.', 'insufficient'),
    ('Python developer with 5 years of professional experience building AI products.', 'ambiguous'),
])
def test_numeric_evidence_decisions(source, outcome):
    assert evaluate(source).outcome == outcome


def test_non_technical_hr_domain():
    result = evaluate('4 years as an HR officer managing payroll.', '3 years relevant experience in HR')
    assert result.outcome == 'sufficient'
    assert result.claims[0].segment_id == 'S001'


def test_general_experience_without_specific_subject():
    result = evaluate('6 years of professional work experience.', '5+ years of professional experience')
    assert result.outcome == 'sufficient'
    assert result.subject is None


def test_subject_specific_do_not_use_unrelated_duration():
    result = evaluate('6 years of Java experience. 2 years of Python experience.')
    assert result.outcome == 'insufficient'
    assert len(result.claims) == 1
    assert 'Python' in result.claims[0].quote


def test_relevant_negation_conflict_not_auto_match():
    result = evaluate('6 years of Python experience.\nNo Python experience.')
    assert result.outcome == 'ambiguous'


def test_source_id_and_copy_of_verbatim_evidence():
    req = requirement()
    old = RequirementAssessment(requirement_id=req.requirement_id,
                                status='matched', evidence_ids=['S999'],
                                evidence='6 years of Java experience.')
    new, warnings, changed = apply_experience_checks(
        requirements=[req], assessments=[old], resume_text='Experience:\n2 years of Python experience.')
    assert changed
    assert new[0].status == 'not_matched'
    assert new[0].evidence_ids == ['S001']
    assert new[0].evidence == '2 years of Python experience.'
    assert new[0].experience_check.outcome == 'insufficient'
    assert new[0].experience_check.changed_status
    assert 'experience insufficient' in warnings[0]


def test_no_explicit_duration_downgrades_unsubstantiated_llm_match():
    req = requirement()
    old = RequirementAssessment(requirement_id='R001', status='matched', evidence='Python')
    rows, notes, changed = apply_experience_checks(
        requirements=[req], assessments=[old], resume_text='Skills:\nPython')
    assert changed and rows[0].status == 'uncertain'
    assert rows[0].experience_check.outcome == 'not_evidenced'
    assert rows[0].evidence_ids == []


def test_explicit_sufficient_years_can_correct_direct_false_negative():
    req = requirement()
    old = RequirementAssessment(requirement_id='R001', status='not_matched')
    rows, _, changed = apply_experience_checks(
        requirements=[req], assessments=[old], resume_text='Experience:\n6 years of Python experience.')
    assert changed and rows[0].status == 'matched'
    assert rows[0].evidence_ids == ['S001']
    assert rows[0].experience_check.claims[0].lower_years == 6


def test_other_requirement_assessments_not_touched():
    req = requirement('Python')
    row = RequirementAssessment(requirement_id='R001', status='matched', evidence='Python')
    result, notes, changed = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text='Python')
    assert not changed and not notes and result[0] == row


def test_report_contains_experience_check_and_scoring_uses_final_status(tmp_path):
    jd = tmp_path/'job.txt'
    jd.write_text('Required Skills:\nPython\n5+ years of Python experience\n', encoding='utf-8')
    resume = tmp_path/'candidate.txt'
    resume.write_text('Skills:\nPython\nExperience:\n2 years of Python experience.\n', encoding='utf-8')
    report = CVRanker(Settings(), use_llm=False).run(jd, [resume])
    assert len(report.requirements) == 2
    candidate = report.candidates[0]
    years = next(a for a in candidate.assessments if a.experience_check is not None)
    assert years.status == 'not_matched'
    assert years.experience_check.outcome == 'insufficient'
    assert candidate.total_required == 2
    assert 0 <= candidate.primary_score <= 100
    assert report.model_dump()['candidates'][0]['assessments'][1]['experience_check']['outcome'] == 'insufficient'


def test_minimum_from_typing_used_not_model_free_text():
    req = requirement()
    assert req.constraint.minimum_years == 5
    assert check_experience(req, 'Experience:\n5 years of Python experience').outcome == 'sufficient'


def test_cross_department_degree_is_not_treated_as_experience():
    r = requirement("Bachelor's degree in Computer Science")
    assert check_experience(r, 'Education:\nBachelor in Computer Science').outcome == 'not_applicable'


def test_numeric_range_with_upper_below_minimum_is_insufficient():
    result = evaluate('3-4 yrs of Python experience.')
    assert result.outcome == 'insufficient'
    assert result.claims[0].upper_years == 4


def test_explicit_no_experience_downgrades_match_to_negative():
    r = requirement()
    checked = check_experience(r, 'Experience:\nNo Python experience.')
    assert checked.outcome == 'insufficient'
    rows, _, changed = apply_experience_checks(
        requirements=[r], assessments=[RequirementAssessment(requirement_id='R001', status='matched')],
        resume_text='Experience:\nNo Python experience.')
    assert changed and rows[0].status == 'not_matched'


def test_learning_only_without_duration_remains_uncertain():
    assert evaluate('Currently learning Python.').outcome == 'ambiguous'


def test_conflicting_learning_and_positive_duration_needs_review():
    assert evaluate('6 years of Python experience.\nCurrently learning Python.').outcome == 'ambiguous'


@pytest.mark.parametrize('jd,subject', [
    ('5 years in Python', 'Python'),
    ('3 yrs using SAP', 'SAP'),
    ('5 years of experience in Finance', 'Finance'),
    ('5 years Python', 'Python'),
    ('5 years of professional experience', None),
])
def test_jd_source_subject_forms(jd, subject):
    assert requirement(jd).constraint.subject == subject


def test_copied_job_requirement_cannot_prove_candidate_years():
    source = 'Professional Summary:\nCandidates must have 6 years of Python experience required.'
    assert check_experience(requirement(), source).outcome == 'not_evidenced'


def test_skill_list_plus_general_years_is_review_not_skill_specific_credit():
    r = requirement()
    resume = 'Skills:\nPython\nExperience:\n6 years of professional experience.'
    report = check_experience(r, resume)
    assert report.outcome == 'ambiguous'
    rows, _, changed = apply_experience_checks(
        requirements=[r], assessments=[RequirementAssessment(requirement_id='R001', status='not_matched')],
        resume_text=resume)
    assert changed and rows[0].status == 'uncertain'
    assert rows[0].experience_check.outcome == 'ambiguous'


def test_explicit_years_as_hr_officer_count_for_hr_experience_not_hr_skill():
    assert evaluate('4 years as an HR officer managing payroll.',
                    '3 years relevant experience in HR').outcome == 'sufficient'


def test_total_career_years_after_python_title_are_not_python_years():
    result = evaluate('Python developer with 5 years of professional experience building AI products.')
    assert result.outcome == 'ambiguous'

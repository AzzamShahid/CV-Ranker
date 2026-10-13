"""Regression cases discovered by the October 13 Phase 7F *live* run.

Independent of synthetic label lookup; a cited ID must support competence and
an unrelated tenure claim must not gain a partial matching status from Qwen.
"""

import pytest

from cv_ranker.assessor import _validate_rows
from cv_ranker.experience_validation import apply_experience_checks
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.segments import segment_resume


def req(name, kind=None):
    base = ValidatedRequirement(requirement_id="R001", name=name, priority="required", jd_evidence=name)
    if kind == 'experience':
        return base.model_copy(update={'constraint': classify_requirement(base, 'Required Experience:\n' + name)})
    return base


def model_decision(req_name, cv, cited, term=None):
    source = segment_resume(cv)
    ids = [s.segment_id for s in source if cited in s.text]
    assert ids, (cited, source)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id='R001', status='matched', evidence_ids=ids[:1], matched_term=term)])
    return _validate_rows(response=response, requirements=[req(req_name)], resume_text=cv, segments=source)


@pytest.mark.parametrize('candidate,requirement,cited,term', [
    ('Currently learning patient care.\nVital signs monitoring\n1 year of nursing experience.',
     'Electronic health records', '1 year of nursing experience.', None),
    ('1 year of nursing experience.', 'Electronic health records',
     '1 year of nursing experience.', 'nursing'),
    ('4 years of accounting experience.', 'Inventory management',
     '4 years of accounting experience.', None),
    ('2+ years of backend experience.', 'Contract negotiation',
     '2+ years of backend experience.', 'backend'),
])
def test_model_cannot_substitute_generic_tenure_for_named_competency(candidate, requirement, cited, term):
    valid, invalid, notes, _ = model_decision(requirement, candidate, cited, term)
    assert 'R001' not in valid
    assert invalid == {'R001'}
    assert any('bare unrelated tenure' in note for note in notes)


def test_explicit_named_competency_in_tenure_claim_remains_eligible():
    valid, invalid, _, _ = model_decision(
        'Electronic health records',
        '2 years of electronic health records experience.',
        '2 years of electronic health records experience.')
    assert valid['R001'].status == 'matched'
    assert not invalid


def test_specific_semantic_action_is_not_blocked():
    valid, invalid, _, _ = model_decision(
        'REST API development', 'Built REST endpoints with FastAPI.',
        'Built REST endpoints with FastAPI.')
    assert valid['R001'].status == 'matched'
    assert not invalid


@pytest.mark.parametrize('jd,cv', [
    ('3+ years of HR experience', 'Candidate profile for HR Generalist.\nSales\nMarketing\n3 years in marketing.\nExcel'),
    ('2+ years of nursing experience', 'Candidate profile for Registered Nurse.\nDental customer service\n3 years of reception experience.\nElectronic health records'),
    ('3+ years of procurement experience', 'Candidate profile for Procurement Analyst.\n3 years of warehouse experience.'),
])
def test_unrelated_tenure_is_not_upgraded_to_review_by_wrong_llm_claim(jd, cv):
    requirement = req(jd, kind='experience')
    initial = RequirementAssessment(requirement_id='R001', status='matched')
    rows, notes, changed = apply_experience_checks(
        requirements=[requirement], assessments=[initial], resume_text=cv)
    assert rows[0].status == 'not_matched'
    assert changed
    assert rows[0].experience_check.outcome == 'not_evidenced'


def test_claimed_competency_without_numeric_years_stays_review_needed():
    requirement = req('5+ years of Python experience', kind='experience')
    cv = 'Skills:\nPython\nExperience:\n4 years of Java experience.'
    rows, notes, changed = apply_experience_checks(
        requirements=[requirement], assessments=[RequirementAssessment(requirement_id='R001', status='matched')],
        resume_text=cv)
    assert rows[0].status == 'uncertain'
    assert changed

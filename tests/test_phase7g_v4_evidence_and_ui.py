"""Adversarial V3 evidence-report defects: prevent false credit, keep UI truthful."""
from pathlib import Path

import pytest

from cv_ranker.assessor import _direct_source_guard, _validate_rows, SYSTEM_PROMPT, CORRECTION_PROMPT
from cv_ranker.compound_validation import evaluate_compound
from cv_ranker.schemas import (
    LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
)
from cv_ranker.segments import segment_resume
from cv_ranker.text_utils import classify_requirement_tone, non_candidate_requirement_copy

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'sample_data' / 'applied_ai_resumes'


def req(name, rid='R001'):
    return ValidatedRequirement(requirement_id=rid, name=name, priority='required', jd_evidence=name)


def sample(name):
    return (DEMO / f'{name}.txt').read_text(encoding='utf-8')


def guard(name, content):
    return _direct_source_guard(req(name), content, segment_resume(content)).status


@pytest.mark.parametrize('name', [
    'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch',
    'Natural Language Processing', 'LLM integrations', 'Model evaluation',
    'AI application development',
])
def test_copied_job_requirements_do_not_generate_any_positive_matches(name):
    content = sample('12_salman_copied_jd_negations')
    assert guard(name, content) != 'matched'
    copied = next(s for s in segment_resume(content) if 'TARGET JOB DESCRIPTION' in s.text)
    assert copied.section == 'non_candidate'


@pytest.mark.parametrize('content,name', [
    ('Experience:\nNo professional NLP, hosted LLM integration, LangChain or LangGraph experience claimed', 'LangChain'),
    ('Experience:\nNo professional NLP, hosted LLM integration, LangChain or LangGraph experience claimed', 'LangGraph'),
    ('Experience:\nHas not used LangChain or LangGraph professionally; has built another retrieval system.', 'LangGraph'),
    ('Skills:\nNo hands-on experience with Angular, Vue, or React.', 'React'),
    ('Skills:\nNo professional experience with AWS, GCP, and Azure.', 'Azure'),
    ('Skills:\nI have no professional Java or Kotlin experience.', 'Kotlin'),
])
def test_coordinated_negation_never_grants_credit(content, name):
    assert guard(name, content) == 'not_matched'
    assert classify_requirement_tone(content, name) == 'negated'


@pytest.mark.parametrize('text,name', [
    ('Skills:\nPython\nNo Redis experience.', 'Python'),
    ('Experience:\nNo Python experience; built Docker systems.', 'Docker'),
    ('Experience:\nHas not used LangGraph; built extensive LangChain workflows.', 'LangChain'),
    ('Projects:\nBuilt a job posting classifier using Python.', 'Python'),
])
def test_unrelated_negation_does_not_poison_positive_claims(text, name):
    assert guard(name, text) == 'matched'


def test_named_framework_denials_in_real_resumes():
    assert guard('LangGraph', sample('03_sara_functional_transfer')) != 'matched'
    rida = sample('06_rida_medical_imaging')
    assert guard('LangChain', rida) != 'matched'
    assert guard('LangGraph', rida) != 'matched'


def test_llm_with_valid_copied_segment_id_gets_no_positive_credit():
    content = sample('12_salman_copied_jd_negations')
    segments = segment_resume(content)
    copied = next(s for s in segments if s.section == 'non_candidate' and 'TARGET JOB DESCRIPTION' in s.text)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id='R001', status='matched', evidence_ids=[copied.segment_id]
    )])
    valid, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req('Machine Learning')], resume_text=content, segments=segments)
    assert 'R001' in invalid and 'R001' not in valid
    assert any('non-candidate' in w for w in warnings)


@pytest.mark.parametrize('name', ['LangChain', 'LangGraph'])
def test_llm_denied_framework_citation_is_downgraded(name):
    content = sample('06_rida_medical_imaging')
    segments = segment_resume(content)
    negative = next(s for s in segments if 'No professional NLP' in s.text)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id='R001', status='matched', evidence_ids=[negative.segment_id]
    )])
    valid, invalid, _, _ = _validate_rows(
        response=response, requirements=[req(name)], resume_text=content, segments=segments)
    assert not invalid and valid['R001'].status == 'not_matched'


def test_compound_alternatives_cannot_match_copied_requirements():
    req0 = req('TensorFlow or PyTorch')
    constraint = req0.constraint.model_copy(update={
        'kind': 'skill', 'operator': 'any_of', 'options': ['TensorFlow', 'PyTorch']
    })
    compound = evaluate_compound(req0.model_copy(update={'constraint': constraint}),
                                 sample('12_salman_copied_jd_negations'))
    # A genuine future-learning clause is tentative, never a fulfilled OR
    # alternative. It can be shown for human review without direct credit.
    assert compound.outcome in {'not_matched', 'uncertain'}
    assert all(item.status != 'matched' for item in compound.components)


def test_citation_over_limit_has_specific_error_and_row_retry():
    content = 'Skills:\nPython\nPython scripting\nPython APIs\nPython libraries'
    segments = segment_resume(content)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id='R001', status='matched', evidence_ids=[s.segment_id for s in segments]
    )])
    valid, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req('Python')], resume_text=content, segments=segments)
    assert 'R001' in invalid and not valid
    assert any('maximum 3' in warning for warning in warnings)
    assert not any('unknown/invalid evidence' in warning for warning in warnings)


def test_main_prompts_explicitly_reject_copied_jd_and_shared_negation():
    assert 'JD excerpts' in SYSTEM_PROMPT
    assert 'has not used A or B' in SYSTEM_PROMPT
    assert 'no more than THREE' in CORRECTION_PROMPT


def test_ui_has_distinct_dynamic_frozen_and_filtered_counts():
    source = (ROOT / 'cv_ranker/ui/dashboard.py').read_text(encoding='utf-8')
    assert 'buckets[\'jd_required\'][\'found\']}/{buckets[\'jd_required\'][\'total\']}' in source
    assert 'buckets[\'jd_preferred\'][\'found\']}/{buckets[\'jd_preferred\'][\'total\']}' in source
    assert 'buckets["experience"]["total"]' in source
    assert 'buckets["education"]["total"]' in source
    assert 'Showing {len(filtered)} of {len(matrix)}' in source
    assert 'cv_candidate_selector' in source
    assert 'st.session_state.pop("cv_candidate_selector", None)' in source


def test_do_not_misclassify_real_work_on_job_postings_as_a_copied_jd():
    assert not non_candidate_requirement_copy('Built a job posting classifier using Python.')

@pytest.mark.parametrize('filename,requirement', [
    ('12_salman_copied_jd_negations.pdf', 'Machine Learning'),
    ('12_salman_copied_jd_negations.pdf', 'TensorFlow'),
    ('12_salman_copied_jd_negations.pdf', 'LLM integrations'),
    ('06_rida_medical_imaging.pdf', 'LangChain'),
    ('06_rida_medical_imaging.pdf', 'LangGraph'),
    ('03_sara_functional_transfer.pdf', 'LangGraph'),
])
def test_exact_pdf_extraction_regressions(filename, requirement):
    from cv_ranker.documents import extract_text
    path = ROOT / 'sample_data' / 'applied_ai_documents' / 'pdf' / filename
    assert guard(requirement, extract_text(path)) != 'matched'


def test_fallback_also_rejects_adversarial_examples():
    from cv_ranker.fallback import fallback_assessment
    for basename, skill in [
        ('12_salman_copied_jd_negations', 'Machine Learning'),
        ('12_salman_copied_jd_negations', 'Deep Learning'),
        ('06_rida_medical_imaging', 'LangGraph'),
        ('03_sara_functional_transfer', 'LangGraph'),
    ]:
        assert fallback_assessment(req(skill), sample(basename)).status != 'matched'


def test_assessor_passes_frozen_jd_provenance_to_model():
    from cv_ranker.assessor import _compact_requirements
    requirement = req('TensorFlow or PyTorch')
    payload = _compact_requirements([requirement])
    assert 'priority=required' in payload
    assert 'JD wording=TensorFlow or PyTorch' in payload

"""Phase 7F.2 regressions from archived release-to-release forensic review.

No job-specific skill vocabularies or model-dependent assumptions are used.
"""
import pytest

from cv_ranker.assessor import _direct_source_guard
from cv_ranker.fallback import fallback_assessment
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume


def req(name: str) -> ValidatedRequirement:
    return ValidatedRequirement(requirement_id='R001', name=name,
                                priority='required', jd_evidence=name)


@pytest.mark.parametrize('text,expected', [
    ('No experience with\nPython', 'not_matched'),
    ('No experience with:\nPython', 'not_matched'),
    ('No experience with\nPython\nDjango', 'not_matched'),
    ('Never used\nPython', 'not_matched'),
    ('Not familiar with\nPython', 'not_matched'),
    ('Currently learning\nPython', 'uncertain'),
    ('Learning:\nPython\nDjango', 'uncertain'),
    ('Studying\nPython', 'uncertain'),
    ('Preparing for\nPython', 'uncertain'),
    ('Interested in\nPython', 'uncertain'),
    ('We require\nPython\nDjango', 'not_matched'),
    ('Candidate must\nPython', 'not_matched'),
    ('Requirements:\nPython', 'not_matched'),
    ('Job Description:\nPython', 'not_matched'),
    ('Python\nDjango\n4 years of professional experience.', 'matched'),
    ('Python\nDjango', 'matched'),
])
def test_qualifier_scope_in_fallback(text, expected):
    assert fallback_assessment(req('Python'), text).status == expected


@pytest.mark.parametrize('text,expected', [
    ('No experience with\nPython\nDjango', 'not_matched'),
    ('No experience with:\nPython\nDjango', 'not_matched'),
    ('Currently learning\nPython\nDjango', 'uncertain'),
    ('We require\nPython\nDjango', 'not_matched'),
    ('Python\nDjango', 'matched'),
])
def test_second_item_in_qualifier_list(text, expected):
    assert fallback_assessment(req('Django'), text).status == expected


@pytest.mark.parametrize('text,expected', [
    ('No experience with\nPython\nDjango', 'not_matched'),
    ('Currently learning\nPython\nDjango', 'uncertain'),
    ('We require\nPython\nDjango', 'not_matched'),
    ('Python\nDjango', 'matched'),
])
def test_same_scope_rules_in_llm_direct_source_guard(text, expected):
    assert _direct_source_guard(req('Python'), text, segment_resume(text)).status == expected


def test_blank_lines_terminate_hanging_negation():
    text = 'No experience with:\nPython\n\nDjango'
    assert fallback_assessment(req('Python'), text).status == 'not_matched'
    assert fallback_assessment(req('Django'), text).status == 'matched'


def test_source_line_preservation_prevents_fake_experience_claim():
    parts = segment_resume('Python\nPyTorch\n4 years of professional experience.')
    assert len(parts) == 3
    assert parts[0].source_lines == ('Python',)
    assert parts[-1].source_lines == ('4 years of professional experience.',)
    assert all(not ('Python' in p.text and '4 years' in p.text) for p in parts)


def test_qualifier_citations_are_physically_grounded():
    parts = segment_resume('No experience with\nPython\nDjango')
    assert any(p.text == 'No experience with Python' and
               p.source_lines == ('No experience with', 'Python') for p in parts)
    assert any(p.text == 'No experience with Django' and
               p.source_lines == ('No experience with', 'Django') for p in parts)


@pytest.mark.parametrize('text,expected', [
    ('Python\nDjango', 'matched'),
    ('Currently learning\nPython', 'uncertain'),
    ('No experience with\nPython', 'not_matched'),
])
def test_fallback_now_returns_a_real_source_segment_reference(text, expected):
    result = fallback_assessment(req('Python'), text)
    assert result.status == expected
    assert result.evidence_ids and len(result.evidence_segments) == 1
    cited = next(p for p in segment_resume(text) if p.segment_id == result.evidence_ids[0])
    assert result.evidence_segments[0].text == cited.text


@pytest.mark.parametrize('text', [
    'Requirements:\nSkills\nPython\nDjango',
    'We require\nSkills\nPython\nDjango',
    'Job description:\nTechnical Skills\nPython',
    'We require\nCurrently learning\nPython',
])
def test_copied_requirements_with_nested_headings_remain_untrusted(text):
    assert fallback_assessment(req('Python'), text).status == 'not_matched'
    assert _direct_source_guard(req('Python'), text, segment_resume(text)).status == 'not_matched'


def test_explicit_resume_section_can_restart_after_untrusted_requirements():
    text = 'Requirements:\nSkills\nPython\n\nProfessional Summary:\nI used Django.'
    assert fallback_assessment(req('Python'), text).status == 'not_matched'
    assert fallback_assessment(req('Django'), text).status == 'matched'

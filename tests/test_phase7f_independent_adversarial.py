"""Independent evidence-boundary tests; do not read Phase 7E expected labels.

These fixtures are separate from the synthetic 200-decision benchmark and
require no Ollama connection. They cover general domains and source boundaries.
"""
import pytest

from cv_ranker.assessor import _direct_source_guard
from cv_ranker.experience_validation import check_experience
from cv_ranker.fallback import fallback_assessment
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume


def requirement(name, rid='R001'):
    return ValidatedRequirement(requirement_id=rid, name=name, priority='required', jd_evidence=name)


def typed(name):
    req = requirement(name)
    return req.model_copy(update={'constraint': classify_requirement(req, 'Required experience:\n' + name)})


def status(name, text):
    return _direct_source_guard(requirement(name), text, segment_resume(text)).status


@pytest.mark.parametrize('name', [
    'Python', 'Accounts payable', 'Financial reporting', 'Vendor management',
    'Vital signs monitoring', 'Production planning', 'Customer support',
    'Ticket management', 'Microsoft Excel', 'Electronic health records',
    'Quality control', 'Payroll', 'Employee relations', 'Inventory management',
    'Preventive maintenance', 'Patient care', 'SAP', 'QuickBooks',
])
def test_short_unheaded_resume_line_is_literal_self_report(name):
    cv = f'Candidate profile for an applicant.\n\n{name}\n'
    assert status(name, cv) == 'matched'
    row = _direct_source_guard(requirement(name), cv, segment_resume(cv))
    assert row.evidence == name and len(row.evidence_ids) == 1


@pytest.mark.parametrize('text', [
    'Job requirements:\nPython\nDjango',
    'Required skills:\nPython\nDjango',
    'Position requirements:\nPython\nDjango',
    'Preferred skills:\nPython\nDjango',
    'Minimum qualifications:\nPython\nDjango',
])
def test_copied_criteria_do_not_become_candidate_skills(text):
    assert status('Python', text) != 'matched'
    assert fallback_assessment(requirement('Django'), text).status != 'matched'


def test_role_title_does_not_prove_embedded_skill():
    assert status('Machine Learning', 'Machine Learning Intern') != 'matched'
    assert status('Python', 'Python Developer') != 'matched'


@pytest.mark.parametrize('cv,name,expected', [
    ('Skills I want to learn:\nDocker', 'Docker', 'uncertain'),
    ('No experience with:\nDocker', 'Docker', 'not_matched'),
    ('Currently learning:\nKubernetes', 'Kubernetes', 'uncertain'),
    ('Currently training in quality control.', 'quality control', 'uncertain'),
    ('Preparing for Docker certification.', 'Docker', 'uncertain'),
    ('Skills:\nPython\nNo experience with Python.', 'Python', 'uncertain'),
])
def test_tone_and_cross_line_context_deny_automatic_full_credit(cv, name, expected):
    assert fallback_assessment(requirement(name), cv).status == expected


def test_source_segments_never_fabricate_a_combined_numeric_claim():
    cv = 'Python\nPyTorch\nNLP\n4 years of professional experience.'
    segments = segment_resume(cv)
    assert all('Python 4 years' not in seg.text for seg in segments)
    assert all(len(seg.source_lines) >= 1 for seg in segments)
    assert check_experience(typed('3+ years of Python experience'), cv).outcome == 'ambiguous'


@pytest.mark.parametrize('cv,outcome', [
    ('Python\n5 years of professional experience.', 'ambiguous'),
    ('Python\n5 years of Java experience.', 'not_evidenced'),
    ('5 years of Python experience.', 'sufficient'),
    ('2 years of Python experience.', 'insufficient'),
    ('6 years of Java experience.\nPython', 'not_evidenced'),
    ('Python developer with 5 years of professional experience.', 'ambiguous'),
    ('5 years of professional experience using Java; Python.', 'ambiguous'),
    ('No Python experience.', 'insufficient'),
    ('4+ years of Python experience.', 'ambiguous'),
])
def test_skill_duration_attribution_does_not_invent_tenure(cv, outcome):
    assert check_experience(typed('5+ years of Python experience'), cv).outcome == outcome


@pytest.mark.parametrize('subject,other', [
    ('HR', 'sales'), ('Production', 'retail'),
    ('Procurement', 'marketing'), ('Customer support', 'warehouse'),
])
def test_unrelated_duration_is_not_claimed_as_target_experience(subject, other):
    jd = '3+ years of ' + subject + ' experience'
    cv = f'Candidate profile for {subject} specialist.\n\n3 years of {other} experience.'
    assert check_experience(typed(jd), cv).outcome == 'not_evidenced'


def test_provenance_keeps_pdf_wraps_without_skill_year_bleed():
    source = 'Skills:\nAI/ML: TensorFlow, PyTorch, model\nevaluation\nExperience:\n2 years of Python experience.'
    parts = segment_resume(source)
    assert any(seg.text.endswith('model evaluation') and seg.source_lines ==
               ('AI/ML: TensorFlow, PyTorch, model', 'evaluation') for seg in parts)
    assert check_experience(typed('5+ years of Python experience'), source).outcome == 'insufficient'


def test_whole_line_equality_prevents_substring_profession_transfer():
    source = 'Financial reporting manager'
    assert status('Financial reporting', source) != 'matched'


def test_consistent_plain_cv_list_has_source_citations():
    cv = 'Vendor management\nPurchase orders\nInventory management\n3 years of procurement experience.'
    for term in ('Vendor management', 'Purchase orders', 'Inventory management'):
        assert status(term, cv) == 'matched'
    assert check_experience(typed('3+ years of procurement experience'), cv).outcome == 'sufficient'

@pytest.mark.parametrize('statement,outcome', [
    ('5 years of\nPython experience.', 'sufficient'),
    ('5 years of Python\nexperience.', 'sufficient'),
    ('Python\n5 years of professional experience.', 'ambiguous'),
    ('5 years of\nJava experience.\nPython', 'not_evidenced'),
])
def test_pdf_wrap_numeric_only_with_explicit_grammar(statement, outcome):
    assert check_experience(typed('5+ years of Python experience'), statement).outcome == outcome


def test_exact_initialism_is_opt_in_in_offline_mode():
    from cv_ranker.assessor import assess_resume
    cv = 'Skills:\nNLP\n'
    req = requirement('Natural Language Processing')
    old, old_mode, _ = assess_resume(resume_text=cv, requirements=[req], llm=None)
    new, new_mode, warnings = assess_resume(
        resume_text=cv, requirements=[req], llm=None, exact_initialism_guard=True)
    assert old[0].status == 'not_matched' and old_mode == 'fallback_exact'
    assert new[0].status == 'matched' and new[0].matched_term == 'NLP'
    assert new_mode == 'mixed' and warnings


def test_undocumented_abbreviation_is_never_python_autocredited():
    from cv_ranker.assessor import assess_resume
    old, _, _ = assess_resume(
        resume_text='Skills:\nGCP\n', requirements=[requirement('Google Cloud')],
        llm=None, exact_initialism_guard=True)
    assert old[0].status != 'matched'

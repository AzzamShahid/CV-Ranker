"""Requirements are typed without altering the frozen denominator or scores."""
import json

import pytest
from pydantic import ValidationError

from cv_ranker.config import Settings
from cv_ranker.pipeline import CVRanker
from cv_ranker.requirement_typing import (
    add_requirement_types, classify_requirement, enrich_ambiguous_types,
)
from cv_ranker.schemas import (
    LLMTypeProposal, LLMTypeResponse, RequirementConstraint, ValidatedRequirement,
)


def req(name, id='R001', priority='required'):
    return ValidatedRequirement(
        requirement_id=id, name=name, priority=priority, jd_evidence=name
    )


def classify(name, section='Required Skills:'):
    return classify_requirement(req(name), f'{section}\n{name}\n')


@pytest.mark.parametrize('text,expected_kind,attribute,expected_value', [
    ('Python', 'skill', 'minimum_years', None),
    ('5+ years of Python experience', 'experience', 'minimum_years', 5.0),
    ('3-5 years relevant experience in HR', 'experience', 'minimum_years', 3.0),
    ("Bachelor's degree in Computer Science", 'education', 'degree_level', 'bachelor'),
    ('Master of Science in Statistics', 'education', 'degree_level', 'master'),
    ('BS in Mechanical Engineering', 'education', 'field_of_study', 'Mechanical Engineering'),
    ('AWS certification', 'certification', 'degree_level', None),
    ('Valid professional driver license', 'license', 'minimum_years', None),
    ('Work authorization required', 'eligibility', 'degree_level', None),
    ('Manage monthly payroll', 'responsibility', 'degree_level', None),
    ('Experience building production systems', 'experience', 'minimum_years', None),
])
def test_cross_domain_types(text, expected_kind, attribute, expected_value):
    constraint = classify(text)
    assert constraint.kind == expected_kind
    assert getattr(constraint, attribute) == expected_value
    assert constraint.source_line_numbers == [2]
    assert constraint.origin == 'source_rules'


def test_subject_only_when_explicit_in_jd():
    constraint = classify('5+ years of Python experience')
    assert constraint.subject == 'Python'
    assert classify('5 years of professional experience').subject is None


def test_explicit_or_and_do_not_invent_extra_criteria():
    either = classify('TensorFlow or PyTorch')
    assert (either.kind, either.operator, either.options) == ('skill', 'any_of', ['TensorFlow', 'PyTorch'])
    both = classify('Python and Django')
    assert (both.kind, both.operator, both.options) == ('skill', 'all_of', ['Python', 'Django'])
    assert either.requires_review and both.requires_review
    assert classify('Degree in Finance or equivalent and five years experience').operator == 'complex'


def test_no_source_means_no_guessed_attributes():
    result = classify_requirement(req('5 years in Accounting'), 'Totally different JD line')
    assert result.kind == 'other' and result.minimum_years is None
    assert result.requires_review and result.source_line_numbers == []


def test_metadata_is_schema_validated():
    with pytest.raises(ValidationError, match='minimum_years may appear only'):
        RequirementConstraint(kind='skill', minimum_years=10)
    with pytest.raises(ValidationError, match='AND/OR requires'):
        RequirementConstraint(kind='skill', operator='all_of', options=['Python'])
    with pytest.raises(ValidationError, match='greater than or equal'):
        RequirementConstraint(kind='experience', minimum_years=-5)


def test_typing_never_changes_frozen_id_name_priority_or_quote():
    items = [req('Python'), req('3 years of experience', 'R002', 'preferred')]
    before = [(r.requirement_id, r.name, r.priority, r.jd_evidence) for r in items]
    result = add_requirement_types(items, 'Required Skills:\nPython\nPreferred Skills:\n3 years of experience')
    after = [(r.requirement_id, r.name, r.priority, r.jd_evidence) for r in result]
    assert before == after
    assert items[0].constraint.origin == 'unclassified'
    assert result[0].constraint.origin == 'source_rules'


def test_optional_qwen_type_is_advisory_and_does_not_invent_attributes():
    class FakeLLM:
        def invoke_structured(self, *, schema, user_prompt, system_prompt):
            assert 'R001' in user_prompt and '<QUOTE>' in user_prompt
            return LLMTypeResponse(requirements=[LLMTypeProposal(requirement_id='R001', kind='responsibility')])

    r = req('Exceptional attention to organizational priorities')
    enriched = add_requirement_types([r], r.name, llm=FakeLLM(), enable_llm=True)
    constraint = enriched[0].constraint
    assert constraint.kind == 'responsibility'
    assert constraint.origin == 'llm_suggestion' and constraint.requires_review
    assert constraint.minimum_years is None and constraint.degree_level is None


def test_qwen_invalid_id_set_fails_closed():
    class FakeLLM:
        def invoke_structured(self, *, schema, user_prompt, system_prompt):
            return LLMTypeResponse(requirements=[LLMTypeProposal(requirement_id='R999', kind='skill')])

    r = req('Exceptional attention to organizational priorities')
    enriched = add_requirement_types([r], r.name, llm=FakeLLM(), enable_llm=True)
    assert enriched[0].constraint.kind == 'other'


def test_opt_in_off_by_default():
    assert Settings().llm_type_review is False


def test_integration_source_types_do_not_change_scores(tmp_path):
    jd = tmp_path/'jd.txt'
    jd.write_text('Required Skills:\nPython\n3+ years of Python experience\nTensorFlow or PyTorch\n', encoding='utf-8')
    cv = tmp_path/'cv.txt'
    cv.write_text('Skills:\nPython\nPyTorch\nExperience:\n5 years of Python experience.\n', encoding='utf-8')
    report = CVRanker(Settings(), use_llm=False).run(jd, [cv])
    assert [r.constraint.kind for r in report.requirements] == ['skill','experience','skill']
    assert [r.constraint.minimum_years for r in report.requirements] == [None,3.0,None]
    assert report.candidates[0].total_required == 3
    assert report.candidates[0].required_score is not None
    assert report.jd_diagnostics[-1]['stage'] == 'final_denominator'
    saved = json.loads(report.model_dump_json())
    assert saved['requirements'][1]['constraint']['minimum_years'] == 3.0


def test_multi_department_end_to_end(tmp_path):
    for label, jd_lines in {
        'hr': 'Required Skills:\nManage employee onboarding\n3 years relevant experience in HR\n',
        'finance': 'Required Qualifications:\nBachelor\'s degree in Accounting\nPrepare monthly financial statements\n',
        'manufacturing': 'Required Skills:\nValid forklift license\nMachine maintenance\n',
    }.items():
        jd = tmp_path/(label+'_jd.txt')
        cv = tmp_path/(label+'_resume.txt')
        jd.write_text(jd_lines, encoding='utf-8')
        cv.write_text('Skills:\nOperations\nProject delivery\n', encoding='utf-8')
        report = CVRanker(Settings(), use_llm=False).run(jd, [cv])
        assert report.requirements
        assert all(r.constraint.kind != 'unclassified' for r in report.requirements)
        assert all(r.constraint.source_line_numbers for r in report.requirements)


def test_eligibility_and_licensing_require_human_review():
    assert classify('Work authorization required').requires_review
    assert classify('Valid nursing license').requires_review

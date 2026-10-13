"""Reviewer-approved aliases are explicit user policy, not an LLM-inferred dictionary."""
import json

import pytest

from cv_ranker.alias_approvals import AliasApproval, apply_reviewed_aliases, load_approved_aliases
from cv_ranker.schemas import RequirementAssessment, ValidatedRequirement
from cv_ranker.config import Settings
from cv_ranker.pipeline import CVRanker


def req(name='Google Cloud', id='R003'):
    return ValidatedRequirement(requirement_id=id, name=name, priority='required', jd_evidence=name)


def prior(id='R003'):
    return RequirementAssessment(requirement_id=id, status='not_matched')


def approval(name='Google Cloud', alias='GCP'):
    return AliasApproval(requirement=name, alias=alias, approved_by='HR reviewer',
                         reason='Reviewed as an acceptable same-platform name for this particular JD')


def use(resume, entries=None):
    return apply_reviewed_aliases(requirements=[req()], assessments=[prior()],
                                  resume_text=resume, approvals=[approval()] if entries is None else entries)


def approval_file(tmp_path, entries):
    p=tmp_path / 'reviewed.json'
    p.write_text(json.dumps({'schema_version': 1, 'approvals': entries}), encoding='utf-8')
    return p


def test_no_file_means_no_mapping_and_no_behavior_change():
    assert load_approved_aliases(None, [req()]) == ([], None)
    result, warnings, changed = use('Skills:\nGCP\n', entries=[])
    assert result[0].status == 'not_matched' and not warnings and not changed


def test_approval_must_reference_exact_frozen_requirement(tmp_path):
    path=approval_file(tmp_path,[approval(name='Django').model_dump()])
    with pytest.raises(ValueError, match='missing/changed JD'):
        load_approved_aliases(path,[req()])


def test_reviewer_alias_provides_full_source_ids_and_authorization():
    output, notes, changed = use('Skills:\nGCP\n')
    match=output[0]
    assert match.status == 'matched' and match.matched_term == 'GCP'
    assert match.evidence_ids == ['S001'] and match.evidence_segments[0].text == 'GCP'
    assert match.reviewed_alias_by == 'HR reviewer' and changed
    assert 'NOT a Qwen-only' in notes[0]


def test_approval_file_is_validated_and_hash_recorded(tmp_path):
    path=approval_file(tmp_path,[approval().model_dump()])
    items, fingerprint=load_approved_aliases(path,[req()])
    assert items == [approval()] and len(fingerprint)==64


def test_negative_only_cannot_be_credit():
    output, notes, changed=use('Experience:\nNo experience with GCP.\n')
    assert output[0].status == 'not_matched' and not notes and not changed


def test_learning_only_is_uncertain_zero_credit():
    output, _, changed=use('Skills:\nCurrently learning GCP\n')
    assert output[0].status == 'uncertain' and changed


def test_contradiction_between_positive_and_negative_alias_is_uncertain():
    output, _, changed=use('Skills:\nGCP\nExperience:\nNo experience with GCP\n')
    assert output[0].status == 'uncertain' and changed


def test_original_requirement_negated_elsewhere_blocks_full_credit():
    output, _, changed=use('Skills:\nGCP\nExperience:\nNo Google Cloud experience.\n')
    assert output[0].status == 'uncertain' and changed


def test_title_and_education_only_do_not_grant_proficiency():
    output, notes, changed=use('Education:\nGCP Certification, 2025.\n')
    assert output[0].status == 'not_matched' and not changed and not notes


def test_alias_cannot_fabricate_unquoted_source_term():
    output, notes, changed=use('Skills:\nAWS\n')
    assert output[0].status == 'not_matched' and not changed and not notes


def test_no_implicit_mapping_without_reviewer_even_for_nlp():
    results, _, changed = apply_reviewed_aliases(requirements=[req('Natural Language Processing')],
            assessments=[prior()], resume_text='Skills:\nNLP\n', approvals=[])
    assert not changed and results[0].status == 'not_matched'


def test_alias_assigned_to_two_different_requirements_is_rejected(tmp_path):
    p=approval_file(tmp_path,[approval().model_dump(),approval(name='Google Cloud Platform').model_dump()])
    with pytest.raises(ValueError, match='Ambiguous alias'):
        load_approved_aliases(p,[req(),req('Google Cloud Platform','R004')])


def test_approval_requires_reviewer_and_reason(tmp_path):
    bad=approval().model_dump();bad['approved_by']='';bad['reason']=''
    p=approval_file(tmp_path,[bad])
    with pytest.raises(ValueError, match='Invalid approved-equivalence'):
        load_approved_aliases(p,[req()])


def test_aliases_are_off_by_default_in_settings():
    assert Settings().approved_aliases_path is None


def test_no_new_cv_scoring_math_or_invented_requirements(tmp_path):
    p=approval_file(tmp_path,[approval().model_dump()])
    # This test uses the existing no-LLM pipeline to prove exact integration;
    # it does not claim the Qwen model itself produced the equivalence.
    jd=tmp_path/'jd.txt'; jd.write_text('Required Skills:\nGoogle Cloud\n', encoding='utf-8')
    cv=tmp_path/'resume.txt'; cv.write_text('Skills:\nGCP\nAn experienced administrator.\n', encoding='utf-8')
    report=CVRanker(settings=Settings(approved_aliases_path=str(p)),use_llm=False).run(jd,[cv])
    assert any(a.alias == 'GCP' for a in [approval()])
    assert report.approved_aliases_sha256
    assert report.approved_aliases[0]['approved_by']=='HR reviewer'
    assert any('reviewer-approved alias' in err for err in report.candidates[0].errors) or any('reviewer-approved' in x for x in report.warnings)


def test_reviewer_cannot_bypass_numeric_experience_requirement(tmp_path):
    p=approval_file(tmp_path,[approval(name='5+ years Python experience',alias='Python').model_dump()])
    with pytest.raises(ValueError, match='restricted to short named requirements'):
        load_approved_aliases(p,[req('5+ years Python experience')])


def test_reviewer_cannot_substitute_unrelated_qualification(tmp_path):
    p=approval_file(tmp_path,[approval(name="Bachelor's degree in Computer Science",alias='AWS').model_dump()])
    with pytest.raises(ValueError, match='restricted to short named requirements'):
        load_approved_aliases(p,[req("Bachelor's degree in Computer Science")])

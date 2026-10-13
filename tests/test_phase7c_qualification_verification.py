"""Phase 7C: literal qualification claim checks, adverse examples and pipeline."""
import json
from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.pipeline import CVRanker
from cv_ranker.qualification_validation import check_qualification, apply_qualification_checks
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import RequirementAssessment, ValidatedRequirement
from cv_ranker.segments import segment_resume


def req(name, req_id='R001'):
    original = ValidatedRequirement(requirement_id=req_id, name=name,
                                    priority='required', jd_evidence=name)
    return original.model_copy(update={
        'constraint': classify_requirement(original, 'Required Qualifications:\n' + name)})


def outcome(jd, cv):
    return check_qualification(req(jd), cv).outcome


@pytest.mark.parametrize('source,expected', [
    ('Education:\nBSc Computer Science, FAST NUCES.', 'satisfied'),
    ('Education:\nBachelor of Science in Computer Science.', 'satisfied'),
    ('Education:\nB.S. in Computer Science, graduated 2023.', 'satisfied'),
    ('Education:\nBS CS.', 'satisfied'),
    ('Education:\nBS Computer Science.\nExperience:\n4 years in analytics.', 'satisfied'),
    ('Education:\nBSc Chemistry.', 'mismatch'),
    ('Education:\nBachelor in Chemistry.', 'mismatch'),
    ('Education:\nMaster of Science in Computer Science.', 'ambiguous'),
    ('Education:\nPursuing BSc Computer Science.', 'ambiguous'),
    ('Education:\nBachelor in Computer Science, expected to graduate in 2027.', 'ambiguous'),
    ('Education:\nDid not complete BSc Computer Science.', 'mismatch'),
    ('Education:\nBachelor in Computer Science.\nBachelor in Computer Science in progress.', 'ambiguous'),
    ('Education:\nBachelor degree (unspecified field).', 'ambiguous'),
    ('Skills:\nPython\nSQL.', 'not_evidenced'),
    ('Skills:\nMS Excel', 'not_evidenced'),
])
def test_degree_field_and_completion(source, expected):
    assert outcome("Bachelor's degree in Computer Science", source) == expected


@pytest.mark.parametrize('jd,source,expected', [
    ('AWS certification', 'Certifications:\nAWS Certified Cloud Practitioner', 'satisfied'),
    ('AWS certification', 'Certifications:\nAWS Certification', 'satisfied'),
    ('AWS certification', 'Skills:\nAWS', 'not_evidenced'),
    ('AWS certification', 'Certifications:\nPreparing for AWS Certified Cloud Practitioner', 'ambiguous'),
    ('AWS certification', 'Certifications:\nNot yet certified in AWS', 'ambiguous'),
    ('AWS certification', 'Training:\nAWS certification program', 'ambiguous'),
    ('AWS certification', 'Certifications:\nNo AWS certification', 'mismatch'),
    ('AWS certification', 'Certifications:\nI will earn AWS certification next year', 'ambiguous'),
    ('AWS certification', 'Certifications:\nAWS certification required for this job', 'not_evidenced'),
    ('AWS certification', 'Certifications:\nExpired AWS certification', 'mismatch'),
    ('AWS certification', 'Certifications:\nAzure Certified Fundamentals', 'mismatch'),
    ('AWS Certified Cloud Practitioner', 'Certifications:\nAWS Certified Cloud Practitioner', 'satisfied'),
    ('AWS Certified Cloud Practitioner', 'Certifications:\nAWS Certified DevOps Engineer', 'mismatch'),
    ('AWS Certified Cloud Practitioner', 'Certifications:\nAWS Certified Cloud Practitioner (expired)', 'mismatch'),
    ('AWS Certified Cloud Practitioner', 'Certifications:\nAWS Certified Cloud Practitioner\nAWS Certified Cloud Practitioner expired', 'ambiguous'),
    ('CCNA certification', 'Certifications:\nCCNA - earned 2023', 'satisfied'),
    ('CCNA certification', 'Skills:\nCCNA', 'not_evidenced'),
])
def test_certification_identity_and_safety(jd, source, expected):
    assert outcome(jd, source) == expected


@pytest.mark.parametrize('source,expected', [
    ('Licenses:\nActive valid nursing license', 'satisfied'),
    ('Licenses:\nNursing license', 'ambiguous'),
    ('Licenses:\nExpired nursing license', 'mismatch'),
    ('Licenses:\nNursing license pending application', 'ambiguous'),
    ('Licenses:\nActive nursing license (expires 2027)', 'ambiguous'),
    ('Profile:\nLicensed Nurse', 'not_evidenced'),
    ('Licenses:\nValid driving license', 'mismatch'),
    ('Licenses:\nActive nursing license\nExpired nursing license', 'ambiguous'),
    ('Licenses:\nNo nursing license', 'mismatch'),
    ('Licenses:\nNot valid nursing license', 'mismatch'),
    ('Licenses:\nNursing license no longer active', 'mismatch'),
    ('Licenses:\nValid nursing license required for this job', 'not_evidenced'),
    ('Experience:\nNursing shifts and duties', 'not_evidenced'),
])
def test_license_scope_and_validity(source, expected):
    assert outcome('Valid nursing license', source) == expected


def test_no_qualification_gate_for_non_credential_types():
    assert check_qualification(req('Python'), 'Skills:\nPython') is None


def test_metadata_does_not_invent_credential_attribute():
    assert outcome('Degree', 'Education:\nBSc Chemistry') == 'ambiguous'
    assert outcome('Certification', 'Certifications:\nAWS Certified Cloud Practitioner') == 'ambiguous'


def test_source_quote_and_id_are_from_resume():
    jd = req("Bachelor's degree in Computer Science")
    source = 'Education:\nBSc Computer Science, FAST NUCES.'
    old = [RequirementAssessment(requirement_id='R001', status='not_matched')]
    rows, notes, changed = apply_qualification_checks(
        requirements=[jd], assessments=old, resume_text=source)
    row = rows[0]
    assert changed and row.status == 'matched'
    assert row.qualification_check.outcome == 'satisfied'
    assert not row.qualification_check.independently_verified
    assert row.evidence_ids == ['S001']
    assert row.evidence == segment_resume(source)[0].text
    assert row.evidence_segments[0].text == row.evidence
    assert 'not_matched -> matched' in notes[0]


def test_partial_degree_cannot_keep_llm_matched():
    original = [RequirementAssessment(requirement_id='R001', status='matched',
                                      evidence='Bachelor in Computer Science')]
    rows, notes, changed = apply_qualification_checks(
        requirements=[req("Bachelor's degree in Computer Science")],
        assessments=original,
        resume_text="Education:\nCurrently pursuing Bachelor's in Computer Science")
    assert changed and rows[0].status == 'uncertain'
    assert rows[0].qualification_check.changed_status
    assert rows[0].evidence_ids == ['S001']


def test_missing_certificate_cannot_keep_fabricated_model_match():
    rows, _, changed = apply_qualification_checks(
        requirements=[req('AWS certification')],
        assessments=[RequirementAssessment(requirement_id='R001', status='matched',
                                           evidence_ids=['S999'], evidence='AWS certified')],
        resume_text='Skills:\nAWS')
    assert changed and rows[0].status == 'uncertain'
    assert rows[0].evidence is None and rows[0].evidence_ids == []


def test_no_unrelated_credentials_as_evidence():
    rows, _, changed = apply_qualification_checks(
        requirements=[req('AWS certification')],
        assessments=[RequirementAssessment(requirement_id='R001', status='matched',
                                           evidence_ids=['S999'], evidence='AWS certified')],
        resume_text='Certifications:\nAzure Certified Fundamentals')
    assert changed and rows[0].status == 'not_matched'
    assert rows[0].evidence_ids == ['S001']
    assert 'Azure' in rows[0].evidence


def test_json_report_and_candidate_ranking_no_llm(tmp_path):
    jd = tmp_path/'jd.txt'
    jd.write_text("Required Skills:\nBachelor's degree in Computer Science\nAWS certification\n", encoding='utf-8')
    res = tmp_path/'resumes'
    res.mkdir()
    (res/'01_qualified.txt').write_text('Education:\nBSc Computer Science\nCertifications:\nAWS Certified Cloud Practitioner', encoding='utf-8')
    (res/'02_studying.txt').write_text('Education:\nCurrently pursuing BSc Computer Science\nCertifications:\nPlanning to earn AWS certification', encoding='utf-8')
    (res/'03_different.txt').write_text('Education:\nBSc Chemistry\nCertifications:\nAzure Certified Fundamentals', encoding='utf-8')
    report = CVRanker(settings=Settings(), use_llm=False).run(jd, sorted(res.iterdir()))
    assert len(report.requirements) == 2
    by = {c.candidate_name: c for c in report.candidates}
    assert by['01_qualified.txt'].primary_score == 100.0
    assert by['02_studying.txt'].primary_score == 0.0
    assert by['03_different.txt'].primary_score == 0.0
    assert by['01_qualified.txt'].assessments[0].qualification_check.outcome == 'satisfied'
    assert by['02_studying.txt'].assessments[0].qualification_check.outcome == 'ambiguous'
    assert by['03_different.txt'].assessments[0].qualification_check.outcome == 'mismatch'
    serial = json.dumps(report.model_dump())
    assert 'qualification_check' in serial and 'independently_verified' in serial


def test_mixed_mode_when_python_corrects_model_status():
    rows, _, changed = apply_qualification_checks(
        requirements=[req('AWS certification')],
        assessments=[RequirementAssessment(requirement_id='R001', status='not_matched')],
        resume_text='Certifications:\nAWS Certified Cloud Practitioner')
    assert changed and rows[0].status == 'matched'

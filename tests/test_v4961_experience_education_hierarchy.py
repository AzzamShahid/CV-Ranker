"""Cross-domain, source-grounded higher-degree and dated-career summary regressions."""

import pytest
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.qualification_validation import apply_qualification_checks, check_qualification
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.segments import segment_resume


def req(jd, rid='R001'):
    original = ValidatedRequirement(requirement_id=rid, name=jd,
                                    priority='required', jd_evidence=jd)
    return original.model_copy(update={'constraint': classify_requirement(
        original, 'Required Qualifications:\n' + jd)})


def cited_model_row(rid, cv, snippets, status='matched'):
    segments = segment_resume(cv)
    sources = [s for s in segments if any(snippet in s.text for snippet in snippets)]
    assert len(sources) == len(snippets), [(s.segment_id, s.text) for s in segments]
    return RequirementAssessment(
        requirement_id=rid, status=status,
        unified_status='Found' if status == 'matched' else 'Not Found',
        reason='Model found source-supported experience.',
        evidence_ids=[s.segment_id for s in sources],
        evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                             section=s.section, text=s.text) for s in sources],
    )


@pytest.mark.parametrize('subject,summary,role,duty', [
    ('textile weaving production',
     'Weaving floor in-charge with 8 years 1 month of full-time air-jet and rapier loom production experience.',
     'Weaving Floor In-Charge', 'Supervised weaving production, shift output, loom operations and defects.'),
    ('hospital quality assurance',
     'Quality supervisor with 8 years 1 month of full-time hospital quality assurance operations experience.',
     'Hospital Quality Supervisor', 'Performed hospital quality assurance audits and delivered reports.'),
    ('financial reporting',
     'Finance team lead with 8 years 1 month of full-time financial reporting and accounting operations experience.',
     'Financial Reporting Lead', 'Managed financial reporting, accounting controls, and ledger reviews.'),
])
def test_cited_summary_and_dated_role_qualify_without_explicit_duty_citation(subject, summary, role, duty):
    jd = f'Minimum 3 years of full-time professional experience in {subject}.'
    cv = (f'Professional Summary\n{summary}\nExperience\n'
          f'{role} | Example Group | Sep 2018 - Present\n- {duty}')
    r = req(jd)
    row = cited_model_row('R001', cv, ['8 years 1 month', 'Sep 2018 - Present'])
    result, _, _ = apply_experience_checks(requirements=[r], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[r], assessments=result)[0]
    assert final.status == 'matched', final.model_dump()
    assert final.unified_status == 'Found'
    assert final.evidence_ids  # dates, summary, duties from the original ledger
    assert 'HR verification' in final.reason or 'independently' in final.reason


def test_full_time_cannot_be_inferred_from_dated_role_without_full_time_assertion():
    jd = 'Minimum 3 years of full-time professional experience in quality assurance.'
    cv = ('Experience\nQuality Analyst | Example Group | Jan 2020 - Oct 2026\n'
          '- Performed quality assurance audits for releases.')
    r = req(jd)
    row = cited_model_row('R001', cv, ['Jan 2020 - Oct 2026', 'Performed quality'])
    checked, _, _ = apply_experience_checks(requirements=[r], assessments=[row], resume_text=cv)
    assert checked[0].status != 'matched'


def test_summary_cannot_substitute_unrelated_dated_role():
    jd = 'Minimum 3 years of full-time professional experience in quality assurance.'
    cv = ('Professional Summary\nQuality assurance specialist with 8 years 1 month of full-time quality assurance experience.\n'
          'Experience\nRetail Sales Officer | Group | Sep 2018 - Present\n'
          '- Managed retail inventory and customer queries.')
    r = req(jd)
    row = cited_model_row('R001', cv, ['8 years 1 month', 'Sep 2018 - Present'])
    checked, _, _ = apply_experience_checks(requirements=[r], assessments=[row], resume_text=cv)
    assert checked[0].status != 'matched'


def test_short_dated_role_cannot_support_long_summary():
    jd = 'Minimum 3 years of full-time professional experience in quality assurance.'
    cv = ('Professional Summary\nQuality assurance lead with 8 years 1 month of full-time quality assurance experience.\n'
          'Experience\nQA Lead | Group | Jan 2025 - Oct 2026\n'
          '- Performed quality assurance audits.')
    r = req(jd)
    row = cited_model_row('R001', cv, ['8 years 1 month', 'Jan 2025 - Oct 2026'])
    checked, _, _ = apply_experience_checks(requirements=[r], assessments=[row], resume_text=cv)
    assert checked[0].status != 'matched'


def test_no_experience_claim_from_copied_jd():
    jd = 'Minimum 3 years of full-time professional experience in textile weaving production.'
    cv = ('Job Requirements\nCandidates must have 8 years of full-time textile weaving production experience.\n'
          'Experience\nWarehouse Operative | Group | Jan 2020 - Oct 2026\n'
          '- Coordinated shipments and managed inventory.')
    assert check_experience(req(jd), cv).outcome != 'sufficient'


@pytest.mark.parametrize('jd,degree', [
    ("Bachelor's degree in Computer Science", 'Master of Science in Computer Science, completed 2024.'),
    ("Bachelor's degree in Textile Engineering", 'MSc Textile Engineering, University of Example, 2023.'),
    ("Bachelor's degree in Accounting", "Master's degree in Accounting, awarded 2025."),
    ("Master's degree in Computer Science", 'PhD in Computer Science, University of Example, 2024.'),
])
def test_completed_higher_same_field_meets_minimum_academic_level(jd, degree):
    r = req(jd)
    cv = 'Education\n' + degree
    assert check_qualification(r, cv).outcome == 'satisfied'
    before = RequirementAssessment(requirement_id='R001', status='not_matched',
                                   unified_status='Not Found', reason='Lower level missing')
    rows, _, _ = apply_qualification_checks(requirements=[r], assessments=[before], resume_text=cv)
    final = reconcile_final_assessments(requirements=[r], assessments=rows)[0]
    assert final.status == 'matched'
    assert final.unified_status == 'Found'
    assert final.evidence_ids
    assert 'master' in final.reason.lower() or 'doctorate' in final.reason.lower()


@pytest.mark.parametrize('jd,degree,expected', [
    ("Bachelor's degree in Computer Science", 'Master of Science in Chemistry, awarded 2024.', 'mismatch'),
    ("Bachelor's degree in Computer Science", 'Pursuing MSc Computer Science, expected 2027.', 'ambiguous'),
    ("Master's degree in Computer Science", 'BSc Computer Science, graduated 2024.', 'mismatch'),
    ("Bachelor's degree in Computer Science", 'MBA, University of Example, 2024.', 'mismatch'),
])
def test_higher_level_does_not_remove_completion_or_field_constraints(jd, degree, expected):
    assert check_qualification(req(jd), 'Education\n' + degree).outcome == expected


def test_bachelor_and_master_independent_conditions_not_waived():
    jd = "Bachelor's degree in Computer Science and Master's degree in Computer Science"
    r = req(jd)
    # Explicit separate AND requires both credential claims, not only a master's.
    cv = 'Education\nMaster of Science in Computer Science, graduated 2024.'
    assert check_qualification(r, cv).outcome != 'satisfied'


def test_explicit_bachelor_identity_not_inferred_from_master():
    jd = "Exactly a Bachelor's degree in Computer Science is required for accreditation."
    r = req(jd)
    assert check_qualification(r, 'Education\nMaster of Science in Computer Science.').outcome != 'satisfied'


def test_numeric_scope_claim_without_full_time_does_not_meet_full_time_minimum():
    jd = 'Minimum 3 years of full-time professional experience in quality assurance.'
    r = req(jd)
    cv = 'Experience\n6 years of quality assurance experience.'
    checked = check_experience(r, cv)
    assert checked.outcome == 'ambiguous'
    row = cited_model_row('R001', cv, ['6 years of quality assurance'])
    rows, _, _ = apply_experience_checks(requirements=[r], assessments=[row], resume_text=cv)
    assert rows[0].status != 'matched'


def test_numeric_scope_claim_with_full_time_meets_full_time_minimum():
    jd = 'Minimum 3 years of full-time professional experience in quality assurance.'
    r = req(jd)
    cv = 'Experience\n6 years of full-time quality assurance experience.'
    assert check_experience(r, cv).outcome == 'sufficient'

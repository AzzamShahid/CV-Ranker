"""Representative computing disciplines exercise generic JD/degree parsing.

These are deterministic source-validation tests, NOT a claim that every
possible future model response can be correct. Production still uses the
frozen JD and original CV evidence to decide semantic equivalence.
"""

import pytest

from cv_ranker.qualification_validation import check_qualification
from cv_ranker.requirement_typing import add_requirement_types
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import UnifiedItem, UnifiedResponse, _map_response


def _req(name, rid='R001'):
    return add_requirement_types([ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority='required',
    )], name)[0]


@pytest.mark.parametrize('discipline', [
    'Computer Science', 'Software Engineering', 'Information Technology',
    'Information Systems', 'Data Science', 'Cybersecurity',
    'Computer Engineering', 'Artificial Intelligence',
    'Computational Biology', 'Human-Computer Interaction',
    'Robotics', 'Bioinformatics',
])
def test_exact_academic_field_retains_its_own_meaning(discipline):
    jd = f"Completed Bachelor's degree in {discipline}."
    outcome = check_qualification(
        _req(jd), f'Education\nBS {discipline}, Example University, 2022')
    assert outcome.outcome == 'satisfied', (discipline, outcome)


@pytest.mark.parametrize('jd,credential', [
    ("Completed Bachelor's degree in Computer Science or Software Engineering.",
     'BS Software Engineering'),
    ("Completed Bachelor's degree in Data Science or Statistics.",
     'BS Statistics'),
    ("Completed Bachelor's degree in Electrical Engineering or Computer Engineering.",
     'BS Computer Engineering'),
])
def test_inclusive_degree_alternatives_are_derived_from_jd(jd, credential):
    assert check_qualification(
        _req(jd), f'Education\n{credential}, Example University, 2022',
    ).outcome == 'satisfied'


@pytest.mark.parametrize('specialty,action', [
    ('Build pipeline maintenance', 'Maintained build pipelines for staged releases.'),
    ('Full-stack API integration', 'Integrated browser workflows with server APIs.'),
    ('Distributed observability', 'Implemented distributed telemetry and alerting.'),
    ('Mobile accessibility audits', 'Performed mobile accessibility audits.'),
    ('Embedded firmware testing', 'Tested embedded device firmware.'),
    ('Database query tuning', 'Optimized database queries under production load.'),
    ('Secure code review', 'Reviewed security issues in application source code.'),
    ('Model drift monitoring', 'Monitored model drift for scheduled ML pipelines.'),
    ('Compiler optimization', 'Implemented compiler optimization passes.'),
    ('Simulation software verification', 'Verified simulation software against reference data.'),
    ('Cloud infrastructure reliability', 'Maintained cloud infrastructure reliability.'),
    ('User experience research', 'Conducted user experience research.'),
])
def test_live_response_schema_accepts_arbitrary_software_specialties(specialty, action):
    # A genuinely sourced model finding must survive the transport validator.
    # Semantic truth is still separately verified by the real engine.
    requirement = _req(specialty)
    segment = ResumeSegment('S001', 'experience', action)
    response = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id='R001', decision='found', relation='entailed',
        evidence_ids=[segment.segment_id],
        reason=f'The CV reports completed work: {action}',
    )])
    mapped, proposed, rejected = _map_response(response, [requirement], {'S001'})
    assert rejected == set()
    assert mapped.assessments[0].evidence_ids == ['S001']
    assert proposed['R001'].decision == 'found'


def test_named_tool_absence_is_not_overridden_by_loosely_related_work():
    req = _req('Experience using a specific employer-named tool')
    row = UnifiedItem(
        requirement_id=req.requirement_id,
        decision='transferable', relation='overlap', evidence_ids=['S001'],
        reason='The applicant completed related work with a distinct tool.',
    )
    _, proposed, invalid = _map_response(
        UnifiedResponse(assessments=[row]), [req], {'S001'})
    assert not invalid
    assert proposed[req.requirement_id].decision == 'transferable'

"""Cross-check official supervisor Found against the actual candidate ledger."""
from __future__ import annotations
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import (ValidatedRequirement,RequirementAssessment,EvidenceCitation)
from cv_ranker.segments import ResumeSegment


def make():
    r=ValidatedRequirement(requirement_id='R001',name='Verify damaged stock',
                            jd_evidence='Verify damaged stock',priority='required')
    s=ResumeSegment('S001','experience','Verified damaged stock and submitted the log.')
    row=RequirementAssessment(requirement_id='R001',status='matched',
            unified_status='Found',assessment_state='verified',evidence_ids=['S001'],
            evidence_segments=[EvidenceCitation(segment_id='S001',section='experience',text=s.text)])
    return r,s,row


def test_genuine_original_source_retains_verified_direct_and_is_idempotent():
    r,s,row=make()
    first=reconcile_final_assessments(requirements=[r],assessments=[row],source_segments=[s])
    second=reconcile_final_assessments(requirements=[r],assessments=first,source_segments=[s])
    assert first[0].unified_status=='Found'
    assert first[0].model_dump()==second[0].model_dump()


def test_forged_or_foreign_source_can_never_become_verified_found():
    r,s,row=make()
    for forged in [row.model_copy(update={'evidence_ids':['S999']}),
                   row.model_copy(update={'evidence_ids':[]}),
                   row.model_copy(update={'evidence_segments':[EvidenceCitation(
                       segment_id='S001',section='experience',text='Invented complete task.')]})]:
        result=reconcile_final_assessments(requirements=[r],assessments=[forged],source_segments=[s])[0]
        assert result.unified_status is None and result.assessment_state=='unverified'
        assert result.current_decision.verdict is None
        assert result.current_decision.failure.code == 'source_identity_invalid'
        assert result.decision_trace[-1].reason_code=='original_source_identity_incomplete'


def test_one_rejected_positive_does_not_change_verified_sibling():
    r,s,row=make()
    other=r.model_copy(update={'requirement_id':'R002'})
    failed=row.model_copy(update={'requirement_id':'R002','evidence_ids':['S999']})
    values=reconcile_final_assessments(requirements=[r,other],assessments=[row,failed],source_segments=[s])
    assert [x.unified_status for x in values]==['Found',None]
    assert values[1].current_decision.failure.code=='source_identity_invalid'
    assert values[0].current_decision.verdict=='Found'


def test_unreviewed_compound_cannot_hide_unsatisfied_jd_clause_in_two_facets():
    from cv_ranker.condition_review import ReviewedFacet,_facets_cover_unreviewed_jd
    jd='Inspect damaged stock and document corrective actions within five days.'
    incomplete=[ReviewedFacet(jd_exact_span='Inspect damaged stock',relation='satisfied',
                  source_ids=['S001'],explanation='Inspection is described.'),
                ReviewedFacet(jd_exact_span='document corrective actions',relation='satisfied',
                  source_ids=['S001'],explanation='Actions are documented.')]
    assert not _facets_cover_unreviewed_jd(jd,incomplete)
    complete=incomplete+[ReviewedFacet(jd_exact_span='within five days',relation='satisfied',
                            source_ids=['S001'],explanation='The report includes the required deadline.')]
    assert _facets_cover_unreviewed_jd(jd,complete)

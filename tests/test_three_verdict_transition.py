"""Three-verdict migration: local, deterministic policy and scoring guards.

All examples are fictional. These tests prove structured contract behavior,
not that a production LLM has improved semantic accuracy.
"""
import pytest
from pydantic import ValidationError

from cv_ranker.decision_contract import DecisionRecord, completed, incomplete
from cv_ranker.schemas import (RequirementAssessment, ValidatedRequirement,
                               EvidenceCitation)
from cv_ranker.scoring import score_candidate
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (_keyed_response_schema, _independent_response_schema,
                               UNIFIED_PROMPT)
from cv_ranker.condition_review import ConditionReviewItem
from cv_ranker.ui.final_decisions import FocusedJudgment


def req(rid, name):
    return ValidatedRequirement(requirement_id=rid, name=name,
        jd_evidence=name, priority='required')


def row(rid, status, verdict, citations=(), *, state='verified'):
    return RequirementAssessment(requirement_id=rid, status=status,
        unified_status=verdict, assessment_state=state,
        evidence_ids=[c.segment_id for c in citations],
        evidence_segments=[EvidenceCitation(segment_id=c.segment_id,
            section=c.section, text=c.text) for c in citations],
        reason='Fictional source-backed assessment')


def test_contract_rejects_completed_without_one_exact_verdict():
    for kwargs in [
        dict(processing_state='completed', verdict=None),
        dict(processing_state='completed', verdict='Unverified'),
        dict(processing_state='completed', verdict='uncertain'),
        dict(processing_state='failed', verdict='Not Found'),
    ]:
        with pytest.raises(ValidationError):
            DecisionRecord(**kwargs)
    for verdict in ('Found','Transferable','Not Found'):
        assert completed(verdict).verdict == verdict


def test_failed_operation_preserves_null_verdict_and_structured_cause():
    state = incomplete('response_schema_invalid',stage='model_validation',
        detail='Synthetic JSON failed an output contract')
    assert state.verdict is None and state.processing_state == 'failed'
    assert state.failure.code == 'response_schema_invalid'
    with pytest.raises(ValidationError):
        DecisionRecord.model_validate({**state.model_dump(), 'verdict': 'Not Found'})


def test_live_candidate_model_contracts_do_not_offer_abstention():
    schema = _keyed_response_schema(('R001',), strict_relation=True)
    for model_schema in (schema, _independent_response_schema(('R001',))):
        prop = 'R001'
        body = dict(decision='uncertain', relation='uncertain', evidence_ids=[],
                    reason='There are mixed facts in the fictional source',
                    proof_excerpt=None)
        with pytest.raises(ValidationError):
            model_schema.model_validate({prop:body})
    with pytest.raises(ValidationError):
        ConditionReviewItem(requirement_id='R001',decision='uncertain',
            reason='An obsolete four-way verdict is rejected')
    with pytest.raises(ValidationError):
        FocusedJudgment(result='uncertain',explanation='A fourth final model option')
    assert 'no uncertain or unverified final choice' in UNIFIED_PROMPT.casefold()


def test_source_bound_positive_finalizes_found_once():
    r=req('R001','Maintain shipment records')
    source=ResumeSegment('S001','experience','Maintained shipment records and reconciled manifests.')
    item=row('R001','matched','Found',[source])
    one=reconcile_final_assessments(requirements=[r],assessments=[item],source_segments=[source])[0]
    two=reconcile_final_assessments(requirements=[r],assessments=[one],source_segments=[source])[0]
    assert one.current_decision == completed('Found',item.reason)
    assert two.current_decision == one.current_decision
    assert two.decision_trace == one.decision_trace


def test_negative_with_no_positive_citation_is_valid_zero():
    r=req('R001','Professional warehouse management experience')
    result=reconcile_final_assessments(requirements=[r],
        assessments=[row('R001','not_matched','Not Found')],source_segments=[])
    assert result[0].current_decision.verdict == 'Not Found'
    candidate=score_candidate(candidate_name='Fictional Person', requirements=[r],
        assessments=result, evaluation_mode='llm_assessed', errors=[])
    assert candidate.primary_score == 0.0 and candidate.matched_primary == 0


def test_missing_original_positive_source_blocks_score_without_negative():
    r=req('R001','Maintain shipment records')
    claim=ResumeSegment('S001','experience','Maintained shipment records.')
    changed=ResumeSegment('S001','experience','Observed loading from a distance.')
    assessment=row('R001','matched','Found',[claim])
    result=reconcile_final_assessments(requirements=[r],
        assessments=[assessment],source_segments=[changed])
    current=result[0].current_decision
    assert current.verdict is None
    assert current.failure.code == 'source_identity_invalid'
    candidate=score_candidate(candidate_name='Fictional Person',requirements=[r],
        assessments=result,evaluation_mode='llm_assessed',errors=[])
    assert candidate.primary_score is None


def test_provisional_sibling_does_not_erase_completed_match():
    r1,r2=req('R001','Python'),req('R002','Supervise spinning machinery')
    s=ResumeSegment('S001','skills','Python')
    a=row('R001','matched','Found',[s])
    b=row('R002','uncertain',None,state='unverified')
    merged=reconcile_final_assessments(requirements=[r1,r2],assessments=[a,b],source_segments=[s])
    assert merged[0].current_decision.verdict == 'Found'
    assert merged[1].current_decision.verdict is None
    scored=score_candidate(candidate_name='Fictional Person',requirements=[r1,r2],
        assessments=merged,evaluation_mode='mixed',errors=[])
    assert scored.matched_primary == 1 and scored.primary_score is None


def test_weighted_leaderboard_never_ranks_an_unfinished_floor():
    from cv_ranker.schemas import RankingReport
    from cv_ranker.weighted_scoring import ScoreWeights, weighted_leaderboard
    r1,r2=req('R001','Basic spreadsheet reporting'),req('R002','Machine maintenance')
    evidence=ResumeSegment('S001','skills','Basic spreadsheet reporting')
    finished=row('R001','matched','Found',[evidence])
    outstanding=row('R002','uncertain',None,state='unverified')
    merged=reconcile_final_assessments(requirements=[r1,r2],
                                        assessments=[finished,outstanding],
                                        source_segments=[evidence])
    scored=score_candidate(candidate_name='Fictional Applicant',
        requirements=[r1,r2],assessments=merged,evaluation_mode='mixed',errors=[])
    report=RankingReport(job_description_source='fictional-JD',
        original_jd_text='Basic spreadsheet reporting. Machine maintenance.',
        jd_validation_mode='manual',yake_candidates=[],requirements=[r1,r2],candidates=[scored])
    projection=weighted_leaderboard(report,ScoreWeights(0,0,100))[0]
    assert projection['rank'] is None
    assert projection['weighted_score'] is None
    assert projection['verified_floor'] == 50
    assert projection['provisional']


def test_old_unverified_report_preserves_its_historical_field():
    historic=RequirementAssessment.model_validate(dict(requirement_id='R001',
        status='uncertain', unified_status='Unverified', assessment_state='unverified',
        reason='Historical technical failure'))
    assert historic.current_decision is None
    assert RequirementAssessment.model_validate(historic.model_dump()).unified_status == 'Unverified'


def test_malicious_model_copy_update_cannot_bypass_score_contract():
    r=req('R001','Stock control')
    source=ResumeSegment('S001','experience','Performed stock control.')
    good=reconcile_final_assessments(requirements=[r],
        assessments=[row('R001','matched','Found',[source])],source_segments=[source])[0]
    corrupted=good.model_copy(update={'unified_status':'Not Found'})
    with pytest.raises(ValidationError):
        score_candidate(candidate_name='Fictional Applicant',requirements=[r],
            assessments=[corrupted],evaluation_mode='llm_assessed',errors=[])


def test_legacy_provider_429_cannot_turn_into_negative():
    from cv_ranker.assessor import _assess_batch
    from cv_ranker.llm import LLMError
    class Always429:
        def invoke_structured(self, **kwargs):
            raise LLMError('OpenRouter HTTP 429 rate limit')
    r=req('R001','Weaving design')
    rows,mode,notice=_assess_batch(resume_text='Education: Bachelor of Arts',
        requirements=[r], llm=Always429())
    assert mode == 'failed'
    assert rows[0].current_decision.verdict is None
    assert rows[0].current_decision.processing_state == 'paused'
    assert rows[0].current_decision.failure.code == 'provider_rate_limit'
    assert 'no candidate negative' in notice[0]

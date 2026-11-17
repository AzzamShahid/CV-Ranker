"""Crash, concurrency and provider-free recovery controls for protocol 57.

Fixtures are synthetic. No public LLM service is contacted. Tests measure
local dispatcher and persistence behavior, not model semantic accuracy.
"""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from cv_ranker.operation_ledger import LocalOperationLedger
from cv_ranker.condition_review import review_compound_uncertainty
from cv_ranker.config import Settings
from cv_ranker.llm import LLMError
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import RequirementAssessment, EvidenceCitation
from cv_ranker.segments import ResumeSegment
from tests.test_v4970_supervisor_three_verdict_e2e import JD, SOURCES, _approved, SyntheticLLM
from tests.test_v4971_deep_audit import _queued


def sig(tag):
    return hashlib.sha256(tag.encode()).hexdigest()


def test_retry_after_and_max_three_attempts_without_wall_clock_sleeps(tmp_path):
    db=tmp_path/'attempts.sqlite'
    with LocalOperationLedger(db) as ledger:
        key=sig('frozen-cv-jd-protocol')
        assert ledger.claim_review(key, now=100)== 'claimed_new'
        ledger.bind_batch([key],sig('first-dispatch-payload'))
        ledger.finish_retryable([key],error_code='provider_rate_limit',
                                retry_after_seconds=30,now=100)
        assert ledger.claim_review(key,now=129)=='retryable_error'
        assert ledger.claim_review(key,now=130)=='claimed_retry'
        ledger.bind_batch([key],sig('second-dispatch-payload'))
        ledger.finish_retryable([key],error_code='provider_rate_limit',now=130)
        assert ledger.claim_review(key,now=130)=='claimed_retry'
        ledger.bind_batch([key],sig('third-dispatch-payload'))
        ledger.finish_retryable([key],error_code='provider_rate_limit',now=130)
        assert ledger.claim_review(key,now=140)=='retryable_error'
        assert ledger.db.execute('SELECT attempt_count FROM operations WHERE signature=?',
                                 (key,)).fetchone()==(3,)


def test_terminal_unknown_delivery_never_resends(tmp_path):
    key=sig('maybe-provider-billed')
    with LocalOperationLedger(tmp_path/'ledger.sqlite') as ledger:
        assert ledger.claim_review(key)=='claimed_new'
        ledger.bind_batch([key],sig('payload'))
        ledger.finish_each({key:('provider_unknown_delivery',None)})
        assert ledger.claim_review(key)=='provider_unknown_delivery'
        assert ledger.result_reference(key)==('provider_unknown_delivery',None)


def test_atomic_result_reference_is_recoverable_and_content_verified(tmp_path):
    key=sig('candidate-original-and-approved-jd')
    payload=b'{"fictional":true,"result":"Found"}'
    with LocalOperationLedger(tmp_path/'ledger.sqlite') as ledger:
        assert ledger.claim_review(key)=='claimed_new'
        ledger.bind_batch([key],sig('actual-payload'))
        digest=ledger.commit_validated_result(key,payload)
        assert ledger.recover_validated_result(key)==payload
        assert ledger.commit_validated_result(key,payload)==digest
        ref=ledger._result_dir()/(digest+'.json')
        if os.name!='nt':
            assert ref.stat().st_mode & 0o777==0o600
        ref.write_bytes(payload+b'forged')
        assert ledger.recover_validated_result(key) is None
    with LocalOperationLedger(tmp_path/'ledger.sqlite') as reopened:
        assert reopened.claim_review(key)=='validated_result'
        assert reopened.recover_validated_result(key) is None


def test_orphan_file_is_not_a_completed_operation(tmp_path):
    db=tmp_path/'ledger.sqlite'
    with LocalOperationLedger(db) as ledger:
        key=sig('crash-before-SQLite-commit')
        assert ledger.claim_review(key)=='claimed_new'
        # Pretend a process died after writing the content but before its
        # transaction. An orphan file never upgrades an unknown dispatch.
        content=b'{"source":"fictional"}'
        digest=hashlib.sha256(content).hexdigest()
        (ledger._result_dir()/(digest+'.json')).write_bytes(content)
    with LocalOperationLedger(db) as recovered:
        assert recovered.claim_review(key)=='claimed_unknown_delivery'
        assert recovered.recover_validated_result(key) is None


def test_lost_result_store_requires_recovery_not_reexecution(tmp_path):
    req=_approved(JD).requirements[0]
    db=tmp_path/'ledger.sqlite'
    first,_=review_compound_uncertainty(requirements=[req],assessments=_queued([req]),
                                        resume_text=SOURCES['found'],llm=SyntheticLLM(Settings()),
                                        ledger_path=db)
    assert first[0].current_decision.verdict=='Found'
    with LocalOperationLedger(db) as ledger:
        paths=list(ledger._result_dir().glob('*.json'))
        assert len(paths)==1
        paths[0].unlink()
    no_calls=SyntheticLLM(Settings())
    recovered,stats=review_compound_uncertainty(requirements=[req],
        assessments=_queued([req]),resume_text=SOURCES['found'],llm=no_calls,
        ledger_path=db)
    assert no_calls.http_attempts==0
    assert recovered[0].current_decision.verdict is None
    assert recovered[0].current_decision.failure.code=='result_store_unrecoverable'
    assert recovered[0].current_decision.processing_state=='input_required'


def test_competing_workers_get_only_one_claim(tmp_path):
    db=tmp_path/'ledger.sqlite'
    key=sig('one-operation-two-processes')
    with LocalOperationLedger(db):
        pass
    def claim(_):
        with LocalOperationLedger(db) as ledger:
            return ledger.claim_review(key)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(claim,range(8)))
    assert values.count('claimed_new')==1
    assert values.count('claimed_unknown_delivery')==7


@pytest.mark.parametrize('size', [1,6,7,12,13])
def test_all_scheduled_work_completes_across_bounded_batches(size,tmp_path):
    from tests.test_v4971_deep_audit import test_DA04_seven_eligible_rows_complete_across_two_batches
    base=_approved(JD).requirements[0]
    rows=[base.model_copy(update={'requirement_id':f'R{i:03}'}) for i in range(1,size+1)]
    class OnePerID(SyntheticLLM):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            data=json.loads(user_prompt)
            result=[]
            for req in data['requirements']:
                sid=next(s['id'] for s in data['sources'] if s['section']=='experience')
                result.append({'requirement_id':req['requirement_id'],'decision':'found',
                     'facets':[{'jd_exact_span':part,'jd_start':JD.index(part),
                           'jd_end':JD.index(part)+len(part),'relation':'satisfied',
                           'source_ids':[sid],'proof_quotes':[{'source_id':sid,
                           'quote':'Operated conveyor' if part=='Operate conveyor' else
                                    'documented dispatch logs'}],
                           'explanation':'The original passage demonstrates the assigned completed duty.'}
                          for part in ('Operate conveyor','document dispatch logs')],
                     'source_ids':[sid],'missing_parts':[],
                     'reason':'Both frozen mandatory duties were completed in original evidence.'})
            self.http_attempts+=1
            return schema.model_validate({'assessments':result})
    llm=OnePerID(Settings())
    result,stats=review_compound_uncertainty(requirements=rows,assessments=_queued(rows),
          resume_text=SOURCES['found'],llm=llm,max_items=6,ledger_path=tmp_path/'ledger.sqlite')
    assert stats.resolved==size
    assert stats.pending==0
    assert llm.http_attempts==(size+5)//6
    assert all(row.current_decision.verdict=='Found' for row in result)


def test_negative_context_must_be_exact_and_candidate_owned(tmp_path):
    req=_approved(JD).requirements[0]
    class InvalidQuote(SyntheticLLM):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.http_attempts+=1
            payload=json.loads(user_prompt)
            sid=next(s['id'] for s in payload['sources'] if s['section']=='experience')
            return schema.model_validate({'assessments':[{'requirement_id':'R001',
               'decision':'not_found',
               'facets':[{'jd_exact_span':part,'jd_start':JD.index(part),
                  'jd_end':JD.index(part)+len(part),'relation':'missing',
                  'source_ids':[sid],'proof_quotes':[{'source_id':sid,'quote':'INVENTED work'}],
                  'evidence_purpose':'context_examined',
                  'explanation':'Unrelated context is not the requested role.'}
                  for part in ('Operate conveyor','document dispatch logs')],
               'source_ids':[sid], 'missing_parts':['Operate conveyor','document dispatch logs'],
               'reason':'Original activity does not support any mandatory task.'}]})
    llm=InvalidQuote(Settings())
    outcome,stats=review_compound_uncertainty(requirements=[req],
        assessments=_queued([req],SOURCES['not_found']),
        resume_text=SOURCES['not_found'],llm=llm,correction_budget=0)
    assert stats.resolved==0
    assert outcome[0].current_decision.failure.code=='response_schema_invalid'
    assert outcome[0].current_decision.verdict is None


def test_transferable_valid_source_preserved_through_canonical_finalizer():
    req=_approved(JD).requirements[0]
    src=ResumeSegment('S005','experience','Operated conveyor machinery for shift coordination.')
    row=RequirementAssessment(requirement_id=req.requirement_id,status='not_matched',
         unified_status='Transferable',reason='Operated related equipment but no dispatch log duties.',
         evidence_ids=[src.segment_id],
         evidence_segments=[EvidenceCitation(segment_id=src.segment_id,section=src.section,text=src.text)])
    final=reconcile_final_assessments(requirements=[req],assessments=[row],source_segments=[src])[0]
    assert final.current_decision.verdict=='Transferable'
    assert final.status=='not_matched'


def test_typed_http_429_cooldown_cannot_be_bypassed_by_immediate_resume(tmp_path):
    """Use typed HTTP status and Retry-After rather than parsing body text."""
    from cv_ranker.llm import OpenRouterHTTPError

    class TypedRejected(SyntheticLLM):
        def invoke_structured(self, **_):
            self.http_attempts += 1
            raise OpenRouterHTTPError(429, retry_after_seconds=120)

    req = _approved(JD).requirements[0]
    ledger_path = tmp_path / 'typed-429.sqlite'
    first = TypedRejected(Settings())
    rows, stats = review_compound_uncertainty(
        requirements=[req], assessments=_queued([req]),
        resume_text=SOURCES['found'], llm=first, ledger_path=ledger_path)
    assert stats.attempted == 1 and first.http_attempts == 1
    assert rows[0].current_decision.verdict is None
    assert rows[0].current_decision.failure.code == 'provider_rate_limit'
    with LocalOperationLedger(ledger_path) as ledger:
        data = ledger.db.execute(
            "SELECT attempt_count, retry_after_epoch FROM operations"
        ).fetchone()
        import time
        assert data[0] == 1
        assert data[1] > time.time() + 90
    second = SyntheticLLM(Settings())
    blocked, stats = review_compound_uncertainty(
        requirements=[req], assessments=rows,
        resume_text=SOURCES['found'], llm=second, ledger_path=ledger_path)
    assert second.http_attempts == 0 and stats.attempted == 0
    assert blocked[0].current_decision.verdict is None

"""Dedicated OS worker for durable jobs. Never execute in a FastAPI handler."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from contextlib import contextmanager
from time import sleep
import time
import math
import json
import os
import socket
import signal
import sys
import traceback
import uuid

from backend.storage import Store, Conflict, NotFound
from backend import engine_service


class StopRequested(RuntimeError): pass


@contextmanager
def lease_pulse(store: Store, job_id: str, worker_id: str, fence: int):
    stop=Event();lost=Event()
    def pulse():
        while not stop.wait(8):
            try:
                if not store.heartbeat(job_id,worker_id,fence,lease_seconds=35):
                    lost.set(); return
            except Exception:
                lost.set();return
    thread=Thread(target=pulse,daemon=True)
    thread.start()
    try:
        yield lost
    finally:
        stop.set();thread.join(timeout=10)


def _is_cancelled(store: Store, job_id: str):
    return bool(store.get_job_record(job_id)['cancel_requested'])


def _safe_error(exc: Exception):
    # Exclude potential provider bodies / local paths / applicant text.
    kind=type(exc).__name__
    if isinstance(exc,StopRequested):return 'cancelled','Cancelled at an assessment checkpoint'
    if isinstance(exc,Conflict):return 'worker_lease_lost','A newer worker owns this operation'
    if kind in ('DocumentError','ValidationError','ValueError'):
        return 'input_invalid','Input or approved revision failed validation; review the source document'
    try:
        from cv_ranker.llm import OpenRouterHTTPError
        if isinstance(exc,OpenRouterHTTPError):
            if exc.status_code == 429:
                return 'provider_rate_limit','Provider returned HTTP 429; retry after the declared cooldown'
            if exc.status_code in (401,403):
                return 'provider_authentication','Cloud credentials or permissions need correction'
            if exc.status_code in (503,502,504):
                return 'provider_unavailable','Provider is currently unavailable'
    except ImportError:
        pass
    return 'engine_processing_error','Processing did not complete; review technical diagnostics before Resume'


def process_claim(store: Store, job_id: str, worker_id: str, fence: int,
                  *, ranker_factory=None):
    record=store.get_job_record(job_id)
    request=json.loads(record['request_json'])
    ws=record['workspace_id']
    if not store.heartbeat(job_id,worker_id,fence,35):raise Conflict('Worker ownership lost before start')
    try:
        with lease_pulse(store,job_id,worker_id,fence) as lost:
            def checkpoint(message='', *, allow_cancel=True):
                if lost.is_set():raise Conflict('Worker lease lost')
                if allow_cancel and _is_cancelled(store,job_id):raise StopRequested('Cooperative cancel')
                if message:store.progress(job_id,worker_id,fence,message)
            if record['kind']=='jd_extract':
                jd_path=store.document_path(ws,request['document_id'])
                checkpoint('Extracting frozen JD')
                draft=engine_service.evaluate_jd(jd_path,request['settings'],progress=checkpoint,ranker_factory=ranker_factory)
                checkpoint('Validating JD')
                store.commit_extracted_jd(job_id,worker_id,fence,
                                          request['document_id'],draft.model_dump(mode='json'))
                return
            if record['kind']!='assess':raise ValueError('Unsupported job')
            approval=store.approval(ws,request['approved_revision_id'])
            approved=approval['body']
            jd_doc=store.draft(ws,approval['draft_id'])['document_id']
            jd_path=store.document_path(ws,jd_doc)
            from datetime import date
            from backend.storage import fingerprint
            context=request.get('assessment_context')
            if not isinstance(context,dict) or not context.get('as_of_date'):
                raise ValueError('Legacy job lacks a frozen assessment date; start a new assessment')
            if (context.get('approved_revision_id') != request['approved_revision_id'] or
                context.get('candidate_source_ids') != request['candidate_ids'] or
                context.get('settings_sha256') != fingerprint(request['settings'])):
                raise ValueError('Frozen assessment context does not match the saved job')
            frozen_date=date.fromisoformat(context['as_of_date'])
            from cv_ranker.schemas import RankingReport, CandidateResult
            from cv_ranker.scoring import assign_ranks
            from cv_ranker.documents import extract_text, DocumentError
            from cv_ranker.build_info import BUILD_ID
            from cv_ranker.eligibility import jd_source_sha256
            draft=engine_service.approved_draft(approved)
            existing={r['document_id']:r for r in store.committed_candidates(job_id)}
            prior=store.report(ws,job_id)
            if prior:
                current=RankingReport.model_validate(prior)
                if current.assessment_as_of_date != frozen_date.isoformat():
                    raise ValueError('Historical report has no compatible frozen assessment date; start a fresh run')
            else:
                text=extract_text(jd_path)
                current=RankingReport(
                   job_description_source=jd_doc,original_jd_text=text,
                   jd_validation_mode=draft.jd_validation_mode,
                   yake_candidates=draft.yake_candidates,requirements=draft.requirements,
                   jd_review_approved=True,jd_review_edited=draft.edited,
                   candidates=[],warnings=draft.warnings,jd_diagnostics=draft.diagnostics,
                   assessment_as_of_date=frozen_date.isoformat(),
                   jd_sha256=jd_source_sha256(text))
            committed_by_pos={r['position']:r for r in existing.values()}
            for position,doc_id in enumerate(request['candidate_ids']):
                checkpoint('Beginning candidate')
                # A completed item is immutable and not re-dispatched on Resume.
                previous=existing.get(doc_id)
                previous_candidate=None
                source_key=None
                if previous:
                    previous_candidate=CandidateResult.model_validate_json(previous['result_json'])
                    if previous_candidate.primary_score is not None and all(
                          a.assessment_state!='unverified' for a in previous_candidate.assessments):
                        continue
                    # We cannot replace a previous uncertain delivery with a
                    # new billable operation unless the per-operation ledger
                    # and original resume source key authorize it.
                    source_key=json.loads(previous['source_ledger_json']).get('source_key') if previous['source_ledger_json'].startswith('{') else None
                doc=None
                response=None
                try:
                    doc=store.document(ws,doc_id)
                    cv_path=store.document_path(ws,doc_id)
                    resume_source=(current.model_copy(update={'candidates':[previous_candidate]})
                                   if previous_candidate is not None else None)
                    response,candidate,segments,key,metrics=engine_service.evaluate_candidate(
                        jd_path,cv_path,approved,request['settings'],progress=checkpoint,
                        ranker_factory=ranker_factory,resume_report=resume_source,
                        resume_candidate=previous_candidate,resume_key=source_key,
                        semantic_dir=store.root/'semantic',assessment_as_of_date=frozen_date)
                except (DocumentError,NotFound):
                    # An unreadable CV is an INPUT failure, never a candidate
                    # negative or an invented source. Commit it as incomplete
                    # and continue independent siblings in this batch.
                    candidate=CandidateResult(
                        candidate_name=(doc['filename'] if doc else 'Unavailable candidate source'),
                        candidate_source=doc_id,primary_score=None,
                        evaluation_mode='failed',score_basis='Document input unavailable',
                        errors=['Candidate source could not be fully read; reupload or repair the document before reassessment.'],
                    )
                    segments=[];key=None;metrics={}
                # A model response already received is valuable completed work.
                # Do not throw it away merely because Cancel arrived in-flight;
                # persist it under the current fence, then stop before the next CV.
                if response is not None:
                    if response.assessment_as_of_date != frozen_date.isoformat():
                        raise ValueError('Worker response has an inconsistent assessment date')
                    identities=('approved_aliases_sha256','eligibility_policy_sha256')
                    if current.candidates and any(getattr(current,field)!=getattr(response,field)
                                                  for field in identities):
                        raise ValueError('Eligibility or alias policy changed within the frozen batch')
                    current=current.model_copy(update={
                        'assessment_as_of_date':response.assessment_as_of_date,
                        'approved_aliases':response.approved_aliases,
                        'approved_aliases_sha256':response.approved_aliases_sha256,
                        'eligibility_policy_sha256':response.eligibility_policy_sha256,
                        'eligibility_policy_reviewed_by':response.eligibility_policy_reviewed_by,
                        'eligibility_gate_names':response.eligibility_gate_names,
                        'eligibility_gates':response.eligibility_gates,
                    })
                checkpoint('Committing candidate',allow_cancel=False)
                candidate=candidate.model_copy(update={
                    'candidate_name':(doc['filename'] if doc else 'Unavailable candidate source'),
                    'candidate_source':doc_id,'rank':None})
                committed_by_pos[position]={'result_json':candidate.model_dump_json(),
                    'source_ledger_json':json.dumps({'source_key':key,'segments':segments})}
                ordered=[CandidateResult.model_validate_json(committed_by_pos[i]['result_json'])
                         for i in sorted(committed_by_pos)]
                # assign_ranks does not invent a score for an incomplete row.
                current=current.model_copy(update={'candidates':assign_ranks(ordered)})
                store.commit_candidate(job_id,worker_id,fence,doc_id,position,
                                       candidate.model_dump(mode='json'),
                                       {'source_key':key,'segments':segments},current.model_dump(mode='json'),
                                       metrics=metrics)
                # Deliberately stop on 429. Restart/retry uses the original
                # engine's semantic ledger and pending decision contract.
                if any(a.current_decision and a.current_decision.failure and
                       a.current_decision.failure.code=='provider_rate_limit'
                       for a in candidate.assessments):
                    delay=metrics.get('provider_retry_after_seconds')
                    # The engine's provider adapter reports this only after a
                    # real 429. Do not fabricate a cooldown or reinterpret
                    # network failures as rate limiting.
                    eligible=(time.time()+float(delay) if isinstance(delay,(int,float))
                       and not isinstance(delay,bool) and math.isfinite(delay) and delay>0 else None)
                    store.terminal(job_id,worker_id,fence,'paused','provider_rate_limit',
                                  'Provider rate limited this run; retry when eligible',eligible_at=eligible)
                    return
            # The durable candidate commits and the final job state are one
            # DB-backed sequence; the event is written in that transaction.
            all_rows=store.committed_candidates(job_id)
            incomplete=any(CandidateResult.model_validate_json(row['result_json']).primary_score is None
                           for row in all_rows)
            if len(all_rows)<len(request['candidate_ids']):
                raise RuntimeError('Some candidate slots have no completed operation')
            store.set_result(job_id,worker_id,fence,current.model_dump(mode='json'),
               state='completed_with_errors' if incomplete else 'completed')
    except StopRequested:
        store.terminal(job_id,worker_id,fence,'cancelled','cancelled',
                       'Stopped at the next safe checkpoint; committed results retained')
    except Conflict:
        # Stale worker must not mutate the newer owner or pretend it committed.
        raise
    except Exception as exc:
        code,message=_safe_error(exc)
        try:store.terminal(job_id,worker_id,fence,'paused',code,message)
        except Conflict: pass


def worker_loop(store: Store | None = None, idle_seconds: float=1.0, *, once: bool=False,
                reconcile_interval: float=5.0):
    store=store or Store()
    owner=f'{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}'
    done=Event()
    def stop(*_):done.set()
    try:signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    except ValueError:pass
    store.reap_stale()
    next_scan=time.monotonic()+max(0.1,min(reconcile_interval,60.0))
    while not done.is_set():
        if time.monotonic() >= next_scan:
            try:
                store.reap_stale()
            except Exception:
                # Transient SQLite contention cannot permanently disable
                # reconciliation; the next monotonic interval retries.
                pass
            next_scan=time.monotonic()+max(0.1,min(reconcile_interval,60.0))
        claimed=store.claim_job(owner)
        if claimed is None:
            if once:break
            done.wait(idle_seconds)
            continue
        job_id,fence=claimed
        try:process_claim(store,job_id,owner,fence)
        except Conflict:pass
        if once:break


if __name__=='__main__':worker_loop()

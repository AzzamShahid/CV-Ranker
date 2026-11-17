"""DA021 source-backed consistency, cancellation, lease and approval regressions."""
from __future__ import annotations
from pathlib import Path
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from backend.storage import Store, Conflict
from tests.web.test_api_worker import setup, workspace, upload, prepare_approved, submit_candidate_job, run_one
from worker.runner import worker_loop


def test_da021_12_approval_replay_same_body_changed_body_conflicts(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,draft=prepare_approved(store,client,headers,ws)
    old=store.approval(ws,approved['id'])
    assert store.approve(ws,draft['id'],draft['revision'],old['body'])['id']==approved['id']
    changed=dict(old['body']); changed['warnings']=['Meaning differs from approved frozen snapshot']
    with pytest.raises(Conflict,match='different content'):
        store.approve(ws,draft['id'],draft['revision'],changed)
    assert store.approval(ws,approved['id'])['body']==old['body']


def test_da021_04_repeat_cancel_cannot_release_live_worker(tmp_path):
    store=Store(tmp_path/'data');ws=store.create_workspace('Example')['id']
    jd=store.add_document(ws,'jd','job.txt','.txt',b'Required: Python')['id']
    job=store.make_job(ws,'jd_extract',{'document_id':jd,'settings':{'use_llm':False}},'one')
    job_id=job['id'];claimed=store.claim_job('worker-1');assert claimed
    states=[store.control(ws,job_id,'cancel')['state'] for _ in range(4)]
    assert states==['cancelling']*4
    with pytest.raises(Conflict):store.control(ws,job_id,'resume')
    assert store.get_job_record(job_id)['owner']=='worker-1'
    # The original worker must acknowledge the stop; only then may resume.
    store.terminal(job_id,'worker-1',claimed[1],'cancelled','cancelled','Stopped at a checkpoint')
    assert store.control(ws,job_id,'resume')['state']=='queued'
    assert store.claim_job('worker-2')[0]==job_id


def test_da021_05_periodic_reap_after_already_started_worker(tmp_path,monkeypatch):
    store=Store(tmp_path/'data');ws=store.create_workspace('Example')['id']
    jd=store.add_document(ws,'jd','job.txt','.txt',b'Required: Python')['id']
    job=store.make_job(ws,'jd_extract',{'document_id':jd,'settings':{'use_llm':False}},'one')
    claim=store.claim_job('disappeared-worker',lease_seconds=60);assert claim
    # Worker replacement starts before lease expiry. We shorten the effective
    # lease without sleeping minutes and run its normal idle loop.
    with store.tx() as db:
        db.execute('UPDATE jobs SET lease_until=? WHERE id=?',(time.time()+0.4,job['id']))
    runner=threading.Thread(target=worker_loop,args=(store,),kwargs={
        'idle_seconds':0.05,'reconcile_interval':0.1},daemon=True)
    # The loop uses no model calls; launch in a subprocess-like separate thread,
    # end it by a test-local stop signal after we see a recovery transition.
    # Instead of an indefinite runner thread, patch claim_job to raise a test
    # sentinel once the stale owner has been reaped.
    original_claim=store.claim_job
    class Done(Exception):pass
    def observe(*args,**kwargs):
        state=store.job(ws,job['id'])
        if state['state']=='paused':raise Done()
        return original_claim(*args,**kwargs)
    monkeypatch.setattr(store,'claim_job',observe)
    with pytest.raises(Done):worker_loop(store,idle_seconds=0.03,reconcile_interval=0.1)
    assert store.job(ws,job['id'])['error_code']=='worker_unknown_delivery'
    assert store.job(ws,job['id'])['state']=='paused'


def test_da021_08_snapshot_is_consistent_after_later_job_commit(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    doc=upload(client,headers,ws,'cv','Applicant.txt','Skills: Python programming')
    job=submit_candidate_job(client,headers,ws,approval,[doc],'snapshot-test')
    run_one(store,job)
    snap=store.assessment_snapshot(ws,job['id'])
    before_rev=snap['result_revision']
    with store.tx() as db:
        db.execute('UPDATE jobs SET result_revision=result_revision+1 WHERE id=?',(job['id'],))
    assert snap['result_revision']==before_rev
    assert snap['report'] is not None
    # A stale snapshot cannot be published into a newly revised job.
    with pytest.raises(Conflict):
        store.record_export(ws,job['id'],snap['weight_revision'],snap['result_revision'],b'placeholder-zip')
    assert store.exports(ws)==[]
    assert list(store.export_root.glob('*.zip'))==[]

"""Failure-injection assertions for frozen dates, snapshot export and source identities.

All inputs are fictional; these tests exercise the real DB/API/worker boundaries.
"""
import json
from datetime import date
from backend import engine_service
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one


def test_frozen_context_survives_cancel_and_resume(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    ids=[upload(client,headers,ws,'cv',f'Person-{i}.txt',f'Skills: Python programming. Fictional applicant {i}') for i in range(3)]
    job=submit_candidate_job(client,headers,ws,approval,ids,'frozen-clock')
    record=store.get_job_record(job['id']);ctx=json.loads(record['request_json'])['assessment_context']
    first_date=ctx['as_of_date']
    assert date.fromisoformat(first_date)
    assert ctx['candidate_source_ids']==ids
    assert ctx['approved_revision_id']==approval['id']
    original=engine_service.evaluate_candidate
    observed=[];n=0
    def call(jd_path,cv_path,*args,**kwargs):
        nonlocal n
        n+=1
        observed.append(kwargs.get('assessment_as_of_date'))
        result=original(jd_path,cv_path,*args,**kwargs)
        if n==1:store.control(ws,job['id'],'cancel')
        return result
    monkeypatch.setattr(engine_service,'evaluate_candidate',call)
    run_one(store,job)
    assert store.job(ws,job['id'])['state']=='cancelled'
    assert store.report(ws,job['id'])['assessment_as_of_date']==first_date
    # Simulate years passing after the first checkpoint. The current clock
    # cannot override the date that was frozen at job submission.
    monkeypatch.setattr('worker.runner.time.time',lambda: 2300000000.0)
    assert client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/resume',headers=headers).status_code==200
    run_one(store,job)
    assert store.job(ws,job['id'])['state']=='completed'
    assert len(observed)==3
    assert {x.isoformat() for x in observed}=={first_date}
    report=store.report(ws,job['id'])
    assert report['assessment_as_of_date']==first_date
    assert all(r['candidate_source'] in ids for r in report['candidates'])
    assert len(store.committed_candidates(job['id']))==3


def test_interleaved_revision_during_zip_creation_rejects_and_cleans(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    doc=upload(client,headers,ws,'cv','Applicant.txt','Skills: Python programming')
    job=submit_candidate_job(client,headers,ws,approval,[doc],'interleaved-export')
    run_one(store,job)
    endpoint=f'/api/v1/workspaces/{ws}/jobs/{job["id"]}'
    original_revision=store.job(ws,job['id'])['result_revision']
    original_ledger=store.committed_candidates(job['id'])
    seen={}
    def concurrent_export(report,weights,ledgers):
        seen['name']=report['candidates'][0]['candidate_name']
        seen['sources']=list(ledgers)
        # A real concurrent worker commits a newer revision after capture.
        with store.tx() as db:
            db.execute('UPDATE jobs SET result_revision=result_revision+1 WHERE id=?',(job['id'],))
        return b'fictitious export bytes, must never publish'
    monkeypatch.setattr(engine_service,'export_zip',concurrent_export)
    result=client.post(endpoint+'/exports',headers=headers,json={
        'revision':original_revision,'weight_revision':store.weights(ws)['revision']})
    assert result.status_code==409,result.text
    assert seen['name']=='Applicant.txt'
    assert seen['sources']==['0']
    assert store.committed_candidates(job['id'])==original_ledger
    assert store.exports(ws)==[]
    assert list(store.export_root.glob('*.zip'))==[]
    assert store.job(ws,job['id'])['result_revision']==original_revision+1


def test_rankings_revision_cannot_claim_a_newer_commit(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    cv=upload(client,headers,ws,'cv','Before Commit.txt','Skills: Python programming')
    job=submit_candidate_job(client,headers,ws,approval,[cv],'rankings-atomic')
    run_one(store,job)
    start_revision=store.job(ws,job['id'])['result_revision']
    real_snapshot=type(store).assessment_snapshot
    def snapshot_then_commit(instance,workspace_id,job_id):
        value=real_snapshot(instance,workspace_id,job_id)
        with instance.tx() as db:
            report=json.loads(db.execute('SELECT result_json FROM jobs WHERE id=?',(job_id,)).fetchone()[0])
            report['candidates'][0]['candidate_name']='After Commit.txt'
            db.execute('UPDATE jobs SET result_json=?,result_revision=result_revision+1 WHERE id=?',
                (json.dumps(report),job_id))
        return value
    # FastAPI owns an independent Store instance, so patch the shared
    # operation rather than a local object's attribute.
    monkeypatch.setattr(type(store),'assessment_snapshot',snapshot_then_commit)
    response=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings')
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['result_revision']==start_revision
    assert payload['items'][0]['candidate']=='Before Commit.txt'
    assert store.job(ws,job['id'])['result_revision']==start_revision+1
    assert store.report(ws,job['id'])['candidates'][0]['candidate_name']=='After Commit.txt'

"""Migration completion: real API/storage boundaries, no paid-model operations."""
from pathlib import Path
import os,time
os.environ['TEXTILEHR_TESTING']='1'
import pytest
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.storage import Store,Conflict
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one


def test_explicit_unknown_delivery_recovery_is_audited(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','job.txt','Required skills:\n- Python')
    request=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'unknown-1'},
        json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    job_id=request['id'];store.claim_job('disconnected-worker')
    with store.tx() as db:db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job_id,))
    assert store.reap_stale()==1
    url=f'/api/v1/workspaces/{ws}/jobs/{job_id}/resolve-unknown'
    inspect=client.post(url,json={'resolution':'inspect'},headers=headers)
    assert inspect.status_code==200
    assert inspect.json()['may_have_incurred_provider_cost'] is True
    wrong=client.post(url,json={'resolution':'accept_duplicate_risk','acknowledgement':'OK'},headers=headers)
    assert wrong.status_code==409
    action=client.post(url,json={'resolution':'accept_duplicate_risk',
       'acknowledgement':'I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES'},headers=headers)
    assert action.status_code==200,action.text
    assert action.json()['state']=='queued'
    assert store.get_job_record(job_id)['recovery_resolution']=='operator_acknowledged_duplicate_cost'
    run_one(store,request)
    assert store.job(ws,job_id)['state']=='completed'
    history=client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/event-history').json()
    assert 'recovery_acknowledged' in [item['kind'] for item in history['items']]


def test_deletion_requires_explicit_confirmation_and_retains_references(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    unreferenced=upload(client,headers,ws,'cv','Unused.txt','Unrelated fictional source')
    url=f'/api/v1/workspaces/{ws}/documents/{unreferenced}'
    assert client.request('DELETE',url,headers=headers,json={'confirmation':'NO'}).status_code==422
    assert client.request('DELETE',url,headers=headers,json={'confirmation':'DELETE'}).status_code==200
    assert client.get(f'/api/v1/workspaces/{ws}/documents/{unreferenced}/download').status_code==404
    jd=upload(client,headers,ws,'jd','job.txt','Required skills:\n- Python')
    queued=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'active'},
        json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    assert client.request('DELETE',f'/api/v1/workspaces/{ws}/documents/{jd}',headers=headers,
         json={'confirmation':'DELETE'}).status_code==409
    run_one(store,queued)
    assert client.request('DELETE',f'/api/v1/workspaces/{ws}/documents/{jd}',headers=headers,
         json={'confirmation':'DELETE'}).status_code==409


def test_stored_cooldown_is_enforced_without_worker_dispatch(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','job.txt','Required skills:\n- Python')
    created=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'cooldown'},
      json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    claimed=store.claim_job('worker')
    store.terminal(created['id'],'worker',claimed[1],'paused','provider_rate_limit','Cooldown',eligible_at=time.time()+100)
    result=client.post(f'/api/v1/workspaces/{ws}/jobs/{created["id"]}/resume',headers=headers)
    assert result.status_code==409 and store.claim_job('second-worker') is None
    with store.tx() as db:db.execute('UPDATE jobs SET eligible_at=? WHERE id=?',(time.time()-1,created['id']))
    assert client.post(f'/api/v1/workspaces/{ws}/jobs/{created["id"]}/resume',headers=headers).status_code==200
    assert store.claim_job('second-worker') is not None


def test_atomic_event_snapshot_and_replay_watermark(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','jd.txt','Required skills:\n- Python')
    created=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'events'},
       json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    snapshot=store.event_snapshot(ws,created['id'])
    assert snapshot['snapshot']['sequence']==1 and snapshot['earliest']==1
    run_one(store,created)
    history=client.get(f'/api/v1/workspaces/{ws}/jobs/{created["id"]}/event-history?after=1').json()
    assert history['snapshot']['sequence']>=2
    assert history['items'][0]['seq']==2
    assert history['items'][-1]['seq']==history['snapshot']['sequence']


def test_api_contract_has_explicit_public_models(tmp_path):
    from backend.contracts import JobSnapshotDTO,RankingsDTO,DocumentsDTO
    app=create_app(Store(tmp_path/'data'),serve_frontend=False)
    schema=app.openapi()
    for name in ['JobSnapshotDTO','RankingDTO','CandidateDetailDTO','WorkspaceDTO','WeightsDTO','JobEventDTO']:
        assert name in schema['components']['schemas']
    job_route=schema['paths']['/api/v1/workspaces/{workspace_id}/jobs/{job_id}']['get']
    assert job_route['responses']['200']['content']['application/json']['schema']['$ref'].endswith('JobSnapshotDTO')


def test_historical_zip_import_supported_and_rejects_unsafe_archive(tmp_path):
    import io,json,zipfile
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    cv=upload(client,headers,ws,'cv','Fictional Applicant.txt','Skills:\nPython')
    job=submit_candidate_job(client,headers,ws,approval,[cv],'history-zip');run_one(store,job)
    report=store.report(ws,job['id'])
    blob=io.BytesIO()
    with zipfile.ZipFile(blob,'w') as archive:
        archive.writestr('complete_assessment.json',json.dumps(report))
    reply=client.post(f'/api/v1/workspaces/{ws}/historical-reports',headers=headers,
        files={'file':('history.zip',blob.getvalue(),'application/zip')})
    assert reply.status_code==201,reply.text
    assert reply.json()['source_name']=='history.zip'
    tampered=io.BytesIO()
    with zipfile.ZipFile(tampered,'w') as archive:
        archive.writestr('../escape','malicious')
        archive.writestr('complete_assessment.json',json.dumps(report))
    wrong=client.post(f'/api/v1/workspaces/{ws}/historical-reports',headers=headers,
        files={'file':('bad.zip',tampered.getvalue(),'application/zip')})
    assert wrong.status_code==422,wrong.text
    assert len(store.historical(ws))==1


def test_two_tabs_share_session_without_invalidating_first_csrf(tmp_path):
    store,first,headers=setup(tmp_path)
    # Another tab opening /session must reuse the same signed cookie and CSRF.
    old_cookie=first.cookies.get('textilehr_local_session')
    second=first.get('/api/v1/session')
    assert second.status_code==200
    assert first.cookies.get('textilehr_local_session')==old_cookie
    assert second.json()['csrf_token']==headers['X-CSRF-Token']
    assert first.post('/api/v1/workspaces',json={'title':'First tab still authorized'},headers=headers).status_code==201


def test_job_deletion_unlocks_referenced_cv_and_keeps_approved_jd(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    cv=upload(client,headers,ws,'cv','Used Applicant.txt','Skills:\nPython programming')
    job=submit_candidate_job(client,headers,ws,approved,[cv],'delete-me')
    job_url=f'/api/v1/workspaces/{ws}/jobs/{job["id"]}'
    assert client.request('DELETE',job_url,headers=headers,json={'confirmation':'DELETE'}).status_code==409
    run_one(store,job)
    assert client.request('DELETE',f'/api/v1/workspaces/{ws}/documents/{cv}',headers=headers,
             json={'confirmation':'DELETE'}).status_code==409
    removed=client.request('DELETE',job_url,headers=headers,json={'confirmation':'DELETE'})
    assert removed.status_code==200,removed.text
    assert client.request('DELETE',f'/api/v1/workspaces/{ws}/documents/{cv}',headers=headers,
             json={'confirmation':'DELETE'}).status_code==200
    assert client.get(f'/api/v1/workspaces/{ws}/jd').json()['approved'] is not None


def test_workspace_deletion_blocks_unknown_delivery_then_removes_private_files(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','private JD.txt','Required skills:\n- Python programming')
    doc_path=store.document_path(ws,jd)
    created=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'delete-space'},
       json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    delete=lambda:client.request('DELETE',f'/api/v1/workspaces/{ws}',headers=headers,json={'confirmation':'DELETE WORKSPACE'})
    assert delete().status_code==409
    run_one(store,created)
    assert delete().status_code==200
    assert not doc_path.exists()
    assert client.get(f'/api/v1/workspaces/{ws}').status_code==404


def test_revisioned_settings_cannot_raise_server_budget(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','requirements.txt','Required skills:\n- Python programming')
    reply=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'budget-test'},
      json={'document_id':jd,'use_llm':False,'provider':'ollama',
            'openrouter_context_tokens':262144,'openrouter_output_tokens':65535,
            'openrouter_max_requests_per_assessment':1000})
    assert reply.status_code==422
    limited=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'budget-low'},
      json={'document_id':jd,'use_llm':False,'provider':'ollama',
            'openrouter_context_tokens':8192,'openrouter_output_tokens':1024,
            'openrouter_max_requests_per_assessment':3})
    assert limited.status_code==202,limited.text
    params=store.get_job_record(limited.json()['id'])['request_json']
    assert '"openrouter_context_tokens":8192' in params
    assert '"openrouter_max_requests_per_assessment":3' in params
    assert 'openrouter_api_key' not in params

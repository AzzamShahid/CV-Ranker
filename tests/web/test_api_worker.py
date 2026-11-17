"""Real FastAPI → SQLite → dedicated-worker-adapter integration with fictional CVs."""
import json
import os
from pathlib import Path

os.environ['TEXTILEHR_TESTING']='1'

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.storage import Store, Conflict
from worker.runner import process_claim


def setup(tmp_path):
    store=Store(tmp_path/'data')
    client=TestClient(create_app(store,serve_frontend=False),base_url='http://testserver')
    auth=client.get('/api/v1/session')
    assert auth.status_code==200,auth.text
    headers={'Origin':'http://testserver','X-CSRF-Token':auth.json()['csrf_token']}
    return store,client,headers


def workspace(client,headers):
    response=client.post('/api/v1/workspaces',json={'title':'Fictional Textile HR Test'},headers=headers)
    assert response.status_code==201,response.text
    return response.json()['id']


def upload(client,headers,ws,kind,name,text):
    response=client.post(f'/api/v1/workspaces/{ws}/documents?kind={kind}',
              files={'file':(name,text.encode('utf-8'),'text/plain')},headers=headers)
    assert response.status_code==201,response.text
    return response.json()['id']


def run_one(store,job):
    claim=store.claim_job('test-worker')
    assert claim and claim[0]==job['id']
    process_claim(store,claim[0],'test-worker',claim[1])


def test_fictional_approval_and_assessment_no_model_calls(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','weaving.txt','Required qualifications:\n- Python programming\n- SQL database skills')
    cv=upload(client,headers,ws,'cv','Applicant A.txt','Skills:\nPython programming\nSQL database skills')
    response=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'first-jd'},
       json={'document_id':jd,'use_llm':False,'provider':'ollama'})
    assert response.status_code==202,response.text
    run_one(store,response.json())
    extraction=store.report(ws,response.json()['id'])
    assert extraction and 'draft_id' in extraction,store.job(ws,response.json()['id'])
    details=client.get(f'/api/v1/workspaces/{ws}/jd/drafts/{extraction["draft_id"]}').json()
    assert details['rows']
    approved=client.post(f'/api/v1/workspaces/{ws}/jd/approve',headers=headers,
        json={'draft_id':details['id'],'revision':details['revision'],'rows':details['rows']})
    assert approved.status_code==200,approved.text
    job=client.post(f'/api/v1/workspaces/{ws}/assessment-jobs',headers=headers|{'Idempotency-Key':'candidate-batch-1'},
       json={'candidate_ids':[cv],'approved_revision_id':approved.json()['id'],
             'use_llm':False,'unified':False,'provider':'ollama'})
    assert job.status_code==202,job.text
    run_one(store,job.json())
    status=client.get(f'/api/v1/workspaces/{ws}/jobs/{job.json()["id"]}')
    assert status.json()['state'] in ('completed','completed_with_errors'),status.json()
    ranking=client.get(f'/api/v1/workspaces/{ws}/jobs/{job.json()["id"]}/rankings')
    assert ranking.status_code==200,ranking.text
    assert ranking.json()['items']
    detail=client.get(f'/api/v1/workspaces/{ws}/jobs/{job.json()["id"]}/candidates/{cv}')
    assert detail.status_code==200,detail.text
    assert detail.json()['candidate']['candidate_source']==cv
    duplicate=client.post(f'/api/v1/workspaces/{ws}/assessment-jobs',headers=headers|{'Idempotency-Key':'candidate-batch-1'},
       json={'candidate_ids':[cv],'approved_revision_id':approved.json()['id'],
             'use_llm':False,'unified':False,'provider':'ollama'})
    assert duplicate.status_code==202 and duplicate.json()['id']==job.json()['id']
    other=client.post(f'/api/v1/workspaces/{ws}/assessment-jobs',headers=headers|{'Idempotency-Key':'candidate-batch-1'},
       json={'candidate_ids':[cv],'approved_revision_id':approved.json()['id'],
             'use_llm':True,'unified':True,'provider':'ollama'})
    assert other.status_code==409
    exp=client.post(f'/api/v1/workspaces/{ws}/jobs/{job.json()["id"]}/exports',headers=headers,
      json={'revision':status.json()['result_revision'],'weight_revision':0})
    assert exp.status_code==201,exp.text
    download=client.get(f'/api/v1/workspaces/{ws}/exports/{exp.json()["id"]}/download')
    assert download.status_code==200 and download.content[:2]==b'PK'


def test_cross_origin_and_revision_conflicts(tmp_path):
    store,client,headers=setup(tmp_path)
    ws=workspace(client,headers)
    bad=client.post('/api/v1/workspaces',headers={'Origin':'https://evil.test','X-CSRF-Token':headers['X-CSRF-Token']},json={'title':'Unauthorized'})
    assert bad.status_code==403
    missing=client.post('/api/v1/workspaces',headers={'Origin':'http://testserver'},json={'title':'Unauthorized'})
    assert missing.status_code==403
    accepted=client.put(f'/api/v1/workspaces/{ws}/weights',headers=headers,
        json={'revision':0,'weights':{'experience':10,'education':10,'jd':80}})
    assert accepted.status_code==200,accepted.text
    stale=client.put(f'/api/v1/workspaces/{ws}/weights',headers=headers,
        json={'revision':0,'weights':{'experience':10,'education':10,'jd':80}})
    assert stale.status_code==409
    assert client.get('/api/v1/workspaces/' + '0'*32).status_code==404


def test_two_claimants_and_stale_fence(tmp_path):
    store=Store(tmp_path/'data');ws=store.create_workspace('Example')['id']
    jd=store.add_document(ws,'jd','jd.txt','.txt',b'Required skills:\n- Python')['id']
    job=store.make_job(ws,'jd_extract',{'document_id':jd,'settings':{'use_llm':False,'provider':'ollama'}},'extract-one')
    claimed=store.claim_job('worker-A')
    assert claimed
    assert store.claim_job('worker-B') is None
    with store.tx() as conn:
        conn.execute("UPDATE jobs SET owner='worker-B',fencing=fencing+1 WHERE id=?",(job['id'],))
    with pytest.raises(Conflict):store.progress(job['id'],'worker-A',claimed[1],'Candidate')


def prepare_approved(store,client,headers,ws,jd_text='Required skills:\n- Python programming'):
    jd=upload(client,headers,ws,'jd','job-description.txt',jd_text)
    queued=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'jd-'+jd},
      json={'document_id':jd,'use_llm':False,'provider':'ollama'})
    assert queued.status_code==202,queued.text
    run_one(store,queued.json())
    draft_id=store.report(ws,queued.json()['id'])['draft_id']
    draft=client.get(f'/api/v1/workspaces/{ws}/jd/drafts/{draft_id}').json()
    result=client.post(f'/api/v1/workspaces/{ws}/jd/approve',headers=headers,
      json={'draft_id':draft_id,'revision':draft['revision'],'rows':draft['rows']})
    assert result.status_code==200,result.text
    return result.json(),draft


def submit_candidate_job(client,headers,ws,approval,ids,key):
    response=client.post(f'/api/v1/workspaces/{ws}/assessment-jobs',headers=headers|{'Idempotency-Key':key},json={
      'candidate_ids':ids,'approved_revision_id':approval['id'],'use_llm':False,'unified':False,'provider':'ollama'})
    assert response.status_code==202,response.text
    return response.json()


def test_duplicate_filenames_are_distinct_candidate_documents(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    first=upload(client,headers,ws,'cv','Applicant.txt','Skills:\nPython programming')
    second=upload(client,headers,ws,'cv','Applicant.txt','Experience:\nHandled parcel sorting and dispatch')
    assert first!=second
    assert store.document(ws,first)['sha256'] !=store.document(ws,second)['sha256']
    job=submit_candidate_job(client,headers,ws,approved,[first,second],'duplicates')
    run_one(store,job)
    report=store.report(ws,job['id'])
    assert len(report['candidates'])==2
    assert {c['candidate_source'] for c in report['candidates']}=={first,second}
    ranks=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings').json()['items']
    assert {r['candidate_id'] for r in ranks}=={first,second}
    left=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/candidates/{first}').json()
    right=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/candidates/{second}').json()
    assert left['candidate']['candidate_source'] !=right['candidate']['candidate_source']
    assert left['original_segments'] !=right['original_segments']


def test_weight_only_edit_makes_zero_model_calls(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    cv=upload(client,headers,ws,'cv','Skills.txt','Skills:\nPython programming')
    job=submit_candidate_job(client,headers,ws,approved,[cv],'weights')
    run_one(store,job)
    original=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings').json()
    def no_assessment(*args,**kwargs):raise AssertionError('A read/weight edit dispatched candidate assessment')
    monkeypatch.setattr('backend.engine_service.evaluate_candidate',no_assessment)
    changed=client.put(f'/api/v1/workspaces/{ws}/weights',headers=headers,
      json={'revision':0,'weights':{'experience':0,'education':0,'jd':100}})
    assert changed.status_code==200,changed.text
    later=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings').json()
    assert later['weight_revision']==1 and original['weight_revision']==0
    assert later['result_revision']==original['result_revision']
    assert client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}').status_code==200
    share=client.post(f'/api/v1/workspaces/{ws}/weights/rebalance',headers=headers,json={})
    assert share.status_code==200,share.text
    assert set(share.json()['shares'])=={r['requirement_id'] for r in approved['body']['requirements']}


def test_cross_workspace_scope_and_bad_uploads(tmp_path):
    store,client,headers=setup(tmp_path);one=workspace(client,headers);two=workspace(client,headers)
    cv=upload(client,headers,one,'cv','Individual.txt','Skills:\nPython')
    assert client.get(f'/api/v1/workspaces/{two}/documents/{cv}/download').status_code==404
    assert client.get(f'/api/v1/workspaces/{two}/documents').status_code==200
    bad_pdf=client.post(f'/api/v1/workspaces/{one}/documents?kind=cv',headers=headers,
      files={'file':('forged.pdf',b'not a PDF','application/pdf')})
    assert bad_pdf.status_code==422
    invalid_docx=client.post(f'/api/v1/workspaces/{one}/documents?kind=cv',headers=headers,
      files={'file':('forged.docx',b'PK\x03\x04broken','application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert invalid_docx.status_code==422
    untrusted_xml=client.post(f'/api/v1/workspaces/{one}/documents?kind=cv',headers=headers,
      files={'file':('code.svg',b'<script>alert(1)</script>','image/svg+xml')})
    assert untrusted_xml.status_code==422


def test_source_csv_formula_name_is_not_executable(tmp_path):
    from zipfile import ZipFile
    from io import BytesIO
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    suspicious='=HYPERLINK("evil.test","Applicant").txt'
    cv=upload(client,headers,ws,'cv',suspicious,'Skills:\nPython programming')
    job=submit_candidate_job(client,headers,ws,approval,[cv],'csv')
    run_one(store,job)
    snapshot=store.job(ws,job['id'])
    exp=client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/exports',headers=headers,json={
      'revision':snapshot['result_revision'],'weight_revision':0})
    assert exp.status_code==201,exp.text
    with ZipFile(BytesIO(client.get(f'/api/v1/workspaces/{ws}/exports/{exp.json()["id"]}/download').content)) as archive:
        csv_data=archive.read('weighted_leaderboard.csv').decode('utf-8-sig')
    assert "'=HYPERLINK" in csv_data


def test_cancel_queued_then_resume_and_event_order(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','JD.txt','Required skills:\n- Python')
    job=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'cancel-test'},
      json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    cancelled=client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/cancel',headers=headers)
    assert cancelled.json()['state']=='cancelled'
    assert store.claim_job('worker-X') is None
    resumed=client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/resume',headers=headers)
    assert resumed.json()['state']=='queued'
    run_one(store,job)
    history=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/event-history?after=0').json()
    seq=[e['seq'] for e in history['items']]
    assert seq==sorted(set(seq))
    assert 'completed' in [e['kind'] for e in history['items']]


def test_historical_json_import_is_read_only(tmp_path):
    from cv_ranker.schemas import RankingReport
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    cv=upload(client,headers,ws,'cv','Candidate.txt','Skills:\nPython')
    job=submit_candidate_job(client,headers,ws,approved,[cv],'hist')
    run_one(store,job)
    historic=store.report(ws,job['id'])
    historic['build_id']='some-older-historical-version'
    response=client.post(f'/api/v1/workspaces/{ws}/historical-reports',headers=headers,
                         files={'file':('archive.json',json.dumps(historic).encode('utf-8'),'application/json')})
    assert response.status_code==201,response.text
    assert response.json()['source_build']=='some-older-historical-version'
    history=client.get(f'/api/v1/workspaces/{ws}/historical-reports').json()['items']
    assert len(history)==1
    assert len(store.historical_report(ws,history[0]['id'])['body']['candidates'])==1
    assert client.post(f'/api/v1/workspaces/{ws}/historical-reports',headers=headers,
                         files={'file':('malicious.pkl',b'pickle','application/octet-stream')}).status_code==422


def test_static_routes_and_unknown_api(tmp_path):
    store=Store(tmp_path/'data')
    client=TestClient(create_app(store,serve_frontend=True),base_url='http://testserver')
    assert client.get('/w/abc123/overview').status_code==200
    assert 'TextileHR AI' in client.get('/w/abc123/overview').text
    assert client.get('/api/v1/unknown-route').status_code==404
    assert client.get('/assets/brand/RWML-Logo.svg').status_code==200


def test_openapi_contract_is_stable(tmp_path):
    store=Store(tmp_path/'data')
    app=create_app(store,serve_frontend=False)
    assert app.openapi()['paths']['/api/v1/workspaces/{workspace_id}/jobs/{job_id}/rankings']['get']
    from subprocess import run
    check=run([__import__('sys').executable,'scripts/generate_web_contract.py','--check'],
              cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True)
    assert check.returncode==0,check.stdout+check.stderr


def test_real_os_worker_process_and_api_restart_preserve_result(tmp_path):
    """Real subprocess consumes a queued job after the initiating HTTP request ends."""
    import subprocess,sys
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','jd.txt','Required skills:\n- Python programming')
    created=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'os-worker'},
          json={'document_id':jd,'use_llm':False,'provider':'ollama'})
    assert created.status_code==202,created.text
    preserved_cookie=client.cookies.get('textilehr_local_session')
    client.close()
    env=os.environ.copy();env['TEXTILEHR_DATA_DIR']=str(store.root)
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([sys.executable,'-m','worker','--once'],cwd=root,env=env,
                          capture_output=True,text=True,timeout=65)
    assert result.returncode==0,(result.stdout[-600:],result.stderr[-1200:])
    reloaded=Store(store.root)
    with TestClient(create_app(reloaded,serve_frontend=False),base_url='http://testserver') as second:
        second.cookies.set('textilehr_local_session',preserved_cookie)
        state=second.get(f'/api/v1/workspaces/{ws}/jobs/{created.json()["id"]}')
        assert state.status_code==200
        assert state.json()['state']=='completed'
        assert reloaded.report(ws,created.json()['id'])['draft_id']


def test_local_sqlite_backup_and_verified_restore(tmp_path):
    from scripts.data_backup import backup,restore
    import zipfile
    store=Store(tmp_path/'data');ws=store.create_workspace('Encrypted backup not claimed')['id']
    store.add_document(ws,'cv','Applicant.txt','.txt',b'Skills: Python programming')
    output=tmp_path/'local-backup.zip'
    backup(store.root,output)
    assert output.is_file() and output.read_bytes().startswith(b'PK')
    restored=tmp_path/'restored'
    restore(output,restored)
    reloaded=Store(restored)
    assert reloaded.workspace(ws)['id']==ws
    assert len(reloaded.documents(ws))==1
    # A missing or corrupt file is never silently trusted on restore.
    tampered=tmp_path/'tampered.zip'
    with zipfile.ZipFile(output) as src,zipfile.ZipFile(tampered,'w') as target:
        for name in src.namelist():
            data=src.read(name)
            target.writestr(name,data+b'forged' if name=='textilehr.sqlite3' else data)
    with pytest.raises(SystemExit,match='hash mismatch'):
        restore(tampered,tmp_path/'tampered-restore')


def test_expired_lease_is_paused_and_unknown_delivery_is_not_blindly_resent(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    jd=upload(client,headers,ws,'jd','JD.txt','Required skills:\n- Python')
    task=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',headers=headers|{'Idempotency-Key':'lost'},
        json={'document_id':jd,'use_llm':False,'provider':'ollama'}).json()
    claimed=store.claim_job('crashed-worker')
    assert claimed is not None
    with store.tx() as db:
        db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(task['id'],))
    assert store.reap_stale()==1
    state=store.job(ws,task['id'])
    assert state['state']=='paused' and state['error_code']=='worker_unknown_delivery'
    assert store.claim_job('unrelated-worker') is None
    attempt=client.post(f'/api/v1/workspaces/{ws}/jobs/{task["id"]}/resume',headers=headers)
    assert attempt.status_code==409
    assert store.job(ws,task['id'])['error_code']=='worker_unknown_delivery'

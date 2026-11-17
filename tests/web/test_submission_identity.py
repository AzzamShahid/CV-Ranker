"""Backend completion: real durable request identity and lost-response replay."""
from concurrent.futures import ThreadPoolExecutor
from tests.web.test_api_worker import setup,workspace,upload
from backend.storage import Store,Conflict,NotFound
import pytest


def test_submission_response_lost_recovered_without_new_job(tmp_path):
    store,client,headers=setup(tmp_path)
    ws=workspace(client,headers)
    doc=upload(client,headers,ws,'jd','Example.txt','Required skills: Python')
    key='ui-'+'f'*64
    body={'document_id':doc,'use_llm':False,'provider':'ollama'}
    endpoint=f'/api/v1/workspaces/{ws}/jd/extraction-jobs'
    created=client.post(endpoint,headers=headers|{'Idempotency-Key':key},json=body)
    assert created.status_code==202,created.text
    original=created.json()['id']
    # In a real browser the response is lost; the idempotency key was stored first.
    found=client.get(f'/api/v1/workspaces/{ws}/submissions/{key}')
    assert found.status_code==200 and found.json()['id']==original
    resend=client.post(endpoint,headers=headers|{'Idempotency-Key':key},json=body)
    assert resend.status_code==202 and resend.json()['id']==original
    assert len(store.jobs(ws))==1
    assert store.job(ws,original)['sequence']==1


def test_lookup_never_creates_work_and_is_workspace_scoped(tmp_path):
    store,client,headers=setup(tmp_path)
    ws=workspace(client,headers);other=workspace(client,headers)
    key='ui-'+'a'*64
    assert client.get(f'/api/v1/workspaces/{ws}/submissions/{key}').status_code==404
    assert store.jobs(ws)==[]
    doc=upload(client,headers,ws,'jd','jd.txt','Required skills: Python')
    job=store.make_job(ws,'jd_extract',{'document_id':doc,'settings':{'use_llm':False}},key)
    assert client.get(f'/api/v1/workspaces/{other}/submissions/{key}').status_code==404
    assert client.get(f'/api/v1/workspaces/{ws}/submissions/{key}').json()['id']==job['id']
    assert store.job(ws,job['id'])['sequence']==1


def test_concurrent_same_intent_is_atomic_across_process_threads(tmp_path):
    store=Store(tmp_path/'db');ws=store.create_workspace('A workspace')['id']
    doc=store.add_document(ws,'jd','jd.txt','.txt',b'Required: Python')['id']
    payload={'document_id':doc,'settings':{'provider':'ollama','use_llm':False}}
    with ThreadPoolExecutor(max_workers=12) as executor:
        jobs=list(executor.map(lambda _:store.make_job(ws,'jd_extract',payload,'same-intent'),range(25)))
    assert {job['id'] for job in jobs}=={jobs[0]['id']}
    assert len(store.jobs(ws))==1
    with pytest.raises(Conflict):store.make_job(ws,'jd_extract',{'document_id':'a different document'},'same-intent')


def test_deleted_job_cannot_be_recreated_by_stale_browser_intent(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    doc=upload(client,headers,ws,'jd','jd.txt','Required skills: Python')
    key='ui-'+'0'*64
    body={'document_id':doc,'use_llm':False,'provider':'ollama'}
    result=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',
       json=body,headers=headers|{'Idempotency-Key':key})
    assert result.status_code==202,result.text
    job=result.json()
    # Explicitly cancel queued job, then delete the terminal record.
    assert client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/cancel',headers=headers).json()['state']=='cancelled'
    deleted=client.request('DELETE',f'/api/v1/workspaces/{ws}/jobs/{job["id"]}',
                          json={'confirmation':'DELETE'},headers=headers)
    assert deleted.status_code==200,deleted.text
    assert client.get(f'/api/v1/workspaces/{ws}/submissions/{key}').status_code==409
    again=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',
       json=body,headers=headers|{'Idempotency-Key':key})
    assert again.status_code==409
    fresh=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',
       json=body,headers=headers|{'Idempotency-Key':key+'-new'})
    assert fresh.status_code==202


def test_schema_three_to_four_tombstone_migration(tmp_path):
    store=Store(tmp_path/'data')
    with store.tx() as db:
        db.execute('DROP TABLE submission_tombstones')
        db.execute('DELETE FROM schema_info WHERE version=4')
    changed=Store(store.root)
    with changed.connect() as db:
        assert db.execute('SELECT max(version) FROM schema_info').fetchone()[0]==4
        assert db.execute("SELECT name FROM sqlite_master WHERE name='submission_tombstones'").fetchone()


def test_workspace_delete_purges_submission_tombstones_and_keeps_foreign_keys(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    doc=upload(client,headers,ws,'jd','job.txt','Required skills: Python')
    key='ui-'+'1'*64
    created=client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',
                        headers=headers|{'Idempotency-Key':key},
                        json={'document_id':doc,'provider':'ollama','use_llm':False}).json()
    client.post(f'/api/v1/workspaces/{ws}/jobs/{created["id"]}/cancel',headers=headers)
    assert client.request('DELETE',f'/api/v1/workspaces/{ws}/jobs/{created["id"]}',
                          json={'confirmation':'DELETE'},headers=headers).status_code==200
    deleted=client.request('DELETE',f'/api/v1/workspaces/{ws}',
                           json={'confirmation':'DELETE WORKSPACE'},headers=headers)
    assert deleted.status_code==200,deleted.text
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM submission_tombstones WHERE workspace_id=?',(ws,)).fetchone()[0]==0

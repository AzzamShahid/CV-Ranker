"""Cancellation during an already-sent candidate operation preserves its response."""
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one
from backend import engine_service


def test_cancel_midflight_commits_received_response_before_stopping(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    docs=[upload(client,headers,ws,'cv',f'Applicant_{i}.txt',
                 f'Skills: Python programming. Fictional sample {i}') for i in range(3)]
    job=submit_candidate_job(client,headers,ws,approved,docs,'midflight-cancel')
    original=engine_service.evaluate_candidate
    invoked={doc:0 for doc in docs}
    first_round=True
    def triggered(jd_path,cv_path,*args,**kwargs):
        nonlocal first_round
        docid=cv_path.stem
        invoked[docid]+=1
        response=original(jd_path,cv_path,*args,**kwargs)
        if first_round and docid==docs[1]:
            first_round=False
            # Cancel after the engine returned its result, before publication.
            store.control(ws,job['id'],'cancel')
        return response
    monkeypatch.setattr(engine_service,'evaluate_candidate',triggered)
    run_one(store,job)
    snapshot=store.job(ws,job['id'])
    assert snapshot['state']=='cancelled'
    assert snapshot['progress']==2
    assert len(store.committed_candidates(job['id']))==2
    report=store.report(ws,job['id'])
    assert {c['candidate_source'] for c in report['candidates']}==set(docs[:2])
    assert client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/resume',headers=headers).status_code==200
    run_one(store,job)
    assert store.job(ws,job['id'])['state']=='completed'
    assert len(store.committed_candidates(job['id']))==3
    assert invoked[docs[0]]==1
    assert invoked[docs[1]]==1
    assert invoked[docs[2]]==1

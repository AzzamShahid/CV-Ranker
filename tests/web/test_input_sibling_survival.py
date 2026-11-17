"""A bad CV does not become Not Found or stop healthy independent siblings."""
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one
from cv_ranker.documents import DocumentError
from backend import engine_service


def test_unreadable_cv_is_incomplete_and_healthy_siblings_finish(tmp_path,monkeypatch):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    first=upload(client,headers,ws,'cv','First.txt','Skills: Python programming')
    bad=upload(client,headers,ws,'cv','Unreadable.txt','CV source marked for synthetic extractor failure')
    last=upload(client,headers,ws,'cv','Last.txt','Skills: Python programming')
    original=engine_service.evaluate_candidate
    def controlled(jd_path,cv_path,*args,**kwargs):
        if cv_path.read_text(encoding='utf8').startswith('CV source marked for synthetic'):
            raise DocumentError('Fictional corrupt document: no source assessment permitted')
        return original(jd_path,cv_path,*args,**kwargs)
    monkeypatch.setattr(engine_service,'evaluate_candidate',controlled)
    job=submit_candidate_job(client,headers,ws,approved,[first,bad,last],'bad-sibling')
    run_one(store,job)
    status=store.job(ws,job['id'])
    assert status['state']=='completed_with_errors'
    assert status['progress']==3
    report=store.report(ws,job['id'])
    rows={row['candidate_source']:row for row in report['candidates']}
    assert rows[first]['primary_score'] is not None
    assert rows[last]['primary_score'] is not None
    assert rows[bad]['primary_score'] is None
    assert rows[bad]['assessments']==[]
    assert all(row['candidate_source']!=bad or row['rank'] is None for row in report['candidates'])
    view=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/candidates/{bad}')
    assert view.status_code==200,view.text
    criteria=view.json()['final']['Criteria']
    assert all(c['Result']=='Assessment incomplete' for c in criteria)
    assert all(c['Result']!='Not Found' for c in criteria)

"""Synthetic multi-candidate job batch acceptance; domain logic runs in existing CVRanker."""
import pytest
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one

@pytest.mark.parametrize('count',[1,6,7,12,13])
def test_all_candidates_commit_beyond_six_item_boundary(tmp_path,count):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    ids=[upload(client,headers,ws,'cv',f'Synthetic_{i}.txt',
            f'Candidate reference {i}. Skills: Python programming.') for i in range(count)]
    job=submit_candidate_job(client,headers,ws,approved,ids,'batch-'+str(count))
    run_one(store,job)
    current=store.job(ws,job['id'])
    assert current['state'] in ('completed','completed_with_errors'),current
    assert current['progress']==count
    assert len(store.committed_candidates(job['id']))==count
    report=store.report(ws,job['id'])
    assert len(report['candidates'])==count
    assert {row['candidate_source'] for row in report['candidates']}==set(ids)
    history=store.events(ws,job['id'],0,200)
    assert len([item for item in history if item['kind']=='candidate_committed'])==count

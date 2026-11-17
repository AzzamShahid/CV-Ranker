"""Canonical read/export revisions and valid-null/zero distinctions."""
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one


def test_rankings_and_export_share_revision_and_candidate_identity(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,_=prepare_approved(store,client,headers,ws)
    first=upload(client,headers,ws,'cv','Applicant.txt','Skills: Python programming')
    second=upload(client,headers,ws,'cv','Applicant.txt','Experience: Dispatching parcels')
    job=submit_candidate_job(client,headers,ws,approval,[first,second],'projection-audit')
    run_one(store,job)
    snapshot=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}').json()
    ranks=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings').json()
    assert ranks['result_revision']==snapshot['result_revision']
    assert {r['candidate_id'] for r in ranks['items']}=={first,second}
    assert len(ranks['items'])==2
    details=[client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/candidates/{doc}').json()
             for doc in (first,second)]
    for i,doc in enumerate((first,second)):
        assert details[i]['candidate']['candidate_source']==doc
        assert len(details[i]['final']['Criteria'])==len(approval['body']['requirements'])
        assert all('Why' in row and 'Processing state' in row and 'Checkpoints' in row
                   for row in details[i]['final']['Criteria'])
        assert all(seg['segment_id'] for seg in details[i]['original_segments'])
    saved=client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/exports',headers=headers,
                      json={'revision':ranks['result_revision'],
                            'weight_revision':ranks['weight_revision']})
    assert saved.status_code==201,saved.text
    updated=client.put(f'/api/v1/workspaces/{ws}/weights',headers=headers,
        json={'revision':0,'weights':{'experience':0,'education':0,'jd':100}})
    assert updated.status_code==200,updated.text
    stale=client.post(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/exports',headers=headers,
                      json={'revision':ranks['result_revision'],
                            'weight_revision':ranks['weight_revision']})
    assert stale.status_code==409
    after=client.get(f'/api/v1/workspaces/{ws}/jobs/{job["id"]}/rankings').json()
    assert after['weight_revision']==1
    assert after['result_revision']==ranks['result_revision']
    assert {r['candidate_id'] for r in after['items']}=={first,second}

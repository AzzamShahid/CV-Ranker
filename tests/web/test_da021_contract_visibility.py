"""DA021 real API JD edit contract and full candidate visibility boundaries."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from backend.contracts import JDRowDTO
from backend.storage import json_dumps
from tests.web.test_api_worker import setup,workspace,upload,prepare_approved,submit_candidate_job,run_one


def test_da021_02_nullable_fractional_years_roundtrip(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,draft=prepare_approved(store,client,headers,ws)
    fetched=client.get(f'/api/v1/workspaces/{ws}/jd/drafts/{draft["id"]}')
    assert fetched.status_code==200,fetched.text
    first=fetched.json()['rows'][0]
    assert first['Minimum years'] is None
    assert JDRowDTO.model_validate(first).minimum_years is None
    omitted={k:v for k,v in first.items() if k!='Minimum years'}
    assert JDRowDTO.model_validate(omitted).minimum_years is None
    for num in (0,1,3.5,7.25):
        assert JDRowDTO.model_validate(first|{'Minimum years':num}).minimum_years==num
    for value in (-1,float('inf'),float('nan'),'three'):
        with pytest.raises(ValidationError):JDRowDTO.model_validate(first|{'Minimum years':value})
    # No invalid or unsupported years can be silently approved as real tenure.
    changed=first|{'Minimum years':3.5}
    result=client.post(f'/api/v1/workspaces/{ws}/jd/approve',headers=headers,
      json={'draft_id':draft['id'],'revision':draft['revision'],'rows':[changed]})
    assert result.status_code==422,result.text
    identical=client.post(f'/api/v1/workspaces/{ws}/jd/approve',headers=headers,
      json={'draft_id':draft['id'],'revision':draft['revision'],'rows':[first]})
    assert identical.status_code==200
    assert identical.json()['id']==approval['id']


def test_da021_12_api_change_approved_priority_returns_conflict(tmp_path):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approval,draft=prepare_approved(store,client,headers,ws)
    row=draft['rows'][0];row['Priority']='preferred' if row['Priority']!='preferred' else 'required'
    replay=client.post(f'/api/v1/workspaces/{ws}/jd/approve',headers=headers,
                       json={'draft_id':draft['id'],'revision':draft['revision'],'rows':[row]})
    assert replay.status_code==409,replay.text
    assert store.approval(ws,approval['id'])['body']==approval['body']


@pytest.mark.parametrize('count',[1,50,51,200])
def test_da021_07_later_page_and_filtered_candidate_visible(tmp_path,count):
    store,client,headers=setup(tmp_path);ws=workspace(client,headers)
    approved,_=prepare_approved(store,client,headers,ws)
    doc=upload(client,headers,ws,'cv','First Applicant.txt','Skills: Python programming')
    job=submit_candidate_job(client,headers,ws,approved,[doc],'candidate-page-boundary')
    run_one(store,job)
    report=store.report(ws,job['id'])
    sample=report['candidates'][0]
    candidates=[];ids=[]
    for index in range(count):
        uid=doc if index==0 else store.add_document(ws,'cv',f'Candidate-{index:03d}.txt','.txt',b'Fictional CV')['id']
        ids.append(uid)
        row={**sample,'candidate_source':uid,'candidate_name':
              ('LAST-PAGE-FILTER-TARGET.txt' if index==count-1 else 'Duplicate Applicant.txt')}
        candidates.append(row)
    report['candidates']=candidates
    with store.tx() as db:
        db.execute('UPDATE jobs SET result_json=?,result_revision=result_revision+1,progress=?,total=? WHERE id=?',
                   (json_dumps(report),count,count,job['id']))
    root=f'/api/v1/workspaces/{ws}/jobs/{job["id"]}'
    first=client.get(root+'/rankings?offset=0&limit=50')
    assert first.status_code==200,first.text
    assert first.json()['total']==count
    assert len(first.json()['items'])==min(50,count)
    last=client.get(root+'/rankings?offset=50&limit=50')
    assert last.status_code==200
    assert len(last.json()['items'])==max(0,min(50,count-50))
    query=client.get(root+'/rankings?search=LAST-PAGE-FILTER-TARGET&offset=0&limit=50')
    assert query.status_code==200,query.text
    assert query.json()['total']==1
    assert query.json()['items'][0]['candidate_id']==ids[-1]
    direct=client.get(root+'/candidates/'+ids[-1]+'/weighted')
    assert direct.status_code==200,direct.text
    assert direct.json()['candidate_id']==ids[-1]
    assert direct.json()['result']['candidate_id']==ids[-1]
    assert direct.json()['result_revision']==first.json()['result_revision']
    stale=client.get(root+'/rankings?offset=50&limit=50&expected_result_revision=1')
    assert stale.status_code==409

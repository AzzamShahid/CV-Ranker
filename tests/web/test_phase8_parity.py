"""Phase 8 feature parity tests: Focused Review, Semantic Shadow, Usage Metrics, and Retention Automation."""
import json
import os
import time
from pathlib import Path

os.environ['TEXTILEHR_TESTING'] = '1'

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.storage import Store, Conflict, NotFound
from worker.runner import process_claim


def setup(tmp_path):
    store = Store(tmp_path / 'data')
    client = TestClient(create_app(store, serve_frontend=False), base_url='http://testserver')
    auth = client.get('/api/v1/session')
    assert auth.status_code == 200, auth.text
    headers = {'Origin': 'http://testserver', 'X-CSRF-Token': auth.json()['csrf_token']}
    return store, client, headers


def create_ws(client, headers, title='Phase 8 Parity Test'):
    res = client.post('/api/v1/workspaces', json={'title': title}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()['id']


def upload_doc(client, headers, ws, kind, name, text):
    res = client.post(f'/api/v1/workspaces/{ws}/documents?kind={kind}',
                      files={'file': (name, text.encode('utf-8'), 'text/plain')},
                      headers=headers)
    assert res.status_code == 201, res.text
    return res.json()['id']


def run_job(store, job):
    claim = store.claim_job('test-worker')
    assert claim and claim[0] == job['id']
    process_claim(store, claim[0], 'test-worker', claim[1])


def prepare_assessment(store, client, headers, ws):
    jd_text = "Required:\n- Python development\n- Cloud infrastructure"
    cv_text = "Applicant Experience:\nWorked on Python development and data pipelines.\nCloud infrastructure with Docker."
    jd_id = upload_doc(client, headers, ws, 'jd', 'job_desc.txt', jd_text)
    cv_id = upload_doc(client, headers, ws, 'cv', 'candidate_cv.txt', cv_text)

    extract = client.post(f'/api/v1/workspaces/{ws}/jd/extraction-jobs',
                          headers=headers | {'Idempotency-Key': 'jd-extract-p8'},
                          json={'document_id': jd_id, 'use_llm': False, 'provider': 'ollama'})
    assert extract.status_code == 202
    run_job(store, extract.json())

    draft = store.report(ws, extract.json()['id'])
    details = client.get(f'/api/v1/workspaces/{ws}/jd/drafts/{draft["draft_id"]}').json()
    approved = client.post(f'/api/v1/workspaces/{ws}/jd/approve', headers=headers,
                           json={'draft_id': details['id'], 'revision': details['revision'], 'rows': details['rows']})
    assert approved.status_code == 200

    assess = client.post(f'/api/v1/workspaces/{ws}/assessment-jobs',
                         headers=headers | {'Idempotency-Key': 'assess-p8'},
                         json={'candidate_ids': [cv_id], 'approved_revision_id': approved.json()['id'],
                               'use_llm': False, 'unified': False, 'provider': 'ollama'})
    assert assess.status_code == 202
    run_job(store, assess.json())
    return assess.json()['id'], cv_id, approved.json()


def test_focused_review_workflow(tmp_path):
    store, client, headers = setup(tmp_path)
    ws = create_ws(client, headers)
    job_id, cv_id, approved = prepare_assessment(store, client, headers, ws)

    # 1. Inspect candidate details before focused review
    detail_before = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/candidates/{cv_id}')
    assert detail_before.status_code == 200
    requirements = detail_before.json()['requirements']
    assert len(requirements) >= 1
    target_req = requirements[0]['requirement_id']
    rev_before = detail_before.json()['result_revision']

    # 2. Execute explicit operator focused review
    review_res = client.post(
        f'/api/v1/workspaces/{ws}/jobs/{job_id}/candidates/{cv_id}/focused-review',
        headers=headers,
        json={'requirement_id': target_req, 'provider': 'ollama', 'use_llm': False}
    )
    assert review_res.status_code == 200, review_res.text
    data = review_res.json()
    assert data['candidate_id'] == cv_id
    assert data['requirement_id'] == target_req
    assert data['new_verdict'] in ('Found', 'Transferable', 'Not Found')
    assert data['result_revision'] == rev_before + 1
    assert len(data['explanation']) >= 12

    # 3. Verify audit history is preserved
    history_res = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/candidates/{cv_id}/review-history')
    assert history_res.status_code == 200
    items = history_res.json()['items']
    assert len(items) == 1
    assert items[0]['requirement_id'] == target_req
    assert items[0]['new_verdict'] == data['new_verdict']

    # 4. Verify candidate detail and rankings reflect canonical successor revision
    detail_after = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/candidates/{cv_id}')
    assert detail_after.json()['result_revision'] == data['result_revision']

    rankings = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/rankings')
    assert rankings.json()['result_revision'] == data['result_revision']


def test_semantic_shadow_diagnostics_no_scoring_change(tmp_path):
    store, client, headers = setup(tmp_path)
    ws = create_ws(client, headers)
    job_id, cv_id, _ = prepare_assessment(store, client, headers, ws)

    rankings_before = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/rankings').json()

    # 1. Run semantic shadow diagnostics
    shadow_res = client.post(
        f'/api/v1/workspaces/{ws}/jobs/{job_id}/semantic-shadow',
        headers=headers,
        json={'top_k': 5}
    )
    assert shadow_res.status_code == 200, shadow_res.text
    shadow = shadow_res.json()
    assert shadow['ready'] is True
    assert shadow['scoring_unchanged'] is True
    assert 'do NOT alter candidate scores' in shadow['notice']
    assert len(shadow['items']) >= 1

    # 2. Verify rankings remain strictly identical (zero score promotion)
    rankings_after = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/rankings').json()
    assert rankings_before['items'] == rankings_after['items']
    assert rankings_before['result_revision'] == rankings_after['result_revision']

    # 3. GET cached semantic shadow
    get_shadow = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/semantic-shadow')
    assert get_shadow.status_code == 200
    assert get_shadow.json()['ready'] is True


def test_usage_reporting_and_secret_redaction(tmp_path):
    store, client, headers = setup(tmp_path)
    ws = create_ws(client, headers)
    job_id, _, _ = prepare_assessment(store, client, headers, ws)

    usage_res = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}/usage')
    assert usage_res.status_code == 200, usage_res.text
    usage = usage_res.json()
    assert usage['job_id'] == job_id
    assert usage['provider'] == 'ollama'
    assert 'estimated_cost_usd' in usage
    assert 'cost_label' in usage
    assert 'api_key' not in str(usage)
    assert 'secret' not in str(usage).casefold()


def test_retention_policy_and_reference_integrity(tmp_path):
    store, client, headers = setup(tmp_path)
    ws = create_ws(client, headers)
    job_id, cv_id, _ = prepare_assessment(store, client, headers, ws)

    # 1. Query retention summary
    summary = client.get(f'/api/v1/workspaces/{ws}/retention?days=30').json()
    assert summary['workspace_id'] == ws
    assert summary['protected_active_jobs'] == 0
    assert summary['protected_unknown_delivery_jobs'] == 0

    # 2. Cannot delete referenced CV document directly
    del_doc = client.request('DELETE', f'/api/v1/workspaces/{ws}/documents/{cv_id}',
                             headers=headers, json={'confirmation': 'DELETE'})
    assert del_doc.status_code == 409

    # 3. Retention purge with 0 days (or 1 day) cleans up eligible completed work safely
    purge = client.post(f'/api/v1/workspaces/{ws}/retention/purge',
                        headers=headers, json={'retention_days': 1})
    assert purge.status_code == 200
    data = purge.json()
    assert 'purged_jobs' in data
    assert 'purged_documents' in data

    # 4. CLI purge command integration
    from scripts.data_backup import purge as cli_purge
    cli_purge(store.root, days=1, workspace=ws)


def test_historical_import_matrix(tmp_path):
    from cv_ranker.schemas import RankingReport
    store, client, headers = setup(tmp_path)
    ws = create_ws(client, headers)
    job_id, cv_id, _ = prepare_assessment(store, client, headers, ws)

    # Export a valid report
    status = client.get(f'/api/v1/workspaces/{ws}/jobs/{job_id}').json()
    exp = client.post(f'/api/v1/workspaces/{ws}/jobs/{job_id}/exports', headers=headers,
                      json={'revision': status['result_revision'], 'weight_revision': 0})
    assert exp.status_code == 201
    zip_bytes = client.get(f'/api/v1/workspaces/{ws}/exports/{exp.json()["id"]}/download').content

    # Matrix 1: Valid ZIP import
    zip_import = client.post(f'/api/v1/workspaces/{ws}/historical-reports', headers=headers,
                             files={'file': ('historical_run.zip', zip_bytes, 'application/zip')})
    assert zip_import.status_code == 201, zip_import.text
    assert zip_import.json()['source_name'] == 'historical_run.zip'

    # Matrix 2: Valid JSON report import
    report = store.report(ws, job_id)
    json_import = client.post(f'/api/v1/workspaces/{ws}/historical-reports', headers=headers,
                              files={'file': ('historical_audit.json', json.dumps(report).encode(), 'application/json')})
    assert json_import.status_code == 201

    # Matrix 3: Incompatible schema / invalid file rejected
    bad_import = client.post(f'/api/v1/workspaces/{ws}/historical-reports', headers=headers,
                             files={'file': ('corrupt.json', b'{"invalid": "data"}', 'application/json')})
    assert bad_import.status_code == 422

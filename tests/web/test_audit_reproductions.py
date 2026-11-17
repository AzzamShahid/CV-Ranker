"""Deterministic reproduction tests for findings DA-A01 through DA-A10.

These tests reproduce the specific defects documented in TextileHR_Antigravity_Deep_Audit.md
and ensure that regressions fail on the unpatched codebase and pass once properly repaired.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

os.environ['TEXTILEHR_TESTING'] = '1'

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.storage import Store, Conflict, NotFound
from backend.engine_service import focused_review_candidate, run_semantic_shadow_diagnostic
from cv_ranker.schemas import (
    CandidateResult, EvidenceCitation, RankingReport,
    RequirementAssessment, RequirementConstraint, ValidatedRequirement
)


def setup_test_env(tmp_path):
    assert 'tmp' in str(tmp_path).lower() or 'temp' in str(tmp_path).lower() or 'pytest' in str(tmp_path).lower()
    store = Store(tmp_path / 'data')
    client = TestClient(create_app(store, serve_frontend=False), base_url='http://testserver')
    auth = client.get('/api/v1/session')
    assert auth.status_code == 200
    headers = {'Origin': 'http://testserver', 'X-CSRF-Token': auth.json()['csrf_token']}
    return store, client, headers


def _req(rid: str, name: str, priority: str = "required") -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id=rid, name=name, priority=priority, jd_evidence=name,
        constraint=RequirementConstraint(kind="skill", origin="source_rules", requires_review=False),
    )


def _assessment(rid: str, status: str = "not_matched", unified: str = "Not Found") -> RequirementAssessment:
    return RequirementAssessment(
        requirement_id=rid, status=status, unified_status=unified,
        reason=f"Initial assessment for {rid}.",
        evidence_segments=[], evidence_ids=[],
    )


def make_test_report(requirements, candidates):
    return RankingReport(
        job_description_source="test_jd.txt",
        jd_validation_mode="test",
        yake_candidates=[],
        requirements=requirements,
        candidates=candidates,
    )


def test_reproduce_da_a01_negation_not_promoted(tmp_path):
    """DA-A01: Offline review substring match turns 'I have no experience in Python development' into Found.
    
    Acceptance: Negated experience must NOT be promoted to 'Found'.
    """
    req_py = _req('R001', 'Python development')
    cand_assessments = [_assessment('R001', 'not_matched', 'Not Found')]
    cand = CandidateResult(
        candidate_name='Candidate Negated',
        candidate_source='cand-negated',
        rank=1,
        primary_score=0.0,
        assessments=cand_assessments,
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_py], [cand])
    
    # Candidate source ledger explicitly contains negated experience
    segments = [
        {'segment_id': 's1', 'section': 'experience', 'text': 'I have no experience in Python development.'}
    ]
    job_settings = {'use_llm': False, 'provider': 'ollama'}
    
    outcome = focused_review_candidate(
        report.model_dump(mode='json'),
        'cand-negated',
        'R001',
        segments,
        job_settings,
    )
    
    # Under defect DA-A01, 'Python development' in 'I have no experience in Python development'
    # matches line 162 in engine_service.py and outcome['new_verdict'] becomes 'Found'.
    # Acceptance criteria: Must NOT be 'Found'.
    assert outcome['new_verdict'] != 'Found', f"Defect DA-A01: Negation promoted to {outcome['new_verdict']}"
    assert outcome['new_verdict'] == 'Not Found'


def test_reproduce_da_a02_concurrent_reviews_conflict(tmp_path):
    """DA-A02: Concurrent focused reviews read same report, overwrite each other's changes.
    
    Acceptance: Two reviews of different requirements on the same candidate/report must both survive
    or return a revision conflict rather than silently dropping one of the reviewed verdicts.
    """
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('DA-A02 Workspace')['id']
    doc = store.add_document(ws, 'cv', 'applicant.txt', '.txt', b'Skills: 5 years Python development and SQL database')
    doc_id = doc['id']
    
    req_1 = _req('R001', 'Python development')
    req_2 = _req('R002', 'SQL database')
    cand_assessments = [
        _assessment('R001', 'not_matched', 'Not Found'),
        _assessment('R002', 'not_matched', 'Not Found'),
    ]
    cand = CandidateResult(
        candidate_name='Candidate A',
        candidate_source=doc_id,
        rank=1,
        primary_score=0.0,
        assessments=cand_assessments,
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_1, req_2], [cand])
    
    job = store.make_job(ws, 'assess', {'candidate_ids': [doc_id], 'settings': {'use_llm': False}}, 'idem-da-a02')
    job_id = job['id']
    with store.tx() as db:
        db.execute("UPDATE jobs SET state='completed', result_json=?, result_revision=1 WHERE id=?",
                   (json.dumps(report.model_dump(mode='json')), job_id))
        db.execute("INSERT INTO candidate_results VALUES(?,?,?,?,?,?)",
                   (job_id, doc_id, 0, json.dumps(cand.model_dump(mode='json')),
                    json.dumps({'segments': [{'segment_id': 's1', 'section': 'skills', 'text': '5 years Python development and SQL database'}]}),
                    time.time()))
    
    # Review 1 executes against the base report revision (revision 1)
    res1 = store.execute_focused_review(ws, job_id, doc_id, 'R001', provider='ollama', use_llm=False)
    assert res1['new_verdict'] == 'Found'
    
    # Now simulate a concurrent second review that was started against the SAME base revision (revision 1)
    # In unpatched code, execute_focused_review has no expected_result_revision check and reads current DB,
    # but if a caller supplies expected_result_revision=1 or runs concurrently, it overwrites revision 2 with stale state.
    # To demonstrate DA-A02: if caller requests review expecting revision 1, it must raise Conflict:
    if 'expected_result_revision' in store.execute_focused_review.__code__.co_varnames:
        with pytest.raises(Conflict, match='revision'):
            store.execute_focused_review(ws, job_id, doc_id, 'R002', provider='ollama', use_llm=False, expected_result_revision=1)
    else:
        # On unpatched code, expected_result_revision does not even exist!
        pytest.fail("Defect DA-A02: execute_focused_review lacks expected_result_revision CAS parameter")


def test_reproduce_da_a04_shadow_empty_retrieval(tmp_path):
    """DA-A04: Empty retrieval produces hardcoded similarity=0.85 and invented positive findings.
    
    Acceptance: Empty retrieval must produce empty findings (no fabricated 0.85 similarities).
    """
    class EmptyRetrievalRanker:
        def __init__(self, *args, **kwargs):
            pass
        def plan_jd_capabilities(self, report):
            return {}
        def run_semantic_shadow(self, *args, **kwargs):
            return []  # Empty retrieval matches
            
    req = _req('R001', 'Textile Quality Control')
    cand = CandidateResult(
        candidate_name='Candidate A',
        candidate_source='cand-001',
        rank=1,
        primary_score=0.0,
        assessments=[],
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req], [cand])
    
    res = run_semantic_shadow_diagnostic(
        report.model_dump(mode='json'),
        top_k=5,
        cache_dir=tmp_path,
        ranker_factory=EmptyRetrievalRanker,
    )
    
    # Under defect DA-A04, lines 269-277 generate items with similarity=0.85 regardless of retrieval
    # Acceptance: No fabricated 0.85 similarity findings when retrieval is empty
    for item in res.get('items', []):
        assert item.get('similarity', 0.0) != 0.85, f"Defect DA-A04: Fabricated similarity 0.85 on empty retrieval for {item}"
    assert len(res.get('items', [])) == 0 or all(it.get('similarity', 0.0) == 0.0 for it in res['items'])


def test_reproduce_da_a05_shadow_failure_handling(tmp_path):
    """DA-A05: Embedding exception caught and returned as ready=True with error in finding.
    
    Acceptance: Operational failure must report ready=False with operational error status.
    """
    class FailingRanker:
        def __init__(self, *args, **kwargs):
            pass
        def plan_jd_capabilities(self, report):
            raise RuntimeError("Embedding model offline or unavailable")
            
    req = _req('R001', 'Textile Quality Control')
    cand = CandidateResult(
        candidate_name='Candidate A',
        candidate_source='cand-001',
        rank=1,
        primary_score=0.0,
        assessments=[],
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req], [cand])
    
    res = run_semantic_shadow_diagnostic(
        report.model_dump(mode='json'),
        top_k=5,
        cache_dir=tmp_path,
        ranker_factory=FailingRanker,
    )
    
    # Under defect DA-A05, lines 278-290 catch all exceptions and return ready=True
    # Acceptance: ready must be False when an operational failure occurs
    assert res['ready'] is False, f"Defect DA-A05: Operational failure returned ready=True: {res}"


def test_reproduce_da_a06_fresh_cv_survives_retention(tmp_path):
    """DA-A06: Fresh CV document deleted by retention purge due to missing age check on documents.
    
    Acceptance: A fresh unreferenced CV (< retention_days old) must survive purge_retention.
    """
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('DA-A06 Workspace')['id']
    
    # Add a fresh CV document created right now
    doc = store.add_document(ws, 'cv', 'fresh_applicant.txt', '.txt', b'Skills: Textile spinning')
    doc_id = doc['id']
    
    # Run a 30-day retention purge
    res = store.purge_retention(ws, retention_days=30)
    
    # Under defect DA-A06, purge_retention deletes this document (purged_documents=1)
    # Acceptance: purged_documents must be 0, and doc must still exist
    assert res['purged_documents'] == 0, f"Defect DA-A06: Fresh document was deleted by 30-day purge: {res}"
    with store.connect() as db:
        remaining = db.execute("SELECT count(*) FROM documents WHERE id=?", (doc_id,)).fetchone()[0]
        assert remaining == 1, "Fresh document should still exist in database"


def test_reproduce_da_a07_preview_matches_purge(tmp_path):
    """DA-A07: Retention preview hardcodes eligible_documents=0 disagreeing with purge.
    
    Acceptance: get_retention_summary eligible_documents must reflect the actual deletion plan.
    """
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('DA-A07 Workspace')['id']
    
    # Add an old orphan CV document (older than 30 days)
    doc = store.add_document(ws, 'cv', 'old_orphan.txt', '.txt', b'Skills: Weaving')
    doc_id = doc['id']
    old_time = time.time() - (45 * 86400)  # 45 days ago
    with store.tx() as db:
        old_iso = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(old_time))
        db.execute("UPDATE documents SET created=? WHERE id=?", (old_iso, doc_id))
    
    preview = store.get_retention_summary(ws, default_days=30)
    # Under defect DA-A07, preview['eligible_documents'] is hardcoded to 0
    # Acceptance: preview['eligible_documents'] must equal 1 (since 1 doc is 45 days old)
    assert preview['eligible_documents'] == 1, f"Defect DA-A07: Preview returned eligible_documents={preview['eligible_documents']}, expected 1"
    
    purge_result = store.purge_retention(ws, retention_days=30)
    assert purge_result['purged_documents'] == preview['eligible_documents'], "Purge count must equal preview count"


def test_reproduce_da_a08_delete_assessment_and_workspace(tmp_path):
    """DA-A08: delete_assessment and delete_workspace raise IntegrityError when child rows exist.
    
    Acceptance: Assessment and workspace deletion must cleanly remove or cascade child rows in
    focused_reviews, semantic_shadows, and job_metrics without IntegrityError.
    """
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('DA-A08 Workspace')['id']
    doc = store.add_document(ws, 'cv', 'cand_c1.txt', '.txt', b'Skills: Weaving')
    doc_id = doc['id']
    
    job = store.make_job(ws, 'assess', {'candidate_ids': [doc_id]}, 'idem-da-a08')
    job_id = job['id']
    
    # Put job in terminal completed state
    with store.tx() as db:
        db.execute("UPDATE jobs SET state='completed' WHERE id=?", (job_id,))
        db.execute("INSERT INTO focused_reviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                   ('fr-1', ws, job_id, doc_id, 'R1', 'Not Found', 'Found', 'Explanation', '[]', time.strftime('%Y-%m-%d %H:%M:%S')))
        db.execute("INSERT INTO semantic_shadows VALUES(?,?,?,?,?,?)",
                   ('ss-1', ws, job_id, '[]', '[]', time.strftime('%Y-%m-%d %H:%M:%S')))
        db.execute("INSERT INTO job_metrics VALUES(?,?,?,?)",
                   (job_id, ws, json.dumps({'actual_model_request_attempts': 3}), time.strftime('%Y-%m-%d %H:%M:%S')))
    
    # Under defect DA-A08, delete_assessment raises sqlite3.IntegrityError: FOREIGN KEY constraint failed
    # Acceptance: delete_assessment must succeed without raising IntegrityError
    try:
        store.delete_assessment(ws, job_id)
    except sqlite3.IntegrityError as err:
        pytest.fail(f"Defect DA-A08: delete_assessment failed with IntegrityError: {err}")
        
    # Re-insert job with child rows and test delete_workspace
    doc2 = store.add_document(ws, 'cv', 'cand_c2.txt', '.txt', b'Skills: Dyeing')
    doc2_id = doc2['id']
    job2 = store.make_job(ws, 'assess', {'candidate_ids': [doc2_id]}, 'idem-da-a08-2')
    job2_id = job2['id']
    with store.tx() as db:
        db.execute("UPDATE jobs SET state='completed' WHERE id=?", (job2_id,))
        db.execute("INSERT INTO focused_reviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                   ('fr-2', ws, job2_id, doc2_id, 'R1', 'Not Found', 'Found', 'Explanation', '[]', time.strftime('%Y-%m-%d %H:%M:%S')))
        db.execute("INSERT INTO semantic_shadows VALUES(?,?,?,?,?,?)",
                   ('ss-2', ws, job2_id, '[]', '[]', time.strftime('%Y-%m-%d %H:%M:%S')))
        db.execute("INSERT INTO job_metrics VALUES(?,?,?,?)",
                   (job2_id, ws, json.dumps({'actual_model_request_attempts': 2}), time.strftime('%Y-%m-%d %H:%M:%S')))
                   
    # Under defect DA-A08, delete_workspace raises sqlite3.IntegrityError: FOREIGN KEY constraint failed
    try:
        store.delete_workspace(ws)
    except sqlite3.IntegrityError as err:
        pytest.fail(f"Defect DA-A08: delete_workspace failed with IntegrityError: {err}")


def test_reproduce_da_a09_metrics_accumulation(tmp_path):
    """DA-A09: Job metrics JSON overwritten with latest candidate instead of accumulating across candidates.
    
    Acceptance: actual_model_request_attempts must accumulate across candidates (e.g. 3 + 5 = 8).
    """
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('DA-A09 Workspace')['id']
    doc1 = store.add_document(ws, 'cv', 'c1.txt', '.txt', b'Skills: Yarn')
    doc2 = store.add_document(ws, 'cv', 'c2.txt', '.txt', b'Skills: Loom')
    
    job = store.make_job(ws, 'assess', {'candidate_ids': [doc1['id'], doc2['id']], 'settings': {'provider': 'ollama', 'model_name': 'qwen2.5:3b'}}, 'idem-da-a09')
    job_id = job['id']
    
    claim = store.claim_job('worker-1')
    assert claim and claim[0] == job_id
    fence = claim[1]
    
    # Candidate 1: 3 attempts, 100 tokens
    metrics_c1 = {
        'actual_model_request_attempts': 3,
        'logical_model_calls': 3,
        'provider_reported_tokens': {'prompt_tokens': 70, 'completion_tokens': 30, 'total_tokens': 100},
    }
    report_stub = {'candidates': [{'candidate_source': doc1['id']}], 'requirements': []}
    store.commit_candidate(job_id, 'worker-1', fence, doc1['id'], 0, {'candidate_source': doc1['id']}, [], report_stub, metrics=metrics_c1)
    
    # Candidate 2: 5 attempts, 200 tokens
    metrics_c2 = {
        'actual_model_request_attempts': 5,
        'logical_model_calls': 5,
        'provider_reported_tokens': {'prompt_tokens': 140, 'completion_tokens': 60, 'total_tokens': 200},
    }
    report_stub['candidates'].append({'candidate_source': doc2['id']})
    store.commit_candidate(job_id, 'worker-1', fence, doc2['id'], 1, {'candidate_source': doc2['id']}, [], report_stub, metrics=metrics_c2)
    
    job_metrics = store.get_job_metrics(ws, job_id)
    # Under defect DA-A09, job_metrics['actual_model_request_attempts'] is 5 (the second candidate's value), not 8
    # Acceptance: actual_model_request_attempts must be 8 (3 + 5)
    assert job_metrics['actual_model_request_attempts'] == 8, (
        f"Defect DA-A09: Metric replaced rather than accumulated. Got {job_metrics['actual_model_request_attempts']}, expected 8"
    )
    assert job_metrics['token_usage']['total_tokens'] == 300, (
        f"Defect DA-A09: Tokens replaced rather than accumulated. Got {job_metrics['token_usage']['total_tokens']}, expected 300"
    )


def test_reproduce_da_a15_uncertain_outcome_schema_compliance(tmp_path):
    """Section 08: Fallback review on ambiguous text ('Currently learning Python') must NOT crash FocusedJudgment schema.
    
    Acceptance: Must not raise Pydantic ValidationError. Must preserve prior verdict without inventing 4th verdict.
    """
    req_py = _req('R001', 'Python development')
    cand_assessments = [_assessment('R001', 'matched', 'Found')]
    cand = CandidateResult(
        candidate_name='Candidate Learning',
        candidate_source='cand-learning',
        rank=1,
        primary_score=100.0,
        assessments=cand_assessments,
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_py], [cand])
    
    # Ambiguous / uncertain mention
    segments = [
        {'segment_id': 's1', 'section': 'experience', 'text': 'Currently learning Python development.'}
    ]
    job_settings = {'use_llm': False, 'provider': 'ollama'}
    
    outcome = focused_review_candidate(
        report.model_dump(mode='json'),
        'cand-learning',
        'R001',
        segments,
        job_settings,
    )
    
    # Prior verdict 'Found' should be preserved when deterministic review is ambiguous
    assert outcome['new_verdict'] == 'Found'
    assert 'ambiguous' in outcome['explanation'].lower() or 'preserved' in outcome['explanation'].lower()


def test_reproduce_da_a16_missing_source_input_not_evidenced(tmp_path):
    """Section 09: Missing candidate source segments must not fabricate 'Not Found' substantive decision.
    
    Acceptance: Must raise ValueError when no readable resume segments exist.
    """
    req_py = _req('R001', 'Python development')
    cand_assessments = [_assessment('R001', 'not_matched', 'Not Found')]
    cand = CandidateResult(
        candidate_name='Candidate Empty',
        candidate_source='cand-empty',
        rank=1,
        primary_score=0.0,
        assessments=cand_assessments,
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_py], [cand])
    
    with pytest.raises(ValueError, match="no readable resume segments"):
        focused_review_candidate(
            report.model_dump(mode='json'),
            'cand-empty',
            'R001',
            [],
            {'use_llm': False},
        )


def test_reproduce_da_a17_semantic_shadow_nullable_similarity_and_no_synthesis(tmp_path):
    """Section 10-12: Semantic diagnostics must not crash on nullable similarity or synthesize fake files.
    """
    req_py = _req('R001', 'Python development')
    cv_file = tmp_path / "candidate.txt"
    cv_file.write_text("Experienced Python and FastAPI backend developer.", encoding="utf-8")
    cand = CandidateResult(
        candidate_name='Candidate Remote',
        candidate_source=str(cv_file),
        rank=1,
        primary_score=100.0,
        assessments=[_assessment('R001', 'matched', 'Found')],
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_py], [cand])
    
    class MockRetrievalRanker:
        def __init__(self, *args, **kwargs):
            pass
        def run_semantic_shadow(self, *args, **kwargs):
            return {
                'candidates': [{
                    'candidate_id': str(cv_file),
                    'candidate_name': 'Candidate Remote',
                    'hits_by_requirement': {
                        'R001': [
                            {'cosine_similarity': None, 'similarity': 0.88, 'segment_id': 's1'},
                            {'cosine_similarity': 0.92, 'similarity': None, 'segment_id': 's2'},
                            {'cosine_similarity': None, 'similarity': None, 'segment_id': 's3'},
                        ]
                    }
                }]
            }

    result = run_semantic_shadow_diagnostic(
        report.model_dump(mode='json'),
        cache_dir=tmp_path / 'cache',
        ranker_factory=MockRetrievalRanker,
    )
    assert result['ready'] is True
    assert len(result['items']) == 2
    assert result['items'][0]['similarity'] == 0.88
    assert result['items'][1]['similarity'] == 0.92
    assert result['items'][0]['candidate_id'] == str(cv_file)


def test_reproduce_da_e04_review_operations_and_recovery(tmp_path):
    """E04: Review operations must be durable in `operations` table and replay-safe across calls and crashes."""
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('E04 Durable Review')
    ws_id = ws['id']
    doc = store.add_document(ws_id, 'cv', 'cand_1.txt', '.txt', b'Proficient with Python and Django web frameworks.')
    cand_id = doc['id']
    req_py = _req('R001', 'Python development')
    cand = CandidateResult(
        candidate_name='Ayesha Khan',
        candidate_source=cand_id,
        rank=1,
        primary_score=50.0,
        assessments=[_assessment('R001', 'not_matched', 'Not Found')],
        errors=[],
        evaluation_mode='fallback_exact',
    )
    report = make_test_report([req_py], [cand])
    segments = [{'segment_id': 's1', 'text': 'Proficient with Python and Django web frameworks.', 'section': 'skills'}]

    # Seed job and candidate result
    job = store.make_job(ws_id, 'assess', {'settings': {'provider': 'ollama', 'use_llm': False}}, 'key_sub_1')
    job_id = job['id']
    with store.tx() as db:
        db.execute('UPDATE jobs SET state="paused", result_json=?, result_revision=1, progress=1, total=1 WHERE id=?',
                   (json.dumps(report.model_dump(mode="json")), job_id))
        db.execute('INSERT INTO candidate_results VALUES (?, ?, 1, ?, ?, ?)',
                   (job_id, cand_id, json.dumps(cand.model_dump(mode="json")), json.dumps({'segments': segments}), '2026-11-17T00:00:00Z'))

    # 1. Execute focused review with explicit idempotency key
    res1 = store.execute_focused_review(ws_id, job_id, cand_id, 'R001', idempotency_key='rev-op-1')
    assert res1['result_revision'] == 2
    assert res1['new_verdict'] in ('Found', 'Not Found', 'Transferable')

    # Verify operations table record
    with store.connect() as db:
        op = db.execute('SELECT * FROM operations WHERE workspace_id=? AND idempotency_key=?', (ws_id, 'rev-op-1')).fetchone()
        assert op is not None
        assert op['state'] == 'completed'
        assert op['committed_revision'] == 2

    # 2. Replay with the same idempotency key must return the exact saved response without re-executing or bumping revision
    res2 = store.execute_focused_review(ws_id, job_id, cand_id, 'R001', idempotency_key='rev-op-1')
    assert res2['result_revision'] == 2
    assert res2['new_verdict'] == res1['new_verdict']

    # Check job revision is still 2 (not bumped to 3)
    job = store.job(ws_id, job_id)
    assert job['result_revision'] == 2

    # 3. Simulate crash after response_saved: insert operation with response_saved
    saved_outcome = {
        'updated_report': report.model_dump(mode='json'),
        'updated_candidate': cand.model_dump(mode='json'),
        'prior_verdict': 'Not Found',
        'new_verdict': 'Transferable',
        'explanation': 'Recovered from saved response without second model call.',
        'citations': [{'Segment': 's1', 'Text': 'Proficient with Python', 'Section': 'skills', 'Validated against CV': True}],
    }
    with store.tx() as db:
        db.execute('''INSERT INTO operations (
            id, workspace_id, job_id, operation_type, candidate_id, requirement_id,
            idempotency_key, request_fingerprint, base_result_revision, state,
            attempt_count, resolved_provider, resolved_model, saved_response_json, created, updated
        ) VALUES ('crash-op', ?, ?, 'focused_review', ?, 'R001', 'rev-op-2', 'fp2', 2, 'response_saved', 1, 'ollama', 'qwen', ?, '2026-11-17T00:00:00Z', '2026-11-17T00:00:00Z')''',
        (ws_id, job_id, cand_id, json.dumps(saved_outcome)))

    # Re-running with rev-op-2 must recover saved response and commit revision 3
    res3 = store.execute_focused_review(ws_id, job_id, cand_id, 'R001', idempotency_key='rev-op-2')
    assert res3['result_revision'] == 3
    assert res3['new_verdict'] == 'Transferable'
    assert 'Recovered from saved response' in res3['explanation']


def test_reproduce_da_e05_replay_safe_usage_accounting(tmp_path):
    """E05: Usage events must be deduplicated via `usage_events` primary key, preventing duplicate billing on retry."""
    store, client, headers = setup_test_env(tmp_path)
    ws = store.create_workspace('E05 Usage Deduplication')
    ws_id = ws['id']
    job = store.make_job(ws_id, 'assess', {'settings': {'provider': 'openrouter', 'openrouter_model': 'google/gemini-2.5-flash-lite'}}, 'key_u')
    job_id = job['id']

    # Record first event
    first_ok = store.record_usage_event(
        job_id=job_id, workspace_id=ws_id, event_id='event:cand1:assess',
        stage='candidate_assessment', provider='openrouter', model='google/gemini-2.5-flash-lite',
        candidate_id='cand1', logical_calls=1, request_attempts=1,
        prompt_tokens=500, completion_tokens=150, total_tokens=650, is_unknown_tokens=False
    )
    assert first_ok is True

    # Replaying the exact same event must be ignored (idempotent)
    second_ok = store.record_usage_event(
        job_id=job_id, workspace_id=ws_id, event_id='event:cand1:assess',
        stage='candidate_assessment', provider='openrouter', model='google/gemini-2.5-flash-lite',
        candidate_id='cand1', logical_calls=1, request_attempts=1,
        prompt_tokens=500, completion_tokens=150, total_tokens=650, is_unknown_tokens=False
    )
    assert second_ok is False

    # Metrics should show exactly 1 call and 650 tokens (not 2 calls / 1300 tokens!)
    metrics = store.get_job_metrics(ws_id, job_id)
    assert metrics['logical_model_calls'] == 1
    assert metrics['actual_model_request_attempts'] == 1
    assert metrics['token_usage']['prompt_tokens'] == 500
    assert metrics['token_usage']['completion_tokens'] == 150
    assert metrics['token_usage']['total_tokens'] == 650
    assert metrics['preserved_unknown'] is False
    assert metrics['estimated_cost_usd'] is not None

    # Now add an event with unknown tokens
    store.record_usage_event(
        job_id=job_id, workspace_id=ws_id, event_id='event:cand2:assess',
        stage='candidate_assessment', provider='openrouter', model='google/gemini-2.5-flash-lite',
        candidate_id='cand2', logical_calls=1, request_attempts=1,
        prompt_tokens=None, completion_tokens=None, total_tokens=None, is_unknown_tokens=True
    )
    metrics2 = store.get_job_metrics(ws_id, job_id)
    assert metrics2['logical_model_calls'] == 2
    assert metrics2['preserved_unknown'] is True
    assert metrics2['token_usage']['total_tokens'] is None


def test_reproduce_da_e06_recoverable_physical_cleanups(tmp_path):
    """E06: Unlink failures (e.g. Windows file lock) must persist in `pending_cleanups` and be retried on restart."""
    store, client, headers = setup_test_env(tmp_path)
    file_path = store.upload_root / 'locked_file.txt'
    file_path.write_text('content', encoding='utf-8')

    # Simulate an error by making unlink raise an OSError
    from unittest.mock import patch
    with patch.object(Path, 'unlink', side_effect=PermissionError('The process cannot access the file because it is being used by another process')):
        res = store._safe_unlink(store.upload_root, 'locked_file.txt')
        assert res is False

    # Pending cleanups table must contain the record
    cleanups = store.list_pending_cleanups()
    assert len(cleanups) == 1
    assert cleanups[0]['stored_name'] == 'locked_file.txt'
    assert cleanups[0]['attempts'] >= 1
    assert 'being used by another process' in cleanups[0]['last_error']

    # Now simulate file being freed and running process_pending_cleanups()
    retried = store.process_pending_cleanups()
    assert retried == 1
    assert not file_path.exists()
    assert len(store.list_pending_cleanups()) == 0



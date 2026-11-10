"""V4.6 supervisor release: offline reproductions of real October 2026 faults.

No API keys, network calls, or personal resumes are needed. The sample PDF is
explicitly fictional and exercises the actual PDF extraction/segment pipeline.
"""

import json
from pathlib import Path
from urllib.error import HTTPError

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.fallback import fallback_requirements
from cv_ranker.documents import extract_text
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.llm import OpenRouterHTTPError, StructuredLLM
from cv_ranker.pipeline import CVRanker
from cv_ranker.qualification_validation import apply_qualification_checks, check_qualification
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import RankingReport, RequirementAssessment, ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.cache import SQLiteVectorCache
from cv_ranker.semantic.core import ShadowRetriever
from cv_ranker.semantic.embedding import EmbeddingError, OllamaEmbeddingGemma
from cv_ranker.ui.semantic_workflow import semantic_failure_message
from cv_ranker.ui.semantic_workflow import run_semantic_review


SARA = Path('sample_data/applied_ai_documents/pdf/03_sara_functional_transfer.pdf')
EXPERIENCE = ('Minimum 3 years of relevant professional experience developing or '
              'delivering AI, machine-learning, deep-learning, or LLM-powered software.')
DEGREE = "Completed Bachelor's degree in Computer Science."


def _requirement(statement, number=1):
    item = ValidatedRequirement(requirement_id=f'R{number:03d}', name=statement,
                                jd_evidence=statement, priority='required')
    return item.model_copy(update={'constraint': classify_requirement(item, statement)})


def test_actual_sara_pdf_reports_four_relevant_years_with_cited_source():
    source = extract_text(SARA)
    req = _requirement(EXPERIENCE)
    assert req.constraint.subject is None  # "relevant professional" is NOT a skill
    check = check_experience(req, source, segment_resume(source))
    assert check.outcome == 'sufficient', check.explanation
    assert any(c.lower_years == 4 and 'LLM' in c.quote for c in check.claims)
    rows, _, _ = apply_experience_checks(requirements=[req],
                                        assessments=[RequirementAssessment(requirement_id='R001', status='not_matched')],
                                        resume_text=source)
    assert rows[0].status == 'matched'
    assert rows[0].evidence_ids
    assert 'four years' in rows[0].evidence.casefold()


def test_full_pipeline_does_not_erase_sufficient_experience_as_complex_review():
    files = Path('sample_data/applied_ai_documents')
    report = CVRanker(use_llm=False).run(files / 'jd/Applied_AI_ML_Engineer_Updated_JD.txt',
                                        [files / 'pdf/03_sara_functional_transfer.pdf',
                                         files / 'pdf/10_farhan_under_3_years.pdf'])
    rows = {c.candidate_name: c.assessments[0] for c in report.candidates}
    sara = rows['03_sara_functional_transfer.pdf']
    farhan = rows['10_farhan_under_3_years.pdf']
    assert sara.status == 'matched' and sara.experience_check.outcome == 'sufficient'
    assert farhan.status == 'not_matched' and farhan.experience_check.outcome == 'insufficient'


def test_bundled_supervisor_jd_includes_degree_and_exact_denominators():
    jd = Path('sample_data/applied_ai_supervisor_jd.txt').read_text(encoding='utf-8')
    frozen = fallback_requirements(jd, [], 30)
    assert len(frozen) == 18
    assert sum(item.priority == 'required' for item in frozen) == 11
    assert sum(item.priority == 'preferred' for item in frozen) == 7
    assert any('Bachelor' in item.name and item.priority == 'required' for item in frozen)


def test_actual_sara_pdf_bs_computer_science_found_not_hidden_under_projects():
    source = extract_text(SARA)
    segments = segment_resume(source)
    assert next(s.section for s in segments if 'BS Computer Science' in s.text) == 'education'
    req = _requirement(DEGREE, 2)
    check = check_qualification(req, source, segments)
    assert check.outcome == 'satisfied', check.explanation
    rows, _, _ = apply_qualification_checks(requirements=[req],
                                           assessments=[RequirementAssessment(requirement_id='R002', status='not_matched')],
                                           resume_text=source)
    assert rows[0].status == 'matched'
    assert any('BS Computer Science' in citation.text for citation in rows[0].evidence_segments)


@pytest.mark.parametrize('resume', [
    'PROFESSIONAL PROFILE\n4 years of sales experience.\nSKILLS\nLLM integrations.',
    'PROFESSIONAL PROFILE\nProfessional experience: 4 years.\nSKILLS\nAI, NLP, machine learning.',
    'PROFESSIONAL PROFILE\n4 years of professional experience selling furniture.\nPROJECTS\nLearning AI.',
])
def test_unrelated_or_unscoped_years_do_not_earn_domain_tenure(resume):
    assert check_experience(_requirement(EXPERIENCE), resume).outcome != 'sufficient'


def test_under_three_years_from_real_farhan_pdf_stays_below_minimum():
    source = extract_text(Path('sample_data/applied_ai_documents/pdf/10_farhan_under_3_years.pdf'))
    assert check_experience(_requirement(EXPERIENCE), source).outcome != 'sufficient'


def test_unrelated_and_pending_degrees_are_not_found():
    req = _requirement(DEGREE)
    assert check_qualification(req, 'EDUCATION\nBS Fine Arts, 2022').outcome == 'mismatch'
    assert check_qualification(req, 'EDUCATION\nPursuing BS Computer Science').outcome == 'ambiguous'


def test_mixed_case_composite_education_heading_in_other_professions():
    cv = 'PROJECTS\nDeployed scheduling workflow.\nEducation, Methods and Additional Background\nBS Accounting, 2020'
    req = _requirement("Completed Bachelor's degree in Accounting.")
    assert check_qualification(req, cv).outcome == 'satisfied'


def test_other_professions_scoped_years_work_without_domain_hardcoding():
    logistics = _requirement('At least 5 years of professional logistics experience.')
    assert logistics.constraint.subject == 'logistics'
    assert check_experience(logistics,
                            'PROFESSIONAL SUMMARY\nI have 5 years of professional logistics experience.').outcome == 'sufficient'
    assert check_experience(logistics,
                            'PROFESSIONAL SUMMARY\n5 years of professional sales experience.').outcome != 'sufficient'


def test_generic_software_scope_is_not_unrelated_sales_tenure():
    req = _requirement('Minimum 3 years of professional experience developing software solutions.')
    assert check_experience(req, 'PROFILE\n4 years professional experience selling insurance.').outcome != 'sufficient'
    assert check_experience(req, 'PROFILE\n4 years of professional experience developing software.').outcome == 'sufficient'


def test_cloud_model_and_local_embedding_are_independently_configured(monkeypatch):
    settings = Settings(llm_provider='ollama', ollama_model='local-test:3b',
                        openrouter_model='cloud/test', embedding_model='custom-embed:latest',
                        ollama_base_url='http://127.0.0.1:11499',
                        embedding_batch_size=4, embedding_timeout_seconds=60)
    captured = {}

    def fake_retrieval(report, **kwargs):
        captured.update(kwargs)
        return {'model_fingerprint': 'test'}

    monkeypatch.setattr('cv_ranker.semantic.run_shadow_retrieval', fake_retrieval)
    result = CVRanker(settings=settings, use_llm=False).run_semantic_shadow(RankingReport(
        job_description_source='test', jd_validation_mode='test', yake_candidates=[],
        requirements=[], candidates=[]), cache_path='not-written.db')
    assert result['model_fingerprint'] == 'test'
    assert captured['model'] == 'custom-embed:latest'
    assert captured['base_url'] == 'http://127.0.0.1:11499'
    assert captured['batch_size'] == 4 and captured['timeout'] == 60


def test_large_embedding_batches_preserve_order_and_dimensions(monkeypatch):
    seen = []

    def fake_request(self, route, body):
        seen.append((route, list(body['input'])))
        return {'embeddings': [[float(i + 1), 1.0] for i, _ in enumerate(body['input'])]}

    monkeypatch.setattr(OllamaEmbeddingGemma, '_request', fake_request)
    embedder = OllamaEmbeddingGemma(batch_size=2, expected_dimensions=2)
    output = embedder.embed_documents(['first', 'second', 'third', 'fourth', 'fifth'])
    assert output.shape == (5, 2)
    assert [len(chunk) for _, chunk in seen] == [2, 2, 1]
    assert seen[0][1][0].startswith('title: none | text: first')


def test_corrupt_single_cache_vector_is_replaced_without_erasing_other_keys(tmp_path):
    class Encoder:
        fingerprint = 'unit-test-stable-digest'

        def embed_documents(self, texts):
            return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)

        embed_queries = embed_documents

    with SQLiteVectorCache(tmp_path / 'vectors.db') as cache:
        broken = SQLiteVectorCache.key(Encoder.fingerprint, 'document', 'damaged')
        good = SQLiteVectorCache.key(Encoder.fingerprint, 'document', 'good')
        cache._conn.execute('INSERT INTO embeddings VALUES (?, ?, ?)', (broken, 2, b'bad'))
        cache._conn.commit()
        cache.put(good, np.array([0.0, 1.0], dtype=np.float32))
        retriever = ShadowRetriever(Encoder(), cache)
        vectors = retriever._encode_cached(['damaged', 'good'], 'document')
        assert retriever.repaired_cache_entries == 1
        assert vectors.shape == (2, 2)
        assert np.allclose(cache.get(good), [0.0, 1.0])
        assert np.allclose(cache.get(broken), [1.0, 0.0])


def test_openrouter_respects_retry_after_and_preserves_local_schema_validation(monkeypatch):
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment
    settings = Settings(llm_provider='openrouter', openrouter_api_key='sk-or-fake',
                        llm_retries=1, openrouter_request_interval_seconds=0,
                        openrouter_retry_delay_seconds=5)
    llm = StructuredLLM(settings)
    sleeps, calls = [], []

    def mock_post(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise OpenRouterHTTPError(429, retry_after_seconds=11)
        return {'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'result': 'uncertain', 'explanation': 'Needs cited source review.', 'source_ids': []})}}]}

    monkeypatch.setattr(llm, '_post_chat', mock_post)
    monkeypatch.setattr('cv_ranker.llm.time.sleep', sleeps.append)
    result = llm.invoke_structured(system_prompt='JSON', user_prompt='Check', schema=CompactFocusedJudgment)
    assert result.result == 'uncertain'
    assert sleeps == [11] and len(calls) == 2
    assert llm.disabled_reason is None


def test_openrouter_parses_safe_retry_hint_and_no_sensitive_body(monkeypatch):
    settings = Settings(llm_provider='openrouter', openrouter_api_key='sk-or-fake',
                        openrouter_request_interval_seconds=0)
    llm = StructuredLLM(settings)

    def fail(_request, timeout):
        raise HTTPError('https://openrouter.ai/api/v1/chat/completions', 429,
                        'secret: do not log', {'Retry-After': '12'}, None)

    monkeypatch.setattr('cv_ranker.llm.urlopen', fail)
    with pytest.raises(OpenRouterHTTPError) as info:
        llm._post_chat({'model': settings.model_name, 'messages': []})
    assert info.value.retry_after_seconds == 12
    assert 'secret' not in str(info.value)


def test_rate_limit_circuit_stops_unbounded_candidate_requests(monkeypatch):
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment
    llm = StructuredLLM(Settings(llm_provider='openrouter', openrouter_api_key='sk-or-fake',
                                 llm_retries=1, openrouter_request_interval_seconds=0))
    calls = []

    def always_limited(_payload):
        calls.append(1)
        raise OpenRouterHTTPError(429)

    monkeypatch.setattr(llm, '_post_chat', always_limited)
    monkeypatch.setattr('cv_ranker.llm.time.sleep', lambda _: None)
    for _ in range(2):
        with pytest.raises(Exception, match='429|circuit'):
            llm.invoke_structured(system_prompt='JSON', user_prompt='Check', schema=CompactFocusedJudgment)
    assert len(calls) == 2  # second request fails fast, no new cloud traffic
    assert 'rate limit' in semantic_failure_message(OpenRouterHTTPError(429)).casefold()
    assert 'OLLAMA_BASE_URL' in semantic_failure_message(EmbeddingError('Cannot reach Ollama at 127.0.0.1'))


def test_successful_local_retrieval_survives_later_cloud_failure(tmp_path):
    report = RankingReport(job_description_source='fake', jd_validation_mode='test',
                           yake_candidates=[], requirements=[_requirement('Python')],
                           candidates=[])
    # Normal workflow correctly needs a candidate; supply an identified one.
    from cv_ranker.schemas import CandidateResult
    report.candidates = [CandidateResult(candidate_name='fake-cv.pdf', candidate_source='fake-cv.pdf')]

    class PartialCloud:
        def plan_jd_capabilities(self, _report):
            return object()

        def run_semantic_shadow(self, *_args, **_kwargs):
            return {'candidates': [{'candidate_name': 'fake-cv.pdf',
                                    'retrieval_status': 'completed'}]}

        def assess_transferability_shadow(self, *_args, **_kwargs):
            raise OpenRouterHTTPError(429)

    captured = []
    with pytest.raises(OpenRouterHTTPError):
        run_semantic_review(PartialCloud(), report, cache_path=tmp_path / 'unused.db',
                            retrieval_callback=captured.append)
    assert captured[0]['candidates'][0]['retrieval_status'] == 'completed'

"""Fictional, provider-free supervisor workflow regression for protocol 56.

This calls the real CVRanker.run, condition reviewer, finalizer, scorer and
ZIP exporter. Fake provider replies exercise contracts, not LLM accuracy.
"""
import io
import json
from zipfile import ZipFile

import pytest

from cv_ranker.config import Settings
from cv_ranker.schemas import (
    JDConditionNode, JDReviewDraft, ValidatedRequirement, RequirementConstraint,
    RequirementAssessment, EvidenceCitation, RankingReport,
)
from cv_ranker.pipeline import CVRanker
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.weighted_scoring import ScoreWeights, weighted_leaderboard
from cv_ranker.eligibility import jd_source_sha256

JD = 'Operate conveyor and document dispatch logs'
SOURCES = {
    'found': 'Experience\nOperated conveyor machinery and documented dispatch logs.',
    'transferable': 'Experience\nOperated conveyor machinery, supervised safe movement of stock.',
    'not_found': 'Experience\nProcessed customer payments at a retail till.',
}


def _approved(jd):
    first = 'Operate conveyor'
    second = 'document dispatch logs'
    a = JDConditionNode(op='leaf', text=first, start=jd.index(first), end=jd.index(first)+len(first))
    b = JDConditionNode(op='leaf', text=second, start=jd.index(second), end=jd.index(second)+len(second))
    expr = JDConditionNode(op='all_of', children=[a,b])
    req = ValidatedRequirement(requirement_id='R001', name=jd, jd_evidence=jd, priority='required',
        constraint=RequirementConstraint(kind='responsibility', operator='complex',
            approved_expression=expr, evidence_modality='performed_work', requires_review=False))
    return JDReviewDraft(jd_sha256=jd_source_sha256(jd), requirements=[req],
        yake_candidates=[], jd_validation_mode='manual', approved=True)


class SyntheticLLM:
    def __init__(self, settings):
        self.settings = settings
        self.disabled_reason = None
        self.logical_calls = self.http_attempts = 0
        self.last_retry_after_seconds = None
        self.http_429_count = 0
        self.token_usage = {}
        self.reused_successful_calls = 0
        self.calls = []

    def prompt_fits(self, *args):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.logical_calls += 1
        self.http_attempts += 1
        payload = json.loads(user_prompt)
        assert schema.__name__ == 'ConditionReviewResponse'
        self.calls.append(payload)
        sources = payload['sources']
        text = ' '.join(x['text'] for x in sources)
        sid = next(x['id'] for x in sources if x['section'] == 'experience')
        mode = ('found' if 'documented dispatch logs' in text else
                'transferable' if 'Operated conveyor' in text else 'not_found')
        facets = []
        for exact in ('Operate conveyor', 'document dispatch logs'):
            supported = exact == 'Operate conveyor' and mode != 'not_found' or mode == 'found'
            row = {'jd_exact_span': exact, 'jd_start': JD.index(exact),
                   'jd_end': JD.index(exact)+len(exact),
                   'relation': 'satisfied' if supported else 'missing',
                   'source_ids': [sid] if supported else [],
                   'proof_quotes': [],
                   'explanation': 'Source action independently examined for this frozen duty.'}
            if supported:
                quote = ('Operated conveyor' if exact == 'Operate conveyor' else
                         'documented dispatch logs')
                row['proof_quotes'] = [{'source_id': sid, 'quote': quote}]
            facets.append(row)
        decision = {'found': 'found', 'transferable': 'transferable', 'not_found': 'not_found'}[mode]
        item = {'requirement_id': 'R001', 'decision': decision,
                'facets': facets,
                'source_ids': [sid] if mode != 'not_found' else [],
                'missing_parts': [] if mode == 'found' else
                   ['document dispatch logs'] if mode == 'transferable' else
                   ['Operate conveyor', 'document dispatch logs'],
                'reason': {'found': 'Original source proves both mandatory duties.',
                           'transferable': 'Operated conveyor but did not establish dispatch logs.',
                           'not_found': 'The supplied CV shows neither conveyor operation nor dispatch logging.'}[mode]}
        return schema.model_validate({'assessments': [item]})


class DummyMetrics:
    warnings = []
    unresolved_criteria = 0
    def public(self):
        return {'llm_calls': 0, 'correction_calls': 0, 'unresolved_criteria': 0}


class StubEngine:
    def __init__(self, *args, **kwargs):
        pass

    def assess(self, requirements, segments, resume_text, **kwargs):
        # Artificially optimistic initial proposal to force full independent
        # condition review; real source verification must prevent false credit.
        evidence = [EvidenceCitation(segment_id=s.segment_id, section=s.section, text=s.text)
                    for s in segments if s.section == 'experience']
        return ([RequirementAssessment(requirement_id=r.requirement_id,
                 status='matched', unified_status='Found',
                 evidence_ids=[e.segment_id for e in evidence], evidence_segments=evidence,
                 evidence=' '.join(e.text for e in evidence),
                 reason='Initial model proposed a match; independent review still required.')
                 for r in requirements], DummyMetrics())

    def close(self):
        pass


@pytest.mark.parametrize('case,verdict,score', [
    ('found','Found',100.0),
    ('transferable','Transferable',0.0),
    ('not_found','Not Found',0.0),
])
def test_supervisor_compound_source_review_through_export(tmp_path, monkeypatch, case, verdict, score):
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM', SyntheticLLM)
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    jd = tmp_path/'approved.txt'
    jd.write_text(JD, encoding='utf-8')
    cv = tmp_path/f'{case}.txt'
    cv.write_text(SOURCES[case], encoding='utf-8')
    ranker = CVRanker(Settings(), unified=True, embedding_cache_path=tmp_path/'cache.db')
    report = ranker.run(jd, [cv], approved_jd=_approved(JD))
    candidate = report.candidates[0]
    result = candidate.assessments[0]
    assert result.current_decision.processing_state == 'completed'
    assert result.current_decision.verdict == verdict
    assert result.unified_status == verdict
    assert candidate.primary_score == score
    assert candidate.rank == 1
    assert not any('semantic_review_incomplete' in x for x in candidate.errors)
    weighted = weighted_leaderboard(report, ScoreWeights(0,0,100))
    assert weighted[0]['weighted_score'] == score
    roundtrip = RankingReport.model_validate_json(report.model_dump_json())
    assert roundtrip.candidates[0].assessments[0].current_decision.verdict == verdict
    zip_bytes = complete_results_zip(report, ScoreWeights(0,0,100))
    with ZipFile(io.BytesIO(zip_bytes)) as export:
        json_report = json.loads(export.read('complete_assessment.json'))
        assert json_report['candidates'][0]['assessments'][0]['current_decision']['verdict'] == verdict
        details = json.loads(export.read('candidates/candidate_001_results.json'))
        assert len(details['why']) == 1
        assert details['why'][0]['decision'] == verdict
        assert len(details['why'][0]['reason']) > 10
        csv_text = export.read('weighted_leaderboard.csv').decode('utf-8-sig')
        assert f'{score}' in csv_text
    if case == 'transferable':
        assert 'dispatch logs' in result.reason
        assert result.evidence_ids
    assert len(ranker.llm.calls) == 1


def test_supervisor_429_preserves_null_and_true_provider_failure(tmp_path, monkeypatch):
    from cv_ranker.llm import LLMError
    class RateLimited(SyntheticLLM):
        def invoke_structured(self, **kwargs):
            self.http_attempts += 1
            raise LLMError('OpenRouter HTTP 429 rate limit')
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM', RateLimited)
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    jd = tmp_path/'jd.txt'; jd.write_text(JD)
    cv = tmp_path/'cv.txt'; cv.write_text(SOURCES['found'])
    ranker = CVRanker(Settings(), unified=True, embedding_cache_path=tmp_path/'cache.db')
    report = ranker.run(jd,[cv],approved_jd=_approved(JD))
    row = report.candidates[0].assessments[0]
    assert row.current_decision.processing_state == 'paused'
    assert row.current_decision.verdict is None
    assert row.current_decision.failure.code == 'provider_rate_limit'
    assert report.candidates[0].primary_score is None
    assert report.candidates[0].rank is None
    assert ranker.llm.http_attempts == 1


def test_supervisor_bad_first_schema_receives_only_one_correction(tmp_path, monkeypatch):
    class BadFirst(SyntheticLLM):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            if self.http_attempts == 0:
                self.http_attempts += 1
                # This is a response validation failure, NOT evidence of absence.
                return schema.model_validate({'assessments': [{'requirement_id': 'R001',
                    'decision':'uncertain', 'facets':[], 'source_ids':[],
                    'missing_parts':[], 'reason':'A fourth verdict was invented by the model.'}]})
            return super().invoke_structured(system_prompt=system_prompt,
                user_prompt=user_prompt, schema=schema)
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM', BadFirst)
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    jd = tmp_path/'jd.txt'; jd.write_text(JD)
    cv = tmp_path/'cv.txt'; cv.write_text(SOURCES['found'])
    ranker = CVRanker(Settings(),unified=True, embedding_cache_path=tmp_path/'cache.db')
    report = ranker.run(jd,[cv],approved_jd=_approved(JD))
    assert report.candidates[0].assessments[0].current_decision.verdict == 'Found'
    assert report.candidates[0].primary_score == 100.0
    assert ranker.llm.http_attempts == 2
    assert ranker.unified_metrics[str(cv)]['compound_review_calls'] == 2


def test_legacy_live_wire_contract_and_three_verdict_scoring():
    from cv_ranker.assessor import _assess_batch
    from cv_ranker.schemas import LLMLiveThreeVerdictResponse
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        LLMLiveThreeVerdictResponse.model_validate({'assessments': [
            {'requirement_id': 'R001', 'status': 'uncertain',
             'reason': 'The model tried a forbidden fourth final outcome.'}]})

    class ThreeChoice:
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            assert schema is LLMLiveThreeVerdictResponse
            assert 'matched, transferable or not_matched' in system_prompt
            return schema.model_validate({'assessments': [
                {'requirement_id':'R001', 'status':'transferable',
                 'reason':'Completed comparable Pulumi automation but no Terraform claim.',
                 'evidence_ids':['S001']},
                {'requirement_id':'R002', 'status':'not_matched',
                 'reason':'The submitted CV does not establish a commercial driving licence.',
                 'evidence_ids':[]},
            ]})
    reqs = [ValidatedRequirement(requirement_id='R001',
                name='Infrastructure automation with Terraform',
                jd_evidence='Infrastructure automation with Terraform', priority='required'),
            ValidatedRequirement(requirement_id='R002',
                name='Commercial driving licence',
                jd_evidence='Commercial driving licence', priority='required')]
    evidence = 'Experience\nBuilt and maintained Pulumi scripts to automate cloud infrastructure.'
    rows, mode, warnings = _assess_batch(resume_text=evidence, requirements=reqs,
                                        llm=ThreeChoice())
    assert mode == 'llm_assessed'
    assert not warnings
    assert rows[0].status == 'not_matched'
    assert rows[0].unified_status == 'Transferable'
    assert rows[0].evidence_segments[0].text in evidence
    assert rows[1].status == 'not_matched'
    assert rows[1].unified_status is None


def test_completed_supervisor_resume_and_weight_only_projection_make_zero_calls(tmp_path, monkeypatch):
    """A protocol-compatible saved decision survives restart without redispatch."""
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM', SyntheticLLM)
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    jd = tmp_path/'jd.txt'; jd.write_text(JD)
    cv = tmp_path/'cv.txt'; cv.write_text(SOURCES['found'])
    first = CVRanker(Settings(), unified=True, embedding_cache_path=tmp_path/'cache1.db')
    initial = first.run(jd, [cv], approved_jd=_approved(JD))
    assert initial.candidates[0].primary_score == 100.0
    key = first.source_keys[str(cv)]
    saved = RankingReport.model_validate_json(initial.model_dump_json())
    later = CVRanker(Settings(), unified=True, embedding_cache_path=tmp_path/'cache2.db')
    restored = later.run(jd, [cv], approved_jd=_approved(JD),
                        resume_report=saved, resume_candidates={key: saved.candidates[0]})
    assert later.llm.http_attempts == 0
    assert restored.candidates[0].primary_score == 100.0
    assert restored.candidates[0].assessments[0].current_decision.verdict == 'Found'
    for _ in range(2):
        weighted = weighted_leaderboard(restored, ScoreWeights(0, 0, 100))
        assert weighted[0]['weighted_score'] == 100.0
    assert later.llm.http_attempts == 0


def test_weight_projection_missing_requirement_is_not_candidate_negative():
    from cv_ranker.schemas import CandidateResult
    from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
    from cv_ranker.weighted_scoring import weighted_candidate
    row = _approved(JD).requirements[0]
    candidate = CandidateResult(candidate_name='missing.txt', candidate_source='missing.txt',
                                primary_score=None, evaluation_mode='failed', assessments=[])
    report = RankingReport(requirements=[row], candidates=[candidate],
                           jd_sha256=jd_source_sha256(JD),
                           job_description_source="fictional_JD.txt",
                           jd_validation_mode="manual", yake_candidates=[])
    projection = weighted_candidate(report, candidate, ScoreWeights(0,0,100))
    assert projection['score'] is None
    assert projection['provisional'] is True
    visible = reconcile_unified_candidate(report,0,[])
    assert visible['Criteria'][0]['Result'] == 'Assessment incomplete'

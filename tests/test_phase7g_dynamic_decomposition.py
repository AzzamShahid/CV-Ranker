"""Dynamic functional retrieval tests using fake structured LLM and fake vectors."""
from pathlib import Path

import numpy as np
import pytest

from cv_ranker import CVRanker, Settings
from cv_ranker.schemas import ValidatedRequirement, RequirementConstraint
from cv_ranker.semantic.decomposition import (
    ProposedCapability, RequirementProposal, DecompositionResponse,
    create_shadow_search_plan, JDSearchPlan, SearchCapability,
)
from cv_ranker.semantic.integration import run_shadow_retrieval
from cv_ranker.schemas import CandidateResult, RankingReport


class MockLLM:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error
        self.calls = 0

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        assert schema is DecompositionResponse
        assert 'source' in user_prompt
        if self.error:
            raise self.error
        return self.data


def r(i='R001', name='Develop APIs and validate requests', **constraint):
    return ValidatedRequirement(
        requirement_id=i, name=name, priority='required', jd_evidence=name,
        constraint=RequirementConstraint(**constraint),
    )


def good_response():
    return DecompositionResponse(requirements=[RequirementProposal(
        requirement_id='R001', capabilities=[
            ProposedCapability(description='API endpoint implementation', source_quote='Develop APIs', origin='explicit'),
            ProposedCapability(description='Request validation', source_quote='validate requests', origin='explicit'),
            ProposedCapability(description='Web backend routing', source_quote='Develop APIs', origin='search_hint'),
        ],
    )])


def test_group_decomposition_creates_only_provisional_queries():
    llm = MockLLM(good_response())
    req = r()
    plan = create_shadow_search_plan([req], llm)
    assert plan.mode == 'jd_decomposition_shadow_not_scoring'
    assert plan.complete is True
    assert plan.scoring_unchanged is True
    assert len(plan.capabilities) == 4
    assert plan.capabilities[0].description == req.name
    assert plan.capabilities[0].capability_id == req.requirement_id
    assert all(x.requires_human_review for x in plan.capabilities[1:])
    assert plan.capabilities[-1].origin == 'search_hint'
    assert llm.calls == 1
    assert req.name == 'Develop APIs and validate requests'


@pytest.mark.parametrize('response', [
    DecompositionResponse(requirements=[RequirementProposal(requirement_id='OTHER',capabilities=[
        ProposedCapability(description='API', source_quote='Develop APIs',origin='explicit')])]),
    DecompositionResponse(requirements=[RequirementProposal(requirement_id='R001',capabilities=[
        ProposedCapability(description='Invented blockchain requirement', source_quote='blockchain',origin='explicit')])]),
    DecompositionResponse(requirements=[RequirementProposal(requirement_id='R001',capabilities=[
        ProposedCapability(description='API', source_quote='Develop APIs',origin='explicit'),
        ProposedCapability(description='API', source_quote='Develop APIs',origin='explicit')])]),
    DecompositionResponse(requirements=[]),
])
def test_bad_proposals_fail_closed_to_frozen_jd_query(response):
    plan = create_shadow_search_plan([r()], MockLLM(response))
    assert plan.complete is False
    assert len(plan.capabilities) == 1
    assert plan.capabilities[0].provenance == 'source_preserved'
    assert plan.warnings


def test_llm_failure_is_visible_and_original_requirement_is_retained():
    plan = create_shadow_search_plan([r()], MockLLM(error=TimeoutError('Qwen unavailable')))
    assert not plan.complete
    assert 'Qwen unavailable' in plan.warnings[0]
    assert plan.capabilities[0].description == r().name


def test_protected_compound_and_numeric_requirements_never_split():
    reqs = [r('R1', 'TensorFlow or PyTorch', operator='any_of', options=['TensorFlow','PyTorch']),
            r('R2', 'Three years in payroll', kind='experience', minimum_years=3),
            r('R3', 'Bachelor of Science', kind='education')]
    llm = MockLLM(error=AssertionError('LLM should not be called'))
    plan = create_shadow_search_plan(reqs, llm)
    assert plan.complete
    assert llm.calls == 0
    assert len(plan.capabilities) == 3
    assert len(plan.warnings) == 3


def test_missing_input_rejected():
    with pytest.raises(ValueError):
        create_shadow_search_plan([], MockLLM(good_response()))
    with pytest.raises(ValueError):
        create_shadow_search_plan([r()], None)
    with pytest.raises(ValueError):
        create_shadow_search_plan([r(), r()], MockLLM(good_response()))


class FakeEncoder:
    fingerprint = 'decomposition-fixture-v1'
    def embed_documents(self, texts):
        return np.array([self.vec(t) for t in texts], dtype='float32')
    def embed_queries(self, texts):
        return np.array([self.vec(t) for t in texts], dtype='float32')
    @staticmethod
    def vec(t):
        t = t.casefold()
        if 'validat' in t or 'payload' in t: return [0., 1., 0.]
        if 'api' in t or 'routes' in t: return [1., 0., 0.]
        return [0., 0., 1.]


def test_real_ranker_decomposition_retrieval_is_read_only(tmp_path):
    jd = tmp_path/'jd.txt'
    jd.write_text('Required Skills:\nDevelop APIs and validate requests\n', encoding='utf-8')
    alice = tmp_path/'alice.txt'
    alice.write_text('Professional Experience:\nImplemented HTTP API routes.\nValidated incoming payloads.', encoding='utf-8')
    bob = tmp_path/'bob.txt'
    bob.write_text('Professional Experience:\nBuilt spreadsheet dashboards.', encoding='utf-8')
    ranker = CVRanker(Settings(), use_llm=False)
    proposed_req = r()
    report = RankingReport(job_description_source=str(jd),
        jd_validation_mode='test_frozen', yake_candidates=[], requirements=[proposed_req],
        candidates=[
            CandidateResult(candidate_name='alice.txt', candidate_source=str(alice), primary_score=50.0, evaluation_mode='fallback_exact',rank=1),
            CandidateResult(candidate_name='bob.txt', candidate_source=str(bob), primary_score=0.0, evaluation_mode='fallback_exact',rank=2),
        ])
    baseline = report.model_dump_json()
    response = good_response()
    plan = create_shadow_search_plan([proposed_req], MockLLM(response))
    result = run_shadow_retrieval(report,cache_path=tmp_path/'vec.db',encoder=FakeEncoder(),top_k=2,capability_plan=plan)
    assert result['scoring_unchanged'] is True
    assert result['decomposition_enabled'] is True
    assert result['decomposition_complete'] is True
    assert len(result['capability_search_plan']['capabilities']) == 4
    assert report.model_dump_json() == baseline
    assert all(hit['candidate_id'] == c['candidate_id']
        for c in result['candidates'] for hits in c['hits_by_requirement'].values() for hit in hits)
    assert any('matched_query_ids' in h for c in result['candidates']
        for hits in c['hits_by_requirement'].values() for h in hits)


def test_search_plan_validation_rejects_foreign_parent():
    req = r()
    report = RankingReport(job_description_source='jd', jd_validation_mode='test',
        yake_candidates=[], requirements=[req], candidates=[])
    bad=JDSearchPlan(complete=True,parent_count=1,capabilities=[SearchCapability(
        parent_requirement_id='OTHER',capability_id='OTHER',description='Misleading',
        source_quote='Nothing',origin='explicit',provenance='source_preserved',requires_human_review=False)],warnings=[])
    with pytest.raises(ValueError,match='foreign'):
        run_shadow_retrieval(report,cache_path='nonexistent.db',encoder=FakeEncoder(),capability_plan=bad)


def test_explicit_all_of_can_generate_search_only_child_queries():
    llm=MockLLM(good_response())
    req = r(operator='all_of',options=['Develop APIs','validate requests'])
    plan = create_shadow_search_plan([req], llm)
    assert plan.complete
    assert len(plan.capabilities)==4
    assert llm.calls==1
    assert all(c.requires_human_review for c in plan.capabilities[1:])


def test_untyped_or_text_is_protected_from_splitting():
    req = r(name='Experience with Python or JavaScript')
    llm=MockLLM(error=AssertionError('must not split OR'))
    plan=create_shadow_search_plan([req],llm)
    assert plan.complete and llm.calls==0
    assert len(plan.capabilities)==1

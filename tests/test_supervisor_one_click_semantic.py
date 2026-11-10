"""Presentation-level 7G integration checks, without real model calls."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pytest

from cv_ranker.schemas import RankingReport, ValidatedRequirement, CandidateResult
from cv_ranker.semantic.transferability import (
    TransferabilityShadowReport, CandidateProposalReport,
    AuditedCapability, EvidenceCitation,
)
from cv_ranker.ui.semantic_workflow import run_semantic_review, semantic_candidate_rows, semantic_summary


def baseline(names=('a.txt',)):
    requirements = [ValidatedRequirement(requirement_id='R001', name='Build HTTP APIs', priority='required', jd_evidence='Build HTTP APIs')]
    candidates = [CandidateResult(candidate_name=n, candidate_source=n, rank=i+1,
                                  primary_score=50.0, evaluation_mode='llm_assessed')
                  for i,n in enumerate(names)]
    return RankingReport(job_description_source='jd.txt', jd_validation_mode='llm_validated',
                         yake_candidates=[], requirements=requirements, candidates=candidates)


def proposals(report):
    return TransferabilityShadowReport(complete=True, frozen_required_count=1,
        candidate_count=len(report.candidates), planned_capability_count=1, candidates=[
        CandidateProposalReport(candidate_id=f'c{i}', candidate_name=c.candidate_name,
            original_primary_score=c.primary_score, original_rank=c.rank,
            status='completed_provisional', warnings=[], assessments=[
            AuditedCapability(requirement_id='R001', capability_id='R001-C01',
                relationship='transferable', citations=[EvidenceCitation(segment_id='S008',
                    exact_quote='Built Express endpoints.')],
                explanation='Similar endpoint functionality via another framework.',
                citation_audit='source_validated')])
        for i, c in enumerate(report.candidates)], warnings=[])


class StubRanker:
    def __init__(self, answer):
        self.answer=answer
        self.calls=[]
    def plan_jd_capabilities(self, report):
        self.calls.append('plan')
        return 'plan-object'
    def run_semantic_shadow(self, report, **kwargs):
        self.calls.append(('retrieve', kwargs))
        assert kwargs['capability_plan']=='plan-object'
        return {'retrieval': True}
    def assess_transferability_shadow(self, report, retrieval):
        self.calls.append('assess')
        assert retrieval == {'retrieval': True}
        return self.answer


def test_one_click_calls_the_existing_semantic_subsystem_in_order(tmp_path):
    rep=baseline()
    before=rep.model_dump_json()
    fake=StubRanker(proposals(rep))
    result=run_semantic_review(fake, rep, cache_path=tmp_path/'cache.db')
    assert fake.calls[0]=='plan' and fake.calls[1][0]=='retrieve' and fake.calls[2]=='assess'
    assert fake.calls[1][1]['model']=='embeddinggemma-2:latest'
    assert rep.model_dump_json()==before
    assert result.scoring_unchanged


def test_review_rows_have_no_score_or_independent_credit():
    rep=baseline(); sem=proposals(rep)
    rows=semantic_candidate_rows(rep, sem, 'a.txt')
    assert len(rows)==1 and rows[0]['Relationship']=='transferable'
    assert rows[0]['Needs review'] is True
    assert 'Score' not in rows[0] and 'Verified' not in rows[0]
    assert 'S008' in rows[0]['Source IDs']
    assert semantic_summary(sem)['transferable']==1


def test_foreign_candidate_missing():
    rep=baseline(); assert semantic_candidate_rows(rep, proposals(rep), 'another.txt')==[]


def test_duplicate_uploaded_resume_names_fail_closed(tmp_path):
    rep=baseline(('same.txt','same.txt'))
    with pytest.raises(ValueError, match='Duplicate candidate'):
        run_semantic_review(StubRanker(proposals(rep)), rep, cache_path=tmp_path/'db')


def test_candidate_identity_mismatch_is_rejected(tmp_path):
    rep=baseline(); sem=proposals(rep)
    altered=sem.model_copy(update={'candidates': [sem.candidates[0].model_copy(update={'original_rank': 100})]})
    with pytest.raises(ValueError, match='mismatches'):
        run_semantic_review(StubRanker(altered), rep, cache_path=tmp_path/'db')


def test_retrieval_error_does_not_change_baseline(tmp_path):
    rep=baseline(); before=rep.model_dump()
    fake=StubRanker(proposals(rep))
    def offline(*args, **kwargs):
        raise RuntimeError('Ollama unavailable')
    fake.run_semantic_shadow=offline
    with pytest.raises(RuntimeError, match='Ollama'):
        run_semantic_review(fake, rep, cache_path=tmp_path/'db')
    assert rep.model_dump()==before


def test_source_failure_is_not_reinterpreted_as_negative(tmp_path):
    rep=baseline(); sem=proposals(rep)
    bad=sem.model_copy(update={'complete':False})
    out=run_semantic_review(StubRanker(bad), rep, cache_path=tmp_path/'db')
    assert not out.complete and out.scoring_unchanged
    assert rep.candidates[0].primary_score==50.0


def test_no_credential_leaks_in_project_file():
    source=(Path(__file__).resolve().parents[1]/'cv_ranker/ui/dashboard.py').read_text(encoding='utf8')
    assert 'OPENROUTER_API_KEY=' not in source
    assert 'cv_semantic_import' not in source
    assert 'Include AI capability cross-check' not in source
    assert 'unified=use_llm' in source
    assert 'run_semantic_review(' not in source
    assert 'SEMANTIC_CACHE' in source

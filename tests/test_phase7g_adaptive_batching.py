"""Adaptive Phase 7G model batching: source-scoped, stable, failure-isolated."""
from __future__ import annotations

import hashlib
import json

import pytest

from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.decomposition import JDSearchPlan, SearchCapability
from cv_ranker.semantic.integration import retrieval_eligible_ids
from cv_ranker.semantic.transferability import (
    BATCH_SYSTEM_PROMPT, CompactBatchResponse, CompactBatchRequirement,
    CompactCapabilityProposal, CompactTransferabilityResponse,
    assess_transferability_shadow,
)


def inputs(tmp_path, count=4):
    lines = [
        'Developed REST endpoints using Flask.',
        'Built document-retrieval pipeline using Haystack.',
        'Created evaluation reports on holdout datasets.',
        'Implemented approval routing through custom Python state machine.',
    ]
    cv = tmp_path / 'candidate.txt'
    cv.write_text('Experience:\n' + '\n'.join(lines) + '\n', encoding='utf-8')
    ss = [s for s in segment_resume(cv.read_text()) if s.segment_id in retrieval_eligible_ids(segment_resume(cv.read_text()))]
    texts = [s for s in ss if s.text in lines]
    names = ['HTTP endpoint construction', 'Document retrieval', 'Model evaluation', 'Conditional workflow orchestration'][:count]
    requirements = [ValidatedRequirement(requirement_id=f'R{i+1:03}', name=name,
                      priority='required', jd_evidence=name) for i, name in enumerate(names)]
    candidate = CandidateResult(candidate_name=cv.name, candidate_source=str(cv), rank=1,
                                primary_score=37.5, evaluation_mode='fallback_exact')
    report = RankingReport(job_description_source='jd.txt', jd_validation_mode='test',
                           yake_candidates=[], requirements=requirements, candidates=[candidate])
    caps = [SearchCapability(parent_requirement_id=r.requirement_id,
                             capability_id=r.requirement_id, description=r.name,
                             source_quote=r.jd_evidence, origin='explicit',
                             provenance='source_preserved', requires_human_review=False)
            for r in requirements]
    plan = JDSearchPlan(complete=True, parent_count=count, capabilities=caps, warnings=[])
    cid = hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    evidence = {}
    segment_ids = {}
    for req, src in zip(requirements, texts):
        segment_ids[req.requirement_id] = src.segment_id
        evidence[req.requirement_id] = [{'segment_id': src.segment_id, 'candidate_id': cid,
            'original_text': src.text, 'section': src.section}]
    retrieval = {'schema_version': 2, 'mode': 'semantic_shadow_read_only',
        'scoring_unchanged': True, 'decomposition_enabled': True,
        'capability_search_plan': plan.model_dump(),
        'candidates': [{'candidate_id': cid, 'candidate_name': cv.name,
                        'direct_primary_score': 37.5, 'ranking_position': 1,
                        'hits_by_requirement': evidence}]}
    return report, retrieval, segment_ids


class BatchLLM:
    supports_compact_transferability = True

    def __init__(self, ids, *, omit=None, foreign=None, max_group=None, fail_multi=False,
                 permanently_wrong=None):
        self.ids = ids
        self.omit = omit
        self.foreign = foreign
        self.max_group = max_group
        self.fail_multi = fail_multi
        self.permanently_wrong = permanently_wrong
        self.batch_calls = []
        self.single_calls = []

    def prompt_fits(self, system_prompt, user_prompt):
        if self.max_group is None:
            return True
        if system_prompt == BATCH_SYSTEM_PROMPT:
            return len(json.loads(user_prompt)['requirements']) <= self.max_group
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        obj = json.loads(user_prompt)
        if schema is CompactBatchResponse:
            reqs = obj['requirements']
            self.batch_calls.append([r['frozen_requirement']['id'] for r in reqs])
            if self.fail_multi:
                raise RuntimeError('Invalid structured multi response')
            results = []
            for entry in reqs:
                rid = entry['frozen_requirement']['id']
                if rid == self.omit:
                    continue
                sid = (self.ids['R001'] if self.foreign == 'borrow' and rid == 'R002'
                       else 'S999' if rid == self.foreign else self.ids[rid])
                results.append(CompactBatchRequirement(requirement_id=rid,
                    capabilities=[CompactCapabilityProposal(capability_id=rid,
                    relationship='direct', source_ids=[sid], explanation='Cited work')]))
            return CompactBatchResponse(requirements=results)
        assert schema is CompactTransferabilityResponse
        rid = obj['frozen_requirement']['id']
        self.single_calls.append(rid)
        sid = 'S999' if rid == self.permanently_wrong else self.ids[rid]
        return CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
            capability_id=rid, relationship='direct', source_ids=[sid], explanation='Cited work')])


def test_four_requirements_need_two_initial_calls(tmp_path):
    report, retrieval, ids = inputs(tmp_path)
    before = report.model_dump_json()
    llm = BatchLLM(ids)
    result = assess_transferability_shadow(report, retrieval, llm, batch_size=3)
    assert result.complete
    assert result.batching['batch_calls'] == 1
    assert result.batching['single_calls'] == 1
    assert len(llm.batch_calls) + len(llm.single_calls) == 2
    assert [x.requirement_id for x in result.candidates[0].assessments] == [r.requirement_id for r in report.requirements]
    assert all(a.citation_audit == 'source_validated' for a in result.candidates[0].assessments)
    assert report.model_dump_json() == before


def test_missing_batch_item_only_retries_that_requirement(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    llm = BatchLLM(ids, omit='R002')
    result = assess_transferability_shadow(report, retrieval, llm)
    assert result.complete
    assert llm.batch_calls == [['R001', 'R002', 'R003']]
    assert llm.single_calls == ['R002']
    assert result.batching['retried_requirements'] == 1
    assert all(a.relationship == 'direct' for a in result.candidates[0].assessments)


def test_foreign_source_does_not_borrow_from_other_requirement(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    llm = BatchLLM(ids, foreign='R002', permanently_wrong='R002')
    result = assess_transferability_shadow(report, retrieval, llm)
    assert not result.complete
    rows = {x.requirement_id: x for x in result.candidates[0].assessments}
    assert rows['R002'].citation_audit == 'audit_failed'
    assert rows['R002'].relationship == 'uncertain'
    assert not rows['R002'].citations
    assert rows['R001'].relationship == 'direct' and rows['R003'].relationship == 'direct'
    assert llm.single_calls == ['R002']


def test_overbudget_batches_split_without_dropping_evidence(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    llm = BatchLLM(ids, max_group=1)
    result = assess_transferability_shadow(report, retrieval, llm, batch_size=3)
    assert result.complete
    assert llm.batch_calls == []
    assert llm.single_calls == ['R001', 'R002', 'R003']
    assert result.batching['split_batches'] == 2


def test_provider_batch_failure_falls_back_to_safe_singles(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    llm = BatchLLM(ids, fail_multi=True)
    result = assess_transferability_shadow(report, retrieval, llm, batch_size=3)
    assert result.complete
    assert result.batching['batch_calls'] >= 1
    assert llm.single_calls == ['R001', 'R002', 'R003']


def test_batch_size_one_uses_original_compact_schema(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    llm = BatchLLM(ids)
    result = assess_transferability_shadow(report, retrieval, llm, batch_size=1)
    assert result.complete and not llm.batch_calls
    assert llm.single_calls == ['R001', 'R002', 'R003']


def test_invalid_batch_size_fails_before_model_calls(tmp_path):
    report, retrieval, ids = inputs(tmp_path)
    llm = BatchLLM(ids)
    with pytest.raises(ValueError, match='batch_size'):
        assess_transferability_shadow(report, retrieval, llm, batch_size=0)
    assert not llm.batch_calls


def test_real_segment_id_borrowed_from_wrong_requirement_is_rejected(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    # S001 exists in the candidate, but it was NOT selected for R002.
    llm = BatchLLM(ids, foreign='borrow', permanently_wrong='R002')
    result = assess_transferability_shadow(report, retrieval, llm)
    rows = {x.requirement_id: x for x in result.candidates[0].assessments}
    assert rows['R002'].citation_audit == 'audit_failed'
    assert rows['R002'].relationship == 'uncertain'
    assert rows['R001'].citation_audit == 'source_validated'
    assert llm.single_calls == ['R002']


def test_duplicate_batch_parent_retried_without_losing_neighbors(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    class DuplicateLLM(BatchLLM):
        def invoke_structured(self, **kw):
            response = super().invoke_structured(**kw)
            if kw['schema'] is CompactBatchResponse:
                duplicate = response.requirements[1]
                return CompactBatchResponse(requirements=response.requirements + [duplicate])
            return response
    llm = DuplicateLLM(ids)
    result = assess_transferability_shadow(report, retrieval, llm)
    assert result.complete
    assert llm.single_calls == ['R002']
    assert result.batching['retried_requirements'] == 1
    assert len(result.candidates[0].assessments) == 3


def test_batch_accepts_transferable_without_adding_primary_score(tmp_path):
    report, retrieval, ids = inputs(tmp_path, count=3)
    class TransferLLM(BatchLLM):
        def invoke_structured(self, **kw):
            response = super().invoke_structured(**kw)
            if kw['schema'] is CompactBatchResponse:
                row = response.requirements[0].capabilities[0]
                response.requirements[0].capabilities[0] = row.model_copy(update={
                    'relationship': 'transferable',
                    'explanation': 'Performed same endpoint functionality through an alternative framework.',
                })
            return response
    llm = TransferLLM(ids)
    result = assess_transferability_shadow(report, retrieval, llm)
    assert result.complete
    assert result.candidates[0].assessments[0].relationship == 'transferable'
    assert result.candidates[0].assessments[0].requires_human_review
    assert result.candidates[0].original_primary_score == 37.5
    assert report.candidates[0].primary_score == 37.5

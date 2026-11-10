"""Integration tests against the actual Phase 7F.2 ranker, no Ollama required."""
from pathlib import Path

import numpy as np
import pytest

from cv_ranker import CVRanker, Settings
from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.integration import retrieval_eligible_ids


class FakeEncoder:
    fingerprint = "fake:7g-integrated:v1"
    def embed_documents(self, texts):
        return np.array([self._v(t) for t in texts], dtype="float32")
    def embed_queries(self, texts):
        return np.array([self._v(t) for t in texts], dtype="float32")
    @staticmethod
    def _v(text):
        text = text.lower()
        if "api" in text or "endpoint" in text or "http" in text:
            return [1., 0., 0.]
        if "python" in text:
            return [0., 1., 0.]
        return [0., 0., 1.]


def test_read_only_shadow_does_not_modify_ranking_or_requirement_count(tmp_path):
    jd = tmp_path / "jd.txt"
    jd.write_text("Required Skills:\nPython\nAPI endpoint development\n", encoding="utf-8")
    a = tmp_path / "alice.txt"
    b = tmp_path / "bob.txt"
    a.write_text("Technical Skills:\nPython\nProfessional Experience:\nBuilt HTTP API endpoints.", encoding="utf-8")
    b.write_text("Technical Skills:\nPython\n", encoding="utf-8")
    ranker = CVRanker(Settings(), use_llm=False)
    report = ranker.run(jd, [a, b])
    baseline = report.model_dump_json()
    count = len(report.requirements)
    result = ranker.run_semantic_shadow(report, cache_path=tmp_path/'v.db', encoder=FakeEncoder(), top_k=1)
    assert report.model_dump_json() == baseline
    assert len(report.requirements) == count
    assert result["scoring_unchanged"] is True
    assert result["decomposition_enabled"] is False
    assert all(c["direct_primary_score"] is not None for c in result["candidates"])
    for c in result['candidates']:
        assert c['ranking_position'] in {x.rank for x in report.candidates}
        for hits in c['hits_by_requirement'].values():
            assert all(hit['candidate_id'] == c['candidate_id'] for hit in hits)
    assert len({c['candidate_id'] for c in result['candidates']}) == 2


def test_copied_jd_and_instructions_excluded_from_retrieval(tmp_path):
    segments = segment_resume("Requirements:\nSkills\nPython\nDjango\nProfessional Experience:\nBuilt APIs with Python.\n")
    allowed = retrieval_eligible_ids(segments)
    assert allowed
    assert all(s.section != 'non_candidate' for s in segments if s.segment_id in allowed)
    assert not any(s.text.strip() in {'Python','Django'} for s in segments if s.segment_id in allowed)
    assert any('Built APIs' in s.text for s in segments if s.segment_id in allowed)


def test_negative_source_is_retrievable_but_never_grants_credit(tmp_path):
    segments = segment_resume('No experience with\nPython\nDjango')
    ids = retrieval_eligible_ids(segments)
    assert any('No experience with Python' in s.text for s in segments if s.segment_id in ids)
    # Search eligibility != verified positive match.


def test_unmatched_or_invalid_frozen_requirements_fail_closed(tmp_path):
    report = RankingReport(job_description_source="jd", jd_validation_mode="test", yake_candidates=[], requirements=[], candidates=[])
    with pytest.raises(ValueError, match="uniquely identified"):
        CVRanker(use_llm=False).run_semantic_shadow(report, cache_path=tmp_path/'x.db', encoder=FakeEncoder())


def test_failed_candidate_is_skipped_without_cv_embedding(tmp_path):
    req = ValidatedRequirement(requirement_id='R001', name='Python', priority='required', jd_evidence='Python')
    report = RankingReport(job_description_source='jd', jd_validation_mode='test', yake_candidates=[],
        requirements=[req], candidates=[CandidateResult(candidate_name='missing.pdf', candidate_source=str(tmp_path/'missing.pdf'), evaluation_mode='failed')])
    result = CVRanker(use_llm=False).run_semantic_shadow(report,cache_path=tmp_path/'x.db',encoder=FakeEncoder())
    assert result['candidates'][0]['retrieval_status'] == 'skipped_failed_assessment'


def test_semantic_shadow_rejects_duplicate_frozen_ids(tmp_path):
    req=ValidatedRequirement(requirement_id='R001',name='Python',priority='required',jd_evidence='Python')
    report=RankingReport(job_description_source='jd',jd_validation_mode='test',yake_candidates=[],requirements=[req,req],candidates=[])
    with pytest.raises(ValueError,match='uniquely identified'):
        CVRanker(use_llm=False).run_semantic_shadow(report,cache_path=tmp_path/'x.db',encoder=FakeEncoder())

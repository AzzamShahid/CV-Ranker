"""Regressions discovered during the 2026-10-19 live Ollama validation."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.semantic.core import CapabilityQuery, EvidenceSegment, ShadowRetriever
from cv_ranker.semantic.cache import SQLiteVectorCache
from cv_ranker.semantic.integration import run_shadow_retrieval
from cv_ranker.semantic.decomposition import JDSearchPlan, SearchCapability
from cv_ranker.semantic.transferability import (
    CompactCapabilityProposal, CompactTransferabilityResponse,
    assess_transferability_shadow,
)


class ExactFakeEncoder:
    fingerprint = "offline-fake-20261019"

    def _vec(self, text):
        if text.strip() == "Python":
            return [1.0, 0.0, 0.0]
        if text.strip() == "JavaScript":
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts):
        return np.array([self._vec(t) for t in texts], dtype=np.float32)

    def embed_queries(self, texts):
        return np.array([self._vec(t) for t in texts], dtype=np.float32)


def test_query_local_scores_are_not_mixed(tmp_path):
    src = [EvidenceSegment("c1", "S001", "Python", True),
           EvidenceSegment("c1", "S002", "JavaScript", True)]
    queries = [CapabilityQuery("R001", "R001", "Python"),
               CapabilityQuery("R002", "R002", "JavaScript")]
    with SQLiteVectorCache(tmp_path / "cache.db") as cache:
        hits = ShadowRetriever(ExactFakeEncoder(), cache, top_k=2).retrieve_by_query("c1", src, queries)
    py = {h.source.segment_id: h for h in hits["R001"]}
    js = {h.source.segment_id: h for h in hits["R002"]}
    assert py["S001"].lexical_exact is True
    assert py["S002"].lexical_exact is False
    assert py["S001"].similarity == 1.0
    assert py["S002"].similarity == 0.0
    assert js["S001"].lexical_exact is False
    assert js["S002"].lexical_exact is True
    assert js["S001"].similarity == 0.0
    assert js["S002"].similarity == 1.0


def test_integrated_requirement_specific_exact_and_cosine(tmp_path):
    cv = tmp_path / "candidate.txt"
    cv.write_text("Skills:\nPython\nJavaScript\n", encoding="utf8")
    candidate = CandidateResult(candidate_name=cv.name, candidate_source=str(cv),
        primary_score=50.0, evaluation_mode="fallback_exact", rank=1)
    report = RankingReport(job_description_source="jd", jd_validation_mode="test", yake_candidates=[],
        requirements=[ValidatedRequirement(requirement_id="R001", name="Python", priority="required", jd_evidence="Python"),
                      ValidatedRequirement(requirement_id="R002", name="JavaScript", priority="required", jd_evidence="JavaScript")],
        candidates=[candidate])
    result = run_shadow_retrieval(report, cache_path=tmp_path / "cache.db",
        encoder=ExactFakeEncoder(), top_k=2)
    hits = result["candidates"][0]["hits_by_requirement"]
    for rid, text in (("R001", "Python"), ("R002", "JavaScript")):
        for hit in hits[rid]:
            if hit["original_text"] != text:
                assert not hit["lexical_exact"], (rid, hit)
                assert hit["cosine_similarity"] == 0.0
            else:
                assert hit["lexical_exact"]
                assert hit["cosine_similarity"] == 1.0
        assert all(x["matched_query_ids"] == [rid] for x in hits[rid])


def test_compact_parse_and_original_source_quote(tmp_path):
    cv = tmp_path / "candidate.txt"
    cv.write_text("Experience:\nDeveloped Flask endpoints.\n", encoding="utf8")
    candidate = CandidateResult(candidate_name=cv.name, candidate_source=str(cv),
        primary_score=50.0, evaluation_mode="fallback_exact", rank=1)
    req = ValidatedRequirement(requirement_id="R001", name="Develop APIs", priority="required", jd_evidence="Develop APIs")
    report = RankingReport(job_description_source="jd", jd_validation_mode="test", yake_candidates=[],
                           requirements=[req], candidates=[candidate])
    parent = SearchCapability(parent_requirement_id="R001", capability_id="R001",
        description="Develop APIs", source_quote="Develop APIs", origin="explicit",
        provenance="source_preserved", requires_human_review=False)
    cap = SearchCapability(parent_requirement_id="R001", capability_id="R001-C01",
        description="API endpoint development", source_quote="Develop APIs", origin="explicit",
        provenance="model_proposed", requires_human_review=True)
    from cv_ranker.segments import segment_resume
    segments = segment_resume(cv.read_text(encoding="utf8"))
    chosen = next(s for s in segments if "Flask" in s.text)
    id_ = hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    retrieval = {"mode": "semantic_shadow_read_only", "scoring_unchanged": True,
        "decomposition_enabled": True,
        "capability_search_plan": JDSearchPlan(complete=True, parent_count=1, capabilities=[parent,cap], warnings=[]).model_dump(),
        "candidates": [{"candidate_id":id_,"candidate_name":cv.name,"direct_primary_score":50.0,"ranking_position":1,
            "hits_by_requirement": {"R001":[{"segment_id":chosen.segment_id,
                "candidate_id":id_,"original_text":chosen.text,"section":chosen.section}]}}]}

    class FakeCompactLLM:
        supports_compact_transferability = True
        def prompt_fits(self, *_):
            return True
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            assert schema is CompactTransferabilityResponse
            assert '"capability_id": "R001-C01"' in user_prompt
            return CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
                capability_id="R001-C01", relationship="transferable",
                source_ids=[chosen.segment_id], explanation="Endpoint functionality" )])

    result = assess_transferability_shadow(report, retrieval, FakeCompactLLM())
    assert result.complete
    item = result.candidates[0].assessments[0]
    assert item.relationship == "transferable"
    assert item.citation_audit == "source_validated"
    assert item.citations[0].exact_quote == chosen.text
    assert item.independent_semantic_verification is False
    assert result.scoring_unchanged is True


def test_compact_positive_with_missing_citation_is_uncertain(tmp_path):
    from cv_ranker.semantic.transferability import _validate_compact_response
    cap = SearchCapability(parent_requirement_id="R001", capability_id="R001-C01",
        description="Build APIs", source_quote="Build APIs", origin="explicit",
        provenance="model_proposed", requires_human_review=True)
    reply = CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
        capability_id="R001-C01", relationship="direct", source_ids=[], explanation="guessed")])
    decisions, warnings = _validate_compact_response("R001", [cap], {"S001":"Built APIs"}, reply)
    assert decisions[0].relationship == "uncertain"
    assert decisions[0].citation_audit == "audit_failed"
    assert warnings


def test_compact_foreign_source_is_rejected(tmp_path):
    import pytest
    from cv_ranker.semantic.transferability import _validate_compact_response
    cap = SearchCapability(parent_requirement_id="R001", capability_id="R001-C01",
        description="Build APIs", source_quote="Build APIs", origin="explicit",
        provenance="model_proposed", requires_human_review=True)
    reply = CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
        capability_id="R001-C01", relationship="direct", source_ids=["S999"], explanation="guessed")])
    with pytest.raises(ValueError, match="source IDs"):
        _validate_compact_response("R001", [cap], {"S001":"Built APIs"}, reply)


def test_old_mixed_retrieval_diagnostics_rejected_before_llm():
    import pytest
    from cv_ranker.semantic.transferability import assess_transferability_shadow
    with pytest.raises(ValueError, match="schema v1 mixes"):
        assess_transferability_shadow(None, {"schema_version": 1}, object())


def test_compact_integration_flags_exact_named_skill_as_potential_direct(tmp_path):
    from cv_ranker.segments import segment_resume
    cv = tmp_path / "candidate.txt"
    cv.write_text("Experience:\nUsed Git for version control.\n", encoding="utf8")
    chosen = next(s for s in segment_resume(cv.read_text()) if "Git" in s.text)
    candidate = CandidateResult(candidate_name=cv.name, candidate_source=str(cv),
        primary_score=100.0, evaluation_mode="fallback_exact", rank=1)
    req = ValidatedRequirement(requirement_id="R001", name="Git", priority="required", jd_evidence="Git")
    report = RankingReport(job_description_source="jd", jd_validation_mode="test", yake_candidates=[],
                           requirements=[req], candidates=[candidate])
    original = SearchCapability(parent_requirement_id="R001", capability_id="R001", description="Git",
        source_quote="Git", origin="explicit", provenance="source_preserved", requires_human_review=False)
    derived = SearchCapability(parent_requirement_id="R001", capability_id="R001-C01", description="Git",
        source_quote="Git", origin="explicit", provenance="model_proposed", requires_human_review=True)
    cid = hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    retrieval = {"schema_version":2, "mode":"semantic_shadow_read_only", "scoring_unchanged":True,
        "decomposition_enabled":True, "capability_search_plan":JDSearchPlan(
            complete=True, parent_count=1, capabilities=[original,derived], warnings=[]).model_dump(),
        "candidates":[{"candidate_id":cid,"candidate_name":cv.name,"direct_primary_score":100.0,
          "ranking_position":1,"hits_by_requirement":{"R001":[{
              "segment_id":chosen.segment_id,"candidate_id":cid,
              "original_text":chosen.text,"section":chosen.section}]}}]}

    class FakeCompactLLM:
        supports_compact_transferability = True
        def prompt_fits(self, *_): return True
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            assert "same work for another employer" in system_prompt
            return CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
                capability_id="R001-C01", relationship="transferable",
                source_ids=[chosen.segment_id], explanation="Earlier position")])

    result = assess_transferability_shadow(report, retrieval, FakeCompactLLM())
    assert result.complete is True  # structural completion is distinct from label quality
    assert result.relationship_consistency_flag_count == 1
    item = result.candidates[0].assessments[0]
    assert item.relationship == "transferable"  # reviewer flag, not automatic label upgrade
    assert item.relationship_consistency_flags == ["possible_direct_mislabeled_transferable"]
    assert item.citation_audit == "source_validated"
    assert item.requires_human_review is True
    assert result.candidates[0].original_primary_score == 100.0

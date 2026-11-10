"""Source-audited but deliberately NON-scoring live-transfer proposals."""
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from cv_ranker import CVRanker, Settings
from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.decomposition import JDSearchPlan, SearchCapability
from cv_ranker.semantic.integration import retrieval_eligible_ids
from cv_ranker.semantic.transferability import (
    EvidenceCitation, ProposedRelationship, RequirementProposal,
    TransferabilityResponse, assess_transferability_shadow,
)


class FakeLLM:
    def __init__(self, relations=None, error=None, prompt_fits=True):
        self.relations = relations or {}
        self.error = error
        self.calls = 0
        self.fits = prompt_fits

    def prompt_fits(self, system_prompt, user_prompt):
        return self.fits

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        assert schema is TransferabilityResponse
        assert "frozen_requirement" in user_prompt
        assert "retrieved_cv_sources" in user_prompt
        if self.error:
            raise self.error
        return TransferabilityResponse(requirements=[RequirementProposal(
            requirement_id="R001", capabilities=self.relations["R001"]
        )])


def fixtures(tmp_path, *, text="Professional Experience:\nDeveloped HTTP endpoints with Flask.\nValidated request payloads.",
             include_child=True):
    cv = tmp_path / "alice.txt"
    cv.write_text(text, encoding="utf-8")
    req = ValidatedRequirement(requirement_id="R001", name="Develop APIs and validate requests",
        priority="required", jd_evidence="Develop APIs and validate requests")
    candidate = CandidateResult(candidate_name=cv.name, candidate_source=str(cv),
        primary_score=50.0, evaluation_mode="fallback_exact", rank=1)
    report = RankingReport(job_description_source="jd", jd_validation_mode="test", yake_candidates=[],
        requirements=[req], candidates=[candidate])
    parent = SearchCapability(parent_requirement_id="R001", capability_id="R001",
        description=req.name, source_quote=req.jd_evidence, origin="explicit",
        provenance="source_preserved", requires_human_review=False)
    entries = [parent]
    if include_child:
        entries += [SearchCapability(parent_requirement_id="R001", capability_id="R001-C01",
            description="API endpoint development", source_quote="Develop APIs", origin="explicit",
            provenance="model_proposed", requires_human_review=True),
            SearchCapability(parent_requirement_id="R001", capability_id="R001-C02",
            description="Web services", source_quote="Develop APIs", origin="search_hint",
            provenance="model_proposed", requires_human_review=True)]
    plan = JDSearchPlan(complete=True, parent_count=1, capabilities=entries, warnings=[])
    candidate_id = hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    segments = [s for s in segment_resume(text) if s.segment_id in retrieval_eligible_ids(segment_resume(text))]
    hits = [{"segment_id": s.segment_id, "candidate_id": candidate_id,
             "original_text": s.text, "section": s.section} for s in segments]
    data = {"mode": "semantic_shadow_read_only", "scoring_unchanged": True,
        "decomposition_enabled": True, "capability_search_plan": plan.model_dump(),
        "candidates": [{"candidate_id": candidate_id, "candidate_name": cv.name,
            "direct_primary_score": 50.0, "ranking_position": 1,
            "hits_by_requirement": {"R001": hits}}]}
    return report, data, segments


def positive(cid, segment, quote, relation="transferable"):
    return ProposedRelationship(capability_id=cid, relationship=relation,
        citations=[EvidenceCitation(segment_id=segment, exact_quote=quote)],
        explanation="Function demonstrated in a different framework")


def single_output(report, data, llm):
    baseline = report.model_dump_json()
    result = assess_transferability_shadow(report, data, llm)
    assert report.model_dump_json() == baseline
    assert result.mode == "qwen_transferability_shadow_not_scoring"
    assert result.scoring_unchanged and result.frozen_required_count == 1
    assert result.candidates[0].original_primary_score == 50.0
    return result


def test_valid_transferable_proposal_is_source_audited_but_unverified(tmp_path):
    report, data, segments = fixtures(tmp_path)
    chosen = next(s for s in segments if "Flask" in s.text)
    llm = FakeLLM({"R001": [positive("R001-C01", chosen.segment_id, "Developed HTTP endpoints with Flask.")]})
    result = single_output(report, data, llm)
    assert llm.calls == 1
    assert result.complete
    assert result.candidates[0].assessments[0].relationship == "transferable"
    assert result.candidates[0].assessments[0].citation_audit == "source_validated"
    assert result.candidates[0].assessments[0].independent_semantic_verification is False
    assert result.candidates[0].assessments[0].requires_human_review is True
    assert result.planned_capability_count == 1  # search hint excluded


def test_invalid_quote_fails_closed(tmp_path):
    report, data, segments = fixtures(tmp_path)
    chosen = segments[0]
    llm = FakeLLM({"R001": [positive("R001-C01", chosen.segment_id, "Invented experience") ]})
    result = single_output(report, data, llm)
    assert not result.complete
    assert result.candidates[0].assessments[0].relationship == "uncertain"
    assert result.candidates[0].assessments[0].citation_audit == "audit_failed"
    assert "Hallucinated" in result.candidates[0].warnings[0]


def test_foreign_citation_cannot_claim_other_candidate(tmp_path):
    report, data, segments = fixtures(tmp_path)
    llm = FakeLLM({"R001": [positive("R001-C01", "S999", "Used Flask") ]})
    result = single_output(report, data, llm)
    assert not result.complete
    assert result.candidates[0].assessments[0].relationship == "uncertain"


def test_missing_capability_fails_closed(tmp_path):
    report, data, _ = fixtures(tmp_path)
    result = single_output(report, data, FakeLLM({"R001": []}))
    assert not result.complete
    assert result.candidates[0].assessments[0].relationship == "uncertain"


def test_model_failure_is_visible_and_safe(tmp_path):
    report, data, _ = fixtures(tmp_path)
    result = single_output(report, data, FakeLLM(error=TimeoutError("timeout")))
    assert not result.complete
    assert "TimeoutError" in result.candidates[0].warnings[0]


def test_no_evidence_is_uncertain_not_unsupported(tmp_path):
    report, data, _ = fixtures(tmp_path)
    data["candidates"][0]["hits_by_requirement"]["R001"] = []
    llm = FakeLLM()
    result = single_output(report, data, llm)
    assert llm.calls == 0 and not result.complete
    assert result.candidates[0].assessments[0].relationship == "uncertain"


def test_context_budget_does_not_truncate_silently(tmp_path):
    report, data, _ = fixtures(tmp_path)
    llm = FakeLLM(prompt_fits=False)
    result = single_output(report, data, llm)
    assert llm.calls == 0
    assert result.candidates[0].assessments[0].relationship == "uncertain"
    assert "context budget" in result.candidates[0].warnings[0]


def test_hit_limit_requires_review_not_negative(tmp_path):
    report, data, _ = fixtures(tmp_path)
    llm = FakeLLM()
    result = assess_transferability_shadow(report, data, llm, max_hits_per_requirement=1)
    assert llm.calls == 0
    assert result.candidates[0].assessments[0].relationship == "uncertain"


def test_retrieved_text_is_rechecked_against_original_source(tmp_path):
    report, data, _ = fixtures(tmp_path)
    data["candidates"][0]["hits_by_requirement"]["R001"][0]["original_text"] = "Injected fake evidence"
    with pytest.raises(ValueError, match="original-text audit"):
        assess_transferability_shadow(report, data, FakeLLM())


def test_foreign_candidate_id_rejected(tmp_path):
    report, data, _ = fixtures(tmp_path)
    data["candidates"][0]["hits_by_requirement"]["R001"][0]["candidate_id"] = "attacker"
    with pytest.raises(ValueError, match="original-text audit"):
        assess_transferability_shadow(report, data, FakeLLM())


def test_duplicate_retrieved_segment_rejected(tmp_path):
    report, data, _ = fixtures(tmp_path)
    hits = data["candidates"][0]["hits_by_requirement"]["R001"]
    hits.append(dict(hits[0]))
    with pytest.raises(ValueError, match="Duplicate original"):
        assess_transferability_shadow(report, data, FakeLLM())


def test_output_is_non_scoring_even_for_direct_proposal(tmp_path):
    report, data, segments = fixtures(tmp_path)
    chosen = next(s for s in segments if "Flask" in s.text)
    llm = FakeLLM({"R001": [positive("R001-C01", chosen.segment_id, "Flask", "direct")]})
    result = single_output(report, data, llm)
    assert result.candidates[0].assessments[0].relationship == "direct"
    assert result.candidates[0].original_rank == 1
    assert "verified_functional_requirement_coverage_pct" not in result.model_dump_json()


def test_positive_without_citation_structurally_forbidden():
    with pytest.raises(ValidationError):
        ProposedRelationship(capability_id="C1", relationship="direct", citations=[], explanation="guess")


def test_plain_unsplit_requirement_is_assessed_once(tmp_path):
    report, data, segments = fixtures(tmp_path, include_child=False)
    chosen = next(s for s in segments if "Flask" in s.text)
    llm = FakeLLM({"R001": [positive("R001", chosen.segment_id, "Flask")]})
    result = single_output(report, data, llm)
    assert len(result.candidates[0].assessments) == 1
    assert result.candidates[0].assessments[0].capability_id == "R001"


def test_empty_search_hint_does_not_generate_assessment(tmp_path):
    report, data, segments = fixtures(tmp_path)
    chosen = next(s for s in segments if "Flask" in s.text)
    llm = FakeLLM({"R001": [positive("R001-C01", chosen.segment_id, "Flask")]})
    result = single_output(report, data, llm)
    assert "R001-C02" not in {x.capability_id for x in result.candidates[0].assessments}


def test_ranker_requires_live_llm(tmp_path):
    report, data, _ = fixtures(tmp_path)
    ranker = CVRanker(Settings(), use_llm=False)
    with pytest.raises(ValueError, match="live structured"):
        ranker.assess_transferability_shadow(report, data)


def test_tampered_proposed_jd_quote_rejected(tmp_path):
    report, data, _ = fixtures(tmp_path)
    data["capability_search_plan"]["capabilities"][1]["source_quote"] = "Invented training requirement"
    with pytest.raises(ValueError, match="JD source quote"):
        assess_transferability_shadow(report, data, FakeLLM())


def test_model_cannot_upgrade_its_proposal_to_human_approved(tmp_path):
    report, data, _ = fixtures(tmp_path)
    data["capability_search_plan"]["capabilities"][1]["requires_human_review"] = False
    with pytest.raises(ValueError, match="flagged for review"):
        assess_transferability_shadow(report, data, FakeLLM())

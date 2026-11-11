"""Avoid false certainty while resolving non-scoring model uncertainty.

Local development may change files; a remotely exposed release still enforces
source integrity. All scenarios run without a live model or applicant data.
"""

import pytest

from cv_ranker import runtime_check
from cv_ranker.schemas import (CandidateResult, RankingReport,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (UnifiedItem, UnifiedResponse, _map_response,
                               _independently_adjudicate, UNIFIED_PROMPT,
                               FINAL_ADJUDICATION_PROMPT)
from cv_ranker.weighted_scoring import (ScoreWeights, provisional_score_bounds,
                                        weighted_candidate)


def _req(name, index):
    return ValidatedRequirement(
        requirement_id=f"R{index:03d}", name=name,
        jd_evidence=name, priority="required")


def test_both_primary_and_independent_prompts_prioritize_evidence_based_decisiveness():
    for prompt in (UNIFIED_PROMPT, FINAL_ADJUDICATION_PROMPT):
        assert "DECISION CALIBRATION" in prompt
        assert "transferable" in prompt.casefold()
        assert "not_found" in prompt.casefold()
        assert "uncertain" in prompt.casefold()
        assert "dates" in prompt.casefold()
        assert "degree" in prompt.casefold()
        assert "participation" in prompt.casefold()
        assert "completed" in prompt.casefold()


def test_uncertain_with_absent_relationship_becomes_non_scoring_not_found():
    requirement = _req("Named employer capability", 1)
    response = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R001", decision="uncertain", relation="absent",
        evidence_ids=[], reason="The CV does not establish the requested capability.")])
    mapped, proposed, invalid = _map_response(response, [requirement], set())
    assert not invalid
    assert proposed["R001"].decision == "not_found"
    assert mapped.assessments[0].status == "not_matched"


def test_uncertain_with_cited_overlap_becomes_unscored_transferable_proposal():
    requirement = _req("Named employer capability", 1)
    response = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R001", decision="uncertain", relation="overlap",
        evidence_ids=["S001"], reason="Completed related work, exact named skill unproven.")])
    mapped, proposed, invalid = _map_response(response, [requirement], {"S001"})
    assert not invalid
    assert proposed["R001"].decision == "transferable"
    assert mapped.assessments[0].status == "not_matched"


def test_uncertain_with_claimed_direct_relationship_cannot_skip_positive_validation():
    requirement = _req("Named employer capability", 1)
    response = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R001", decision="uncertain", relation="direct",
        evidence_ids=["S001"], reason="The relationship is inconsistent in the model output.")])
    _, _, invalid = _map_response(response, [requirement], {"S001"})
    assert invalid == {"R001"}


def test_independent_uncertainty_overlap_normalization_preserves_source_id():
    class Model:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate({"R001": {
                "decision": "uncertain", "relation": "overlap",
                "evidence_ids": ["S001"], "proof_excerpt": None,
                "reason": "The candidate completed related tasks using another tool."}})

    req = _req("Named employer capability", 1)
    original = {"S001": ResumeSegment("S001", "experience", "Built related tasks with another tool.")}
    mapped, proposals, invalid = _independently_adjudicate(
        Model(), [req], "{}", {"S001"}, original)
    assert not invalid
    assert proposals["R001"].decision == "transferable"
    assert mapped.assessments[0].evidence_ids == ["S001"]


def test_provisional_bounds_never_credit_unverified_positive_claim():
    reqs = [_req(f"Requirement {i}", i) for i in range(1, 5)]
    candidate = CandidateResult(candidate_name="Candidate A", primary_score=None,
                                assessments=[
        RequirementAssessment(requirement_id="R001", status="matched", unified_status="Found"),
        RequirementAssessment(requirement_id="R002", status="not_matched", unified_status="Transferable"),
        RequirementAssessment(requirement_id="R003", status="not_matched", unified_status="Not Found"),
        RequirementAssessment(requirement_id="R004", status="matched", unified_status="Unverified",
                              assessment_state="unverified"),
    ])
    report = RankingReport(job_description_source="jd", jd_validation_mode="test",
                           yake_candidates=[], requirements=reqs, candidates=[candidate])
    weights = ScoreWeights(experience=0, education=0, jd=100)
    bounds = provisional_score_bounds(report, candidate, weights)
    assert weighted_candidate(report, candidate, weights)["score"] is None
    assert bounds["verified_floor"] == 25.0
    assert bounds["possible_ceiling"] == 50.0
    assert bounds["unverified_requirements"] == 1
    assert bounds["provisional"]


def test_local_edits_do_not_raise_hash_mismatch_but_remote_checks_do(monkeypatch):
    monkeypatch.setenv("CVR_ACCESS_MODE", "local")
    monkeypatch.delenv("CVR_STRICT_SOURCE_HASHES", raising=False)
    monkeypatch.setattr(runtime_check, "_sha256", lambda _path: "edited-content")
    info = runtime_check.runtime_fingerprint()
    assert info["source_integrity"] == "local_editable"

    monkeypatch.setenv("CVR_ACCESS_MODE", "oidc")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        runtime_check.runtime_fingerprint()

    monkeypatch.setenv("CVR_ACCESS_MODE", "local")
    monkeypatch.setenv("CVR_STRICT_SOURCE_HASHES", "1")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        runtime_check.runtime_fingerprint()

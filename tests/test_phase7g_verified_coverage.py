"""Verifies scoring isolation and source-backed functional coverage."""
import pytest
from cv_ranker.schemas import CandidateResult, ValidatedRequirement
from cv_ranker.semantic.coverage_scoring import (
    CapabilityPlan, AdjudicatedCapability, score_verified_capability_coverage,
)


def req(id, priority="required"):
    return ValidatedRequirement(requirement_id=id, name=f"JD {id}", priority=priority, jd_evidence=f"JD {id}")


def cap(req_id, suffix="1", origin="explicit"):
    return CapabilityPlan(requirement_id=req_id, capability_id=f"{req_id}-{suffix}",
                          description="Source-grounded capability", origin=origin)


def verdict(cap_id, relation="direct", ids=None, verification="verified", constraint="satisfied"):
    return AdjudicatedCapability(capability_id=cap_id, relationship=relation,
                                  evidence_ids=ids if ids is not None else (["S001"] if relation in ("direct", "transferable") else []),
                                  verification=verification, constraint_status=constraint)


def score(requirements, plan, decisions, sources=None):
    candidate=CandidateResult(candidate_name="Candidate A", primary_score=37.5, evaluation_mode="llm_assessed")
    snapshot=candidate.model_dump_json()
    result=score_verified_capability_coverage(candidate=candidate, requirements=requirements,
             plan=plan, decisions=decisions, admissible_source_ids=sources if sources is not None else {"S001"})
    assert candidate.model_dump_json()==snapshot
    assert result.original_primary_score==37.5 and result.ranking_unchanged
    return result


def test_all_direct_coverage_independent_from_original_primary():
    result=score([req("R1")], [cap("R1")], [verdict("R1-1")])
    assert result.verified_direct_requirement_coverage_pct==100
    assert result.verified_functional_requirement_coverage_pct==100
    assert result.original_primary_score==37.5


def test_transferable_does_not_replace_direct_match():
    result=score([req("R1")], [cap("R1")], [verdict("R1-1", "transferable")])
    assert result.verified_direct_requirement_coverage_pct==0
    assert result.verified_functional_requirement_coverage_pct==100
    assert result.requirements[0].state=="functionally_supported"


def test_partial_cannot_gain_full_requirement_credit():
    result=score([req("R1")], [cap("R1", "1"),cap("R1", "2")],
                 [verdict("R1-1", "transferable"),verdict("R1-2", "not_evidenced")])
    assert result.partial_required==1
    assert result.verified_functional_requirement_coverage_pct==0
    assert result.requirements[0].transferable_capabilities==1


def test_search_hints_never_improve_denominator_or_score():
    result=score([req("R1")], [cap("R1"), cap("R1", "hint", "search_hint")],
                 [verdict("R1-1"),verdict("R1-hint", "transferable")])
    assert result.search_hints_excluded==1
    assert result.requirements[0].explicit_capabilities==1


def test_unverified_model_claim_cannot_be_credited():
    result=score([req("R1")], [cap("R1")], [verdict("R1-1", verification="unreviewed")])
    assert result.verified_functional_requirement_coverage_pct is None
    assert result.review_required==1
    assert result.requirements[0].state=="needs_review"


def test_missing_constraint_blocks_positive_credit():
    for state in ("unresolved", "not_satisfied"):
        result=score([req("R1")], [cap("R1")], [verdict("R1-1", constraint=state)])
        assert result.verified_functional_requirement_coverage_pct is None if state == "unresolved" else result.verified_functional_requirement_coverage_pct == 0


def test_cross_candidate_or_excluded_source_rejected():
    with pytest.raises(ValueError, match="Unknown or inadmissible"):
        score([req("R1")], [cap("R1")], [verdict("R1-1", ids=["FOREIGN"])])


def test_no_frozen_requirement_coverage_from_incomplete_decomposition():
    result=score([req("R1"),req("R2")], [cap("R1")], [verdict("R1-1")])
    assert result.verified_functional_requirement_coverage_pct is None
    assert result.evaluated_required_count==1


def test_coverage_missing_or_foreign_or_duplicate_verdict_fails():
    r=[req("R1")]
    p=[cap("R1")]
    with pytest.raises(ValueError, match="Incomplete"):
        score(r,p,[])
    with pytest.raises(ValueError, match="Unexpected"):
        score(r,p,[verdict("R1-1"),verdict("BAD")])
    with pytest.raises(ValueError, match="Duplicate capability verdict"):
        score(r,p,[verdict("R1-1"),verdict("R1-1")])


def test_duplicate_original_source_ids_fail():
    with pytest.raises(ValueError, match="Duplicate evidence"):
        verdict("R1-1",ids=["S001","S001"])


def test_required_and_preferred_not_mixed():
    result=score([req("R1"),req("R2","preferred")], [cap("R1"),cap("R2")],
                 [verdict("R1-1","not_evidenced"), verdict("R2-1")])
    assert result.verified_functional_requirement_coverage_pct==0
    assert result.frozen_required_count==1


def test_related_does_not_earn_credit():
    result=score([req("R1")],[cap("R1")],[verdict("R1-1","related_only")])
    assert result.requirements[0].state=="related_only"
    assert result.verified_functional_requirement_coverage_pct==0


def test_verification_rejection_fails_closed():
    result=score([req("R1")],[cap("R1")],[verdict("R1-1",verification="rejected")])
    assert result.requirements[0].state=="not_evidenced"
    assert result.verified_functional_requirement_coverage_pct==0


def test_invalid_plan_and_duplicate_capability_fail_closed():
    with pytest.raises(ValueError, match="nonexistent"):
        score([req("R1")],[cap("R2")],[verdict("R2-1")])
    with pytest.raises(ValueError, match="Duplicate capability plan"):
        score([req("R1")],[cap("R1"),cap("R1")],[verdict("R1-1")])


def test_failed_candidate_cannot_publish_transfer_coverage():
    with pytest.raises(ValueError, match="incomplete or failed"):
        score_verified_capability_coverage(
            candidate=CandidateResult(candidate_name="X", evaluation_mode="failed"),
            requirements=[req("R1")], plan=[cap("R1")],
            decisions=[verdict("R1-1")], admissible_source_ids={"S001"},
        )


def test_cvranker_exposes_only_read_only_verified_reporting():
    from cv_ranker.pipeline import CVRanker
    from cv_ranker.config import Settings
    ranker = CVRanker(Settings(), use_llm=False)
    c = CandidateResult(candidate_name="Candidate A", primary_score=42.0, evaluation_mode="fallback_exact")
    report = ranker.score_verified_functional_coverage(
        c, [req("R1")], [cap("R1")], [verdict("R1-1", "transferable")],
        admissible_source_ids={"S001"},
    )
    assert report.verified_functional_requirement_coverage_pct == 100
    assert c.primary_score == 42.0 and c.rank is None

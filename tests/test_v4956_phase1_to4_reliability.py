"""Offline, source-grounded regression cases for the phase 1–4 repairs.

These use model-declared semantic relations in the tests; they do not claim a
real model correctly adjudicated the source, or infer credentials from words.
"""

import pytest

from cv_ranker.assessor import _validate_rows
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.scoring import score_candidate
from cv_ranker.schemas import (
    EvidenceCitation, LLMAssessmentItem, LLMCandidateAssessmentResponse,
    RankingReport, RequirementAssessment, RequirementConstraint,
    ValidatedRequirement,
)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import UnifiedItem, _final_unified_row
from cv_ranker.weighted_scoring import ScoreWeights, weighted_candidate, weighted_leaderboard


def requirement(rid, name, kind="responsibility"):
    return ValidatedRequirement(
        requirement_id=rid, name=name, priority="required", jd_evidence=name,
        constraint=RequirementConstraint(kind=kind, origin="source_rules"),
    )


def validate(req, source, *, section="skills", semantic=True):
    segment = ResumeSegment("S001", section, source)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id=req.requirement_id, status="matched", evidence_ids=["S001"],
        reason="The independent evaluator reports direct task entailment.",
    )])
    checked, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req], resume_text=source,
        segments=[segment], semantic_grounded=semantic,
    )
    return checked, invalid, warnings


@pytest.mark.parametrize("jd,description", [
    ("Run a documented disaster-recovery restore exercise",
     "Ran a documented disaster-recovery restore exercise and recorded the outcome."),
    ("Participate in recovery drills",
     "Paired with the night operator on recovery drills and measured recovery time."),
    ("Investigate failed releases",
     "Traced failed releases to a stalled upstream dependency and restored the service."),
])
def test_substantive_completed_work_is_not_vetoed_by_section_or_verb_list(jd, description):
    req = requirement("R010", jd)
    checked, invalid, notices = validate(req, description, section="skills")
    assert not invalid, notices
    assert checked["R010"].status == "matched"
    assert checked["R010"].evidence_ids == ["S001"]


@pytest.mark.parametrize("rid,jd,unrelated,missing", [
    ("R005", "Manage cloud infrastructure through Terraform modules",
     "Managed a Linux hosting estate and moved maintenance tasks into version control.", "Terraform"),
    ("R009", "Implement least-privilege AWS IAM roles for applications",
     "Rewrote alerting rules and operated production Kubernetes clusters.", "AWS"),
])
def test_generic_infrastructure_action_cannot_prove_missing_named_condition(
    rid, jd, unrelated, missing,
):
    req = requirement(rid, jd)
    _, invalid, notices = validate(req, unrelated, section="experience")
    assert invalid == {rid}
    assert any(missing in warning and "named JD condition" in warning for warning in notices)


def test_named_condition_and_actual_completed_work_can_be_accepted():
    req = requirement("R005", "Manage cloud infrastructure through Terraform modules")
    checked, invalid, notices = validate(
        req, "Created Terraform modules and managed cloud infrastructure with reviewed plans.",
        section="skills",
    )
    assert not invalid, notices
    assert checked["R005"].status == "matched"


def test_unsupported_expanded_initialisms_are_review_leads_not_automatic_direct_credit():
    req = requirement("R009", "Implement least-privilege AWS IAM roles for applications")
    checked, invalid, notices = validate(
        req, ("Implemented least-privilege roles for apps in Amazon Web Services "
              "using Identity and Access Management policies."),
        section="experience",
    )
    # v48 explicitly rejects unapproved initial-letter coincidences as
    # direct proof. The proper-name expansion may be reviewed/approved, but
    # neither the initialism pattern nor the model's assertion licenses 100%.
    assert invalid == {"R009"}
    assert any("AWS" in note or "IAM" in note for note in notices)


def test_documented_restore_duty_is_typed_as_responsibility_not_unknown_other():
    req = requirement("R010", "Run a documented disaster-recovery restore exercise")
    typed = classify_requirement(req, req.jd_evidence)
    assert typed.kind == "responsibility"
    assert typed.requires_review is False


def test_mislabeled_completed_work_is_eligible_for_transferable_not_found_credit():
    req = requirement("R010", "Run a documented disaster-recovery restore exercise")
    text = "Paired with the night operator on recovery drills and measured recovery time."
    citation = EvidenceCitation(segment_id="S001", section="skills", text=text)
    row = RequirementAssessment(requirement_id="R010", status="not_matched",
                                evidence=text, evidence_ids=["S001"],
                                evidence_segments=[citation])
    proposal = UnifiedItem(requirement_id="R010", decision="transferable",
                           relation="overlap", evidence_ids=["S001"],
                           reason="Completed related recovery drills; no documented restore exercise established.")
    final = _final_unified_row(row, proposal, req, {"S001": ResumeSegment("S001", "skills", text)})
    assert final.unified_status == "Transferable"
    assert final.status == "not_matched"


def test_unverified_is_scored_only_as_provisional_verified_floor():
    criteria = [requirement("R001", "Task A"), requirement("R002", "Task B"),
                requirement("R003", "Task C")]
    assessments = [
        RequirementAssessment(requirement_id="R001", status="matched", unified_status="Found"),
        RequirementAssessment(requirement_id="R002", status="matched", unified_status="Unverified",
                              assessment_state="unverified"),
        RequirementAssessment(requirement_id="R003", status="not_matched", unified_status="Not Found"),
    ]
    candidate = score_candidate(candidate_name="Mariam", requirements=criteria,
                                assessments=assessments, evaluation_mode="mixed", errors=[])
    report = RankingReport(job_description_source="unit-test", jd_validation_mode="frozen",
                           yake_candidates=[], requirements=criteria, candidates=[candidate])
    weighted = weighted_candidate(report, candidate, ScoreWeights())
    ordered = weighted_leaderboard(report, ScoreWeights())
    assert candidate.primary_score is None  # preserves safe retry semantics
    assert weighted["score"] == 33.33
    assert weighted["possible_ceiling"] == 66.67
    assert weighted["unverified_ids"] == ["R002"]
    assert ordered[0]["rank"] is None  # Never officialize a lower bound
    assert ordered[0]["weighted_score"] is None
    assert ordered[0]["verified_floor"] == 33.33
    assert ordered[0]["provisional"] is True
    assert "Incomplete" in ordered[0]["review"]


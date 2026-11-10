"""V4.9.3: source-defined OR tenure, inclusive degrees and audit lifecycle.

All professions/fields are illustrative fixtures. Production contains no
candidate or occupational acceptance table.
"""
import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.qualification_validation import apply_qualification_checks, check_qualification
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (CandidateResult, EvidenceCitation, RankingReport,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.ui_support import final_leaderboard_rows
from cv_ranker.unified import UnifiedEvidenceEngine
from cv_ranker.ui.dashboard import _archive_current_run, _restore_archived_run


def typed(text, rid="R001"):
    r = ValidatedRequirement(requirement_id=rid, name=text, jd_evidence=text,
                             priority="required")
    return r.model_copy(update={"constraint": classify_requirement(r, text)})


@pytest.mark.parametrize("jd,cv", [
    ("Minimum 3 years of experience with Python or Django",
     "Experience:\n4 years of Django experience building web apps."),
    ("Minimum 3 years of inventory or logistics experience",
     "Experience:\n4 years of professional logistics experience in warehouses."),
    ("At least 3 years of professional nursing or clinical coordination experience",
     "Experience:\n4 years of clinical coordination experience in hospitals."),
])
def test_explicit_jd_or_options_share_numeric_threshold(jd, cv):
    requirement = typed(jd)
    assert requirement.constraint.subject and " or " in requirement.constraint.subject
    check = check_experience(requirement, cv)
    assert check.outcome == "sufficient", check
    assert check.claims and check.claims[0].lower_years == 4.0
    row = RequirementAssessment(requirement_id="R001", status="not_matched")
    out, _, changed = apply_experience_checks(
        requirements=[requirement], assessments=[row], resume_text=cv)
    assert changed and out[0].status == "matched"


def test_or_tenure_does_not_count_unrelated_duration():
    jd = "Minimum 3 years of inventory or logistics experience"
    check = check_experience(typed(jd),
                             "Experience:\n7 years of professional chemistry teaching.")
    assert check.outcome != "sufficient"


def test_mixed_and_or_stays_reviewed_instead_of_granting_partial_credit():
    jd = "Minimum 3 years of Python or Django and Kubernetes experience"
    check = check_experience(typed(jd), "Experience:\n4 years of Django experience.")
    assert check.outcome != "sufficient"


@pytest.mark.parametrize("jd,cv", [
    ("Completed Bachelor's degree in computing programs.",
     "Education:\nBS in Software Engineering, completed 2024."),
    ("Completed Bachelor's degree in business-related disciplines.",
     "Education:\nBachelor of Science in Accounting, completed 2024."),
    ("Completed Bachelor's degree in Computer Science or a related field.",
     "Education:\nBS in Software Engineering, completed 2024."),
])
def test_inclusive_field_family_defers_only_the_field_relationship_to_model(jd, cv):
    requirement = typed(jd, rid="R002")
    segments = segment_resume(cv)
    check = check_qualification(requirement, cv, segments)
    assert check.outcome == "field_semantic", check
    source = segments[0]
    model_found = RequirementAssessment(
        requirement_id="R002", status="matched", evidence_ids=[source.segment_id],
        evidence=source.text, evidence_segments=[EvidenceCitation(
            segment_id=source.segment_id, section=source.section, text=source.text)],
        reason="The candidate's completed degree falls in the JD's inclusive field family.",
    )
    rows, _, _ = apply_qualification_checks(
        requirements=[requirement], assessments=[model_found], resume_text=cv)
    assert rows[0].status == "matched" and rows[0].review_recommended
    # A category is not an automatic Python synonym: if the model rejects it,
    # the validator itself must never award a degree point.
    model_rejected = model_found.model_copy(update={"status": "not_matched"})
    rows, _, _ = apply_qualification_checks(
        requirements=[requirement], assessments=[model_rejected], resume_text=cv)
    assert rows[0].status == "not_matched"


def test_exact_field_mismatch_still_blocks_a_claimed_different_major():
    jd = "Completed Bachelor's degree in Computer Science."
    check = check_qualification(
        typed(jd), "Education:\nBS in Software Engineering, completed 2024.")
    assert check.outcome == "mismatch"


def test_broad_family_needs_cited_completion_and_correct_degree_level():
    jd = "Completed Bachelor's degree in computing programs."
    requirement = typed(jd, rid="R002")
    cv = "Education:\nMaster of Science in Software Engineering, completed 2024."
    assert check_qualification(requirement, cv).outcome != "field_semantic"
    cv = "Education:\nCurrently pursuing a BS in Software Engineering."
    assert check_qualification(requirement, cv).outcome != "field_semantic"


def test_historical_citation_notice_does_not_make_verified_result_provisional():
    requirement = typed("Quality assurance")
    cv = "Quality assurance"
    source = ResumeSegment("S001", "skills", cv)
    assessment = RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence=cv, evidence_ids=["S001"],
        evidence_segments=[EvidenceCitation(segment_id="S001", section="skills", text=cv)],
        reason="The candidate lists quality assurance as a skill.")
    candidate = score_candidate(
        candidate_name="Anonymous", requirements=[requirement], assessments=[assessment],
        evaluation_mode="llm_assessed", errors=[
            "R001: first-pass citation corrected; final proof was source-grounded."])
    report = RankingReport(job_description_source="jd.txt", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[requirement], candidates=[candidate])
    final = reconcile_unified_candidate(
        report, 0, [{"segment_id": "S001", "section": "skills", "text": cv}])
    assert final["Provisional"] is False
    assert len(final["Notices"]) == 1
    assert final_leaderboard_rows(report, {"0": final})[0]["Review"] == "Complete"


class FlatEncoder:
    fingerprint = "generic-source-audit-encoder"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class BrokenFirstCitation:
    disabled_reason = None
    def __init__(self):
        self.calls = 0
    def prompt_fits(self, *_):
        return True
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        prompt = json.loads(user_prompt)
        return schema.model_validate({r["id"]: {
            "decision": "found",
            "evidence_ids": ["S999" if self.calls == 1 else "S001"],
            "matched_term": "Quality assurance",
            "reason": "The CV lists quality assurance as a positive self-reported skill.",
        } for r in prompt["requirements"]})


def test_repaired_technical_source_error_is_audit_history_not_live_failure(tmp_path):
    requirement = typed("Quality assurance")
    source = ResumeSegment("S001", "skills", "Quality assurance")
    model = BrokenFirstCitation()
    with UnifiedEvidenceEngine(Settings(llm_provider="ollama"), model,
                               encoder=FlatEncoder(), cache_path=tmp_path / "cache.db") as engine:
        rows, metrics = engine.assess([requirement], [source], source.text,
                                      candidate_id="generic-audit-history")
    assert model.calls == 2
    assert rows[0].unified_status == "Found"
    assert metrics.unresolved_criteria == 0
    assert metrics.warnings == []
    assert metrics.resolved_validation_notices


class SourceProbe:
    disabled_reason = None
    def __init__(self):
        self.prompts = []
    def prompt_fits(self, *_):
        return True
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        prompt = json.loads(user_prompt)
        self.prompts.append(prompt)
        return schema.model_validate({r["id"]: {
            "decision": "not_found", "evidence_ids": [], "matched_term": None,
            "reason": "The candidate's qualification remains for model review.",
        } for r in prompt["requirements"]})


def test_degree_section_reaches_model_when_embedding_top_one_is_unrelated(tmp_path):
    req = typed("Completed Bachelor's degree in computing programs.")
    segments = [
        ResumeSegment("S001", "projects", "Repaired machinery in production."),
        ResumeSegment("S002", "education", "BS in Software Engineering, completed 2024."),
    ]
    model = SourceProbe()
    with UnifiedEvidenceEngine(Settings(llm_provider="ollama"), model,
                               encoder=FlatEncoder(), top_k=1,
                               cache_path=tmp_path / "typed-retrieval.db") as engine:
        engine.assess([req], segments, "\n".join(s.text for s in segments),
                      candidate_id="generic-typed-source")
    assert model.prompts and model.prompts[0]["sources"][0]["id"] == "S002"


def test_last_three_session_reports_are_recoverable_without_external_storage():
    state = {"cv_ranking_report": {"candidates": [{"candidate_name": "Run A"}]},
             "cv_run_label": "Run A", "cv_source_ledgers": {"0": [{"segment_id": "S001"}]}}
    for name in ("Run B", "Run C", "Run D", "Run E"):
        _archive_current_run(state)
        state["cv_run_label"] = name
        state["cv_ranking_report"] = {"candidates": [{"candidate_name": name}]}
    assert [h["cv_run_label"] for h in state["cv_run_history"]] == [
        "Run D", "Run C", "Run B"]
    _restore_archived_run(state, 1)
    assert state["cv_run_label"] == "Run C"
    assert state["cv_ranking_report"]["candidates"][0]["candidate_name"] == "Run C"
    assert state["cv_source_ledgers"]["0"][0]["segment_id"] == "S001"
    assert [h["cv_run_label"] for h in state["cv_run_history"]] == [
        "Run E", "Run D", "Run B"]

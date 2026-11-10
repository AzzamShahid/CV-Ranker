"""Regressions from the reported Phase 7G live assessment failures.

These cover decision and citation contracts, not provider-specific canned aliases.
"""

import json

import numpy as np
import pytest

from cv_ranker.assessor import _validate_rows
from cv_ranker.config import Settings
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.jd import SYSTEM_PROMPT as JD_PROMPT
from cv_ranker.qualification_validation import apply_qualification_checks
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.unified import (
    FINAL_ADJUDICATION_PROMPT, UNIFIED_PROMPT, UnifiedEvidenceEngine,
    UnifiedItem, UnifiedResponse, _final_unified_row, _keyed_response_schema, _map_response,
    _repair_nonatomic_source_metadata,
)


def requirement(name, *, rid="R001", kind="skill", **attrs):
    return ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority="required",
        constraint=RequirementConstraint(kind=kind, origin="source_rules", **attrs),
    )


def test_prompt_contracts_ask_for_complete_jd_and_semantically_aligned_decisions():
    for wording in ("A or B", "numeric minimums", "EXACT CONTIGUOUS", "priority"):
        assert wording.casefold() in JD_PROMPT.casefold()
    for prompt in (UNIFIED_PROMPT, FINAL_ADJUDICATION_PROMPT):
        lowered = prompt.casefold()
        assert "relation" in lowered
        assert "transferable" in lowered
        assert "completed" in lowered
        assert "not_found" in lowered
        assert "experience" in lowered
        assert "degree" in lowered
        assert "reason" in lowered


def test_live_schema_requires_semantic_relation_without_breaking_old_test_doubles():
    strict_schema = _keyed_response_schema(("R001",), strict_relation=True)
    with pytest.raises(Exception):
        strict_schema.model_validate({"R001": {
            "decision": "not_found", "reason": "The CV has no supporting claim.",
            "evidence_ids": [], "matched_term": None}})
    assert _keyed_response_schema(("R001",)).model_validate({"R001": {
        "decision": "not_found", "reason": "The CV has no supporting claim.",
        "evidence_ids": [], "matched_term": None}})


def test_four_distinct_valid_model_citations_do_not_invalidate_one_skill():
    req = requirement("Predictive modeling")
    sources = {f"S{i:03}": ResumeSegment(f"S{i:03}", "experience", "Built prediction models.")
               for i in range(1, 5)}
    raw = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R001", decision="found", relation="entailed",
        evidence_ids=list(sources), matched_term="prediction pipeline from the JD",
        reason="Built prediction models for real-world tasks using observed data.",
    )])
    notices = []
    response, proposed, invalid = _map_response(
        raw, [req], set(sources), normalized_notices=notices)
    assert not invalid
    assert len(response.assessments[0].evidence_ids) == 3
    assert len(notices) == 1
    response = _repair_nonatomic_source_metadata(
        response, [req], sources, semantic_grounded_ids={"R001"})
    assert response.assessments[0].matched_term is None
    checked, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req], resume_text="Built prediction models.",
        segments=list(sources.values()), semantic_grounded_ids={"R001"})
    assert not invalid, warnings
    assert checked["R001"].status == "matched"
    row = _final_unified_row(checked["R001"], proposed["R001"], req, sources)
    assert row.unified_status == "Found" and row.review_recommended


@pytest.mark.parametrize("degree", [
    "BS Software Engineering | City University, 2021",
    "BS Information Technology | City University, 2021",
    "MSc Artificial Intelligence | City University, 2021",
])
def test_model_related_degree_explanation_cannot_leave_an_unscored_overlap_not_found(degree):
    req = requirement("Completed Bachelor's degree in Computer Science.",
                      rid="R002", kind="education", degree_level="bachelor",
                      field_of_study="Computer Science")
    original = {"S001": ResumeSegment("S001", "education", degree)}
    raw = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R002", decision="not_found", relation="overlap",
        evidence_ids=["S001"], reason="The applicant has a completed closely related degree.",
    )])
    response, proposals, invalid = _map_response(raw, [req], set(original))
    assert not invalid and proposals["R002"].decision == "transferable"
    checked, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[req], resume_text=f"Education\n{degree}",
        segments=list(original.values()))
    assert not invalid, warnings
    row = _final_unified_row(checked["R002"], proposals["R002"], req, original)
    final, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[row], resume_text=f"Education\n{degree}")
    assert final[0].unified_status == "Transferable"
    assert final[0].status != "matched"


@pytest.mark.parametrize("bad_ids", [
    ["S001", "S001", "S002", "S003"],
    ["S001", "S002", "S003", "S999"],
])
def test_duplicate_or_unprovided_citations_still_invalidate_model(bad_ids):
    req = requirement("Inventory control")
    raw = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R001", decision="found", relation="entailed",
        evidence_ids=bad_ids, reason="Managed inventory movement in a warehouse.")])
    _, _, invalid = _map_response(raw, [req], {"S001", "S002", "S003"})
    assert invalid == {"R001"}


def test_four_years_of_relevant_work_can_reuse_cited_duty_and_link_its_dated_heading():
    req = requirement("Minimum 3 years of professional warehouse scheduling experience",
                      kind="experience", minimum_years=3, subject="warehouse scheduling")
    cv = ("Experience\n"
          "Operations Planner | Supply Organization | Jan 2022 - Oct 2026\n"
          "- Developed warehouse scheduling workflows for logistics dispatch.\n")
    segments = segment_resume(cv)
    check = check_experience(req, cv, segments)
    assert check.outcome == "role_semantic"
    role = check.role_groups[0][0]
    duty_id = role.duty_segment_ids[0]
    original = next(s for s in segments if s.segment_id == duty_id)
    llm_row = RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence_ids=[duty_id], evidence_segments=[EvidenceCitation(
            segment_id=duty_id, section=original.section, text=original.text)],
        evidence=original.text, reason="Developed warehouse scheduling workflows in a dated role.")
    rows, _, _ = apply_experience_checks(
        requirements=[req], assessments=[llm_row], resume_text=cv)
    assert rows[0].status == "matched"
    assert role.role_segment_id in rows[0].evidence_ids
    assert duty_id in rows[0].evidence_ids


class FlatEncoder:
    fingerprint = "v498-four-citation-live-regression"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class VerboseSemanticProvider:
    disabled_reason = None

    def __init__(self):
        self.settings = Settings(llm_provider="ollama")
        self.calls = 0

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        payload = json.loads(user_prompt)
        ids = [source["id"] for source in payload["sources"]]
        return schema.model_validate({"R001": {
            "decision": "found", "relation": "entailed", "evidence_ids": ids,
            "matched_term": "Machine Learning",  # invalid invented highlight
            "reason": "Trained classifiers and evaluated predictions on recorded data.",
        }})


def test_four_citation_abstract_competency_keeps_candidate_rankable(tmp_path):
    req = requirement("Predictive modeling")
    cv = ("Experience\n"
          "Trained classifiers using labeled images.\n"
          "Built automated outcome scoring workflows.\n"
          "Evaluated prediction quality against a holdout set.\n"
          "Deployed prediction service for customer queries.")
    segments = segment_resume(cv)
    assert len(segments) >= 4
    provider = VerboseSemanticProvider()
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=8,
                               cache_path=tmp_path / "semantic.sqlite") as engine:
        rows, metrics = engine.assess([req], segments, cv,
                                      candidate_id="completed-work-sample")
    assert rows[0].unified_status == "Found", (rows, metrics.public())
    assert metrics.unresolved_criteria == 0
    assert provider.calls == 1

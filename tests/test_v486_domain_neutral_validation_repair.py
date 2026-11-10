"""Cross-domain grading and model-response contracts; no skill catalogue."""

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.text_utils import phrase_present
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse,
                               _map_response, _repair_nonatomic_source_metadata)


def _req(rid, name, priority="required", kind="skill", operator="single"):
    return ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority=priority,
        constraint=RequirementConstraint(kind=kind, operator=operator))


class FlatEncoder:
    fingerprint = "v486-static-test-embedding-contract"

    def embed_documents(self, texts):
        return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)

    def embed_queries(self, texts):
        return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)


class GroupedLLM:
    disabled_reason = None

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        return next(self.responses)


def test_missing_row_and_invented_quote_cannot_create_a_fabricated_score(tmp_path):
    """Work with independently authored logistics/safety examples, not a named CV."""
    text = ("Professional Experience:\n"
            "- Delivered monthly supplier inventory reports.\n"
            "- Implemented safety inspections across four warehouses.\n")
    segments = segment_resume(text)
    ids = {"reports": next(s.segment_id for s in segments if "inventory reports" in s.text),
           "inspections": next(s.segment_id for s in segments if "safety inspections" in s.text)}
    reqs = [_req("R1", "Supplier demand forecasting"),
            _req("R2", "Safety inspections")]
    first = UnifiedResponse(assessments=[UnifiedItem(
        requirement_id="R1", decision="found", evidence_ids=[ids["reports"]],
        matched_term="forecasting", reason="Invented a nonexistent forecasting activity.")])
    second = UnifiedResponse(assessments=[
        UnifiedItem(requirement_id="R1", decision="found", evidence_ids=[ids["reports"]],
                    matched_term="forecasting", reason="Still lacks actual forecast evidence."),
        UnifiedItem(requirement_id="R2", decision="found", evidence_ids=[ids["inspections"]],
                    reason="Completed safety inspections are directly described.")])
    llm = GroupedLLM([first, second])
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "cache.sqlite", encoder=FlatEncoder())
    try:
        assessed, metrics = engine.assess(reqs, segments, text, candidate_id="cross-domain-fixture")
    finally:
        engine.close()
    assert llm.calls == 3 and metrics.correction_calls == 1
    assert metrics.final_verification_calls == 1
    assert assessed[0].unified_status == "Unverified"
    assert assessed[1].unified_status == "Found"
    assert metrics.unresolved_ids == ["R1"]
    result = score_candidate(candidate_name="Neutral", requirements=reqs,
                             assessments=assessed, evaluation_mode="llm_assessed", errors=[])
    assert result.primary_score is None and result.matched_required == 1


def test_unrelated_completed_work_cannot_rescue_invented_task_quote():
    req = _req("R101", "Warehouse inventory forecasting")
    segment = ResumeSegment("S001", "experience", "Delivered warehouse inventory reports.", (1,))
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id=req.requirement_id, status="matched", evidence_ids=["S001"],
        matched_term="forecasting", reason="Unsupported forecast claim.")])
    cleaned = _repair_nonatomic_source_metadata(response, [req], {"S001": segment})
    assert cleaned.assessments[0].matched_term == "forecasting"  # Still invalid.


def test_grammatical_overlap_does_not_automatically_override_semantic_verdict():
    req = _req("R101", "Medical imaging", priority="preferred")
    citation = ResumeSegment("S001", "experience", "Designed a medical-image triage pilot on public data.")
    proposal = LLMAssessmentItem(requirement_id="R101", status="not_matched",
                                 evidence_ids=["S001"], reason="Model considers only overlap.")
    repaired = _repair_nonatomic_source_metadata(
        LLMCandidateAssessmentResponse(assessments=[proposal]), [req], {"S001": citation})
    assert repaired.assessments[0].status == "not_matched"


def test_only_duplicate_identical_model_substance_may_be_collapsed():
    req = _req("R101", "AtomicTool")
    first = UnifiedItem(requirement_id="R101", decision="found", evidence_ids=["S001"],
                        matched_term="AtomicTool", reason="The CV lists the exact tool.")
    same = first.model_copy(update={"reason": "Identical decision from a duplicated row."})
    converted, _, invalid = _map_response(UnifiedResponse(assessments=[first, same]),
                                          [req], {"S001"})
    assert invalid == {"R101"} and not converted.assessments
    conflict = first.model_copy(update={"decision": "not_found", "evidence_ids": []})
    _, _, invalid = _map_response(UnifiedResponse(assessments=[first, conflict]),
                                  [req], {"S001"})
    assert invalid == {"R101"}


def test_whole_word_punctuation_is_generic_not_skill_specific():
    assert phrase_present("Deep Learning", "Shipped deep-learning software")
    assert phrase_present("Patient records", "Patient-records workflow")
    assert not phrase_present("Go", "Good communicator")
    assert not phrase_present("SQL", "NoSQL databases")

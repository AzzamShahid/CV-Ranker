"""Deterministic guards and evaluation-only batch-size probe regression tests."""
import json

import pytest

from cv_ranker.assessor import assess_resume
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
from cv_ranker.segments import segment_resume
from evaluation.evaluate_benchmark import RowResult, _save_json


class Replies:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.settings = type("S", (), {"assessment_batch_size": 20})()
        self.calls = 0

    def invoke_structured(self, **_):
        self.calls += 1
        return next(self.answers)


def result(name, cv, initial, corrected):
    segments = segment_resume(cv)
    positive = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status=initial, evidence_ids=[segments[0].segment_id]
    )])
    negative = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status=corrected, evidence_ids=[]
    )])
    llm = Replies(positive, negative)
    req = ValidatedRequirement(requirement_id="R001", name=name, priority="required", jd_evidence=name)
    rows, mode, warnings = assess_resume(resume_text=cv, requirements=[req], llm=llm)
    return rows[0], mode, warnings, llm.calls


def test_uncertain_from_bare_title_requires_correction():
    row, mode, warnings, calls = result("Machine Learning", "Experience:\nMachine Learning Engineer\n", "uncertain", "not_matched")
    assert row.status == "not_matched"
    assert mode == "llm_assessed" and calls == 2
    assert any("no qualifying capability evidence" in msg for msg in warnings)


def test_uncertain_from_degree_only_not_skill():
    row, mode, warnings, calls = result("Machine Learning", "Education:\nBachelor of Science in Machine Learning\n", "uncertain", "not_matched")
    assert row.status == "not_matched"
    assert mode == "llm_assessed" and calls == 2


def test_uncertain_from_actual_learning_evidence_remains_valid():
    segments = segment_resume("Skills:\nCurrently learning Kubernetes.\n")
    reply = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status="uncertain", evidence_ids=[segments[0].segment_id]
    )])
    llm = Replies(reply)
    req = ValidatedRequirement(requirement_id="R001", name="Kubernetes", priority="required", jd_evidence="Kubernetes")
    rows, mode, warnings = assess_resume(resume_text="Skills:\nCurrently learning Kubernetes.\n", requirements=[req], llm=llm)
    assert rows[0].status == "uncertain"
    assert mode == "llm_assessed" and llm.calls == 1


def test_benchmark_output_includes_requested_batch_size(tmp_path):
    row = RowResult("s", "R001", "Python", "exact", "matched", "matched", "llm_assessed", ["S001"], "Python", "Python", True)
    p = tmp_path / "batch.json"
    metrics = {
        "total": 1, "correct": 1, "accuracy": 1.0,
        "matched_precision": 1.0, "matched_recall": 1.0, "matched_f1": 1.0,
        "by_category": {"exact": 1.0}, "confusion": {("matched", "matched"): 1},
    }
    _save_json(p, [row], metrics, scope="assessment", model="qwen2.5:3b", batch_size=3)
    payload = json.loads(p.read_text())
    assert payload["assessment_batch_size"] == 3
    assert payload["metrics"]["correct"] == 1


def test_compare_batch_results_tracks_changes_and_provenance():
    from evaluation.compare_batch_runs import compare_batch_results
    base = {
        "build_id": "b", "assessment_protocol": "p", "benchmark_data_sha256": "h", "scope": "assessment", "model": "m",
        "assessment_batch_size": 20, "metrics": {"accuracy": 0.0},
        "measurement_quality": {"valid_live_llm_measurement": False},
        "rows": [{"scenario_id": "x", "requirement_id": "R001", "requirement_name": "Python", "expected": "matched", "predicted": "not_matched", "correct": False}],
    }
    probe = json.loads(json.dumps(base))
    probe["assessment_batch_size"] = 3
    probe["metrics"]["accuracy"] = 1.0
    probe["rows"][0]["predicted"] = "matched"
    probe["rows"][0]["correct"] = True
    compared = compare_batch_results(base, probe)
    assert len(compared["different_statuses"]) == 1
    assert compared["probe_accuracy"] == 1
    probe["build_id"] = "different"
    with pytest.raises(ValueError, match="build_id"):
        compare_batch_results(base, probe)

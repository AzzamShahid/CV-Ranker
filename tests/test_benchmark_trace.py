"""Trace raw structured model decisions separately from Python scoring decisions."""
import json

from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse
from evaluation.trace import RecordingLLM
from evaluation.evaluate_benchmark import _attach_raw_observation, _raw_diagnostics, RowResult, _assessment_rows


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.settings = type("SettingsStub", (), {"assessment_batch_size": 20})()
        self.disabled_reason = None

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        return next(self.responses)


def response(status, evidence_ids=None, matched_term=None):
    return LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status=status,
        evidence_ids=evidence_ids or [], matched_term=matched_term
    )])


def row(predicted, expected="matched"):
    return RowResult("case", "R001", "Python", "exact", expected, predicted,
                     "mixed", [], None, None, predicted == expected)


def test_trace_records_raw_before_python_override():
    recorder = RecordingLLM(FakeLLM([response("not_matched")]))
    output = recorder.invoke_structured(
        system_prompt="You evaluate one resume against fixed requirements",
        user_prompt="irrelevant", schema=LLMCandidateAssessmentResponse
    )
    assert output.assessments[0].status == "not_matched"
    item = _attach_raw_observation(row("matched"), recorder.observations()["R001"])
    assert item.raw_initial_status == "not_matched"
    assert item.raw_final_status == "not_matched"
    assert item.decision_path == "python_or_fallback_changed_status"
    assert _raw_diagnostics([item])["post_model_status_changes"] == 1


def test_trace_distinguishes_llm_correction_from_python_change():
    recorder = RecordingLLM(FakeLLM([response("matched", ["S999"]), response("uncertain", ["S001"])]))
    recorder.invoke_structured(system_prompt="You evaluate one resume", user_prompt="", schema=LLMCandidateAssessmentResponse)
    recorder.invoke_structured(system_prompt="You are correcting invalid rows", user_prompt="", schema=LLMCandidateAssessmentResponse)
    observed = recorder.observations()["R001"]
    item = _attach_raw_observation(row("uncertain", expected="uncertain"), observed)
    assert item.raw_initial_status == "matched"
    assert item.raw_final_status == "uncertain"
    assert item.llm_attempts == 2
    assert item.decision_path == "llm_correction_agreed_with_final"
    assert _raw_diagnostics([item])["model_retry_status_changes"] == 1


def test_assessment_benchmark_captures_direct_guard_override(monkeypatch):
    from evaluation import evaluate_benchmark as benchmark
    monkeypatch.setattr(benchmark, "StructuredLLM", lambda settings: FakeLLM([response("not_matched")]))
    scenario = {
        "id": "test", "resume_text": "Skills:\nPython\n",
        "requirements": [{"id": "R001", "name": "Python", "priority": "required",
                          "expected_status": "matched", "category": "exact"}],
    }
    results = _assessment_rows(scenario, "fake")
    assert results[0].predicted == "matched"
    assert results[0].raw_final_status == "not_matched"
    assert results[0].decision_path == "python_or_fallback_changed_status"
    assert results[0].evaluation_mode == "mixed"


def test_missing_raw_status_never_invents_model_accuracy():
    item = _attach_raw_observation(row("matched"), None)
    metrics = _raw_diagnostics([item])
    assert metrics["raw_model_status_coverage"] == 0
    assert metrics["raw_status_accuracy_on_observed"] is None


def test_full_pipeline_benchmark_records_raw_status(monkeypatch):
    import cv_ranker.pipeline as pipeline_module
    from cv_ranker.schemas import JDRequirement, JDValidationResponse
    from evaluation.evaluate_benchmark import _pipeline_rows

    class FakePipelineLLM:
        def __init__(self, settings):
            self.settings = settings
            self.disabled_reason = None

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            if schema is JDValidationResponse:
                return JDValidationResponse(requirements=[JDRequirement(
                    name="Python", priority="required", evidence="Python"
                )])
            return response("not_matched")

    monkeypatch.setattr(pipeline_module, "StructuredLLM", FakePipelineLLM)
    scenario = {
        "id": "pipeline_trace", "resume_text": "Skills:\nPython\nBuilt production services using Python.\n",
        "requirements": [{"id": "R001", "name": "Python", "priority": "required",
                          "expected_status": "matched", "category": "exact"}],
    }
    rows = _pipeline_rows(scenario, "fake")
    assert len(rows) == 1
    assert rows[0].raw_initial_status == "not_matched"
    assert rows[0].predicted == "matched"
    assert rows[0].decision_path == "python_or_fallback_changed_status"
    assert rows[0].evaluation_mode == "jd:llm_validated;cv:mixed"

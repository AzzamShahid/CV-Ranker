"""No behavioral changes: focused and grouped model attempts must be observable."""
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse
from evaluation.trace import RecordingLLM
from evaluation.evaluate_benchmark import RowResult, _attach_raw_observation, _measurement_quality


def response(status, evidence_ids=(), term=None):
    return LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status=status,
        evidence_ids=list(evidence_ids), matched_term=term
    )])


class Delegate:
    def __init__(self, *responses):
        self.responses = iter(responses)

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        return next(self.responses)


def test_focused_retry_is_not_collapsed_into_grouped_second_look():
    record = RecordingLLM(Delegate(
        response("not_matched"),
        response("matched", ["S001"]),
        response("not_matched"),
    ))
    record.invoke_structured(system_prompt="Initial task", user_prompt="Evaluate", schema=LLMCandidateAssessmentResponse)
    record.invoke_structured(system_prompt="Correcting invalid rows", user_prompt="SECOND LOOK AT POSSIBLE FALSE NEGATIVES", schema=LLMCandidateAssessmentResponse)
    record.invoke_structured(system_prompt="Correcting invalid rows", user_prompt="SECOND LOOK FOCUSED ABBREVIATION CLARIFICATION", schema=LLMCandidateAssessmentResponse)
    observation = record.observations()["R001"]
    assert [a["phase"] for a in observation["attempt_history"]] == ["initial", "second_look", "focused_abbreviation"]
    assert observation["focused_abbreviation"] is True
    assert observation["attempts"] == 3
    assert observation["last_status"] == "not_matched"
    assert observation["attempt_history"][1]["evidence_ids"] == ["S001"]

    row = RowResult("semantic_positive", "R001", "Natural Language Processing", "semantic_abbreviation",
                    "matched", "not_matched", "llm_assessed", [], None, None, False)
    _attach_raw_observation(row, observation)
    assert row.decision_path == "llm_focused_abbreviation_agreed_with_final"
    assert _measurement_quality([row], "assessment")["llm_focused_abbreviation_rows"] == ["semantic_positive/R001"]


def test_history_keeps_actual_source_terms_without_full_prompt_or_cv_text():
    recorder = RecordingLLM(Delegate(response("matched", ["S002"], "NLP")))
    recorder.invoke_structured(system_prompt="system includes secret", user_prompt="resume PII 123",
                               schema=LLMCandidateAssessmentResponse)
    observation = recorder.observations()["R001"]
    history = observation["attempt_history"]
    assert history[0]["matched_term"] == "NLP"
    assert "prompt" not in history[0] and "resume" not in history[0]
    assert "system includes secret" not in str(history)


def test_explicit_focus_phase_still_counts_as_second_look_for_old_reports():
    recorder = RecordingLLM(Delegate(response("matched", ["S001"], "GCP")))
    recorder.invoke_structured(system_prompt="Correction", user_prompt="SECOND LOOK FOCUSED ABBREVIATION CLARIFICATION",
                               schema=LLMCandidateAssessmentResponse)
    assert recorder.observations()["R001"]["second_look"] is True


def test_cli_can_isolate_single_scenario_and_toggle_only_focused_retry(monkeypatch):
    import sys
    from evaluation import evaluate_benchmark as benchmark

    scenarios = [
        {"id": "semantic_positive", "resume_text": "Skills:\nNLP\n", "requirements": [
            {"id": "R001", "name": "Natural Language Processing", "priority": "required", "expected_status": "matched"}]},
        {"id": "different_case", "resume_text": "Skills:\nDocker\n", "requirements": [
            {"id": "R001", "name": "Docker", "priority": "required", "expected_status": "matched"}]},
    ]
    seen = []

    def fake_rows(scenario, model, batch_size, second_look, focused_abbreviation):
        seen.append((scenario["id"], second_look, focused_abbreviation))
        return [RowResult(scenario["id"], "R001", "Natural Language Processing", "exact",
                          "matched", "matched", "llm_assessed", [], None, None, True)]

    monkeypatch.setattr(benchmark, "_load", lambda _: {"scenarios": scenarios})
    monkeypatch.setattr(benchmark, "_assessment_rows", fake_rows)
    monkeypatch.setattr(sys, "argv", ["benchmark", "--scope", "assessment", "--scenario", "semantic_positive", "--no-focused-abbreviation"])
    assert benchmark.main() == 0
    assert seen == [("semantic_positive", True, False)]

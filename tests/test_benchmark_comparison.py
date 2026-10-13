from copy import deepcopy

import pytest

from evaluation.compare_benchmarks import compare, load_report
from evaluation.evaluate_benchmark import RowResult, _measurement_quality, _metrics, _save_json, _load


def make_row(id, expected, predicted, mode="llm_assessed"):
    return RowResult("s", id, f"skill {id}", "semantic", expected, predicted, mode, [], None, None, expected == predicted)


def test_quality_rejects_fallback_and_mixed_even_with_perfect_accuracy():
    rows = [make_row("R1", "matched", "matched", mode="fallback_exact")]
    assert _metrics(rows)["accuracy"] == 1.0
    assert not _measurement_quality(rows, "assessment")["valid_live_llm_measurement"]
    rows[0].evaluation_mode = "mixed"
    assert not _measurement_quality(rows, "assessment")["valid_live_llm_measurement"]
    rows[0].evaluation_mode = "llm_assessed"
    assert _measurement_quality(rows, "assessment")["valid_live_llm_measurement"]


def test_pipeline_quality_requires_both_live_jd_and_live_assessment():
    rows = [make_row("R1", "matched", "matched", mode="jd:fallback_structural;cv:llm_assessed")]
    assert not _measurement_quality(rows, "pipeline")["valid_live_llm_measurement"]
    rows[0].evaluation_mode = "jd:llm_validated;cv:llm_assessed"
    assert _measurement_quality(rows, "pipeline")["valid_live_llm_measurement"]


def test_benchmark_load_rejects_duplicate_requirements(tmp_path):
    from evaluation.evaluate_benchmark import DEFAULT_DATA
    data = _load(DEFAULT_DATA)
    data = deepcopy(data)
    data["scenarios"][0]["requirements"].append(data["scenarios"][0]["requirements"][0])
    path = tmp_path / "data.json"
    path.write_text(__import__("json").dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate requirement ID"):
        _load(path)


def report(scope, predicted, *, name="llm_assessed"):
    quality_mode = name if scope == "assessment" else f"jd:llm_validated;cv:{name}"
    return {
        "scope": scope, "model": "qwen2.5:3b", "build_id": "x", "assessment_protocol": "segment",
        "benchmark_data_sha256": "hash", "measurement_quality": {"valid_live_llm_measurement": name == "llm_assessed"},
        "metrics": {"accuracy": int(predicted == "matched")},
        "rows": [{"scenario_id": "s", "requirement_id": "R1", "requirement_name": "skill R1",
                  "expected": "matched", "predicted": predicted, "correct": predicted == "matched", "evaluation_mode": quality_mode}],
    }


def test_comparison_attributes_lost_jd_requirement_and_checks_provenance():
    result = compare(report("assessment", "matched"), report("pipeline", "missing_requirement"))
    assert result["comparable"]
    assert result["counts"]["jd_requirement_lost_or_renamed"] == 1
    assert result["differences"][0]["assessment_prediction"] == "matched"
    other = report("pipeline", "matched")
    other["build_id"] = "different"
    assert not compare(report("assessment", "matched"), other)["comparable"]


def test_benchmark_json_includes_build_dataset_and_quality(tmp_path):
    from evaluation.evaluate_benchmark import DEFAULT_DATA
    rows = [make_row("R1", "matched", "matched")]
    path = tmp_path / "result.json"
    _save_json(path, rows, _metrics(rows), scope="assessment", model="qwen2.5:3b", data_path=DEFAULT_DATA)
    result = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert result["benchmark_data_sha256"]
    assert result["build_id"]
    assert result["measurement_quality"]["valid_live_llm_measurement"]


def test_valid_benchmark_can_complete_with_incorrect_model_predictions(monkeypatch):
    import sys
    from evaluation import evaluate_benchmark as runner

    label = {"scenarios": [{"id": "s", "requirements": [{"id": "R1", "name": "Python", "priority": "required", "expected_status": "matched", "category": "exact"}], "resume_text": "Python"}]}
    monkeypatch.setattr(runner, "_load", lambda _: label)
    monkeypatch.setattr(runner, "_assessment_rows", lambda *_: [make_row("R1", "matched", "not_matched")])
    monkeypatch.setattr(sys, "argv", ["evaluate_benchmark.py", "--scope", "assessment"])
    assert runner.main() == 0  # Real measurements don't require perfect predictions.
    monkeypatch.setattr(runner, "_assessment_rows", lambda *_: [make_row("R1", "matched", "matched", mode="mixed")])
    assert runner.main() == 3  # Contaminated measurements are invalid, even at 100%.


def test_comparison_refuses_different_row_sets():
    a = report("assessment", "matched")
    p = report("pipeline", "matched")
    p["rows"][0]["requirement_id"] = "R999"
    result = compare(a, p)
    assert not result["comparable"]
    assert any("row sets differ" in msg for msg in result["compatibility_issues"])

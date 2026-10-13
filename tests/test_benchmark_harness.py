import json
from pathlib import Path

from evaluation.evaluate_benchmark import _load, _metrics, RowResult


def test_benchmark_dataset_is_human_reviewable_and_valid():
    path = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_cases.json"
    data = _load(path)
    assert data["benchmark_version"] == 1
    assert len(data["scenarios"]) >= 5
    categories = set()
    total = 0
    for scenario in data["scenarios"]:
        assert scenario["id"]
        assert scenario["description"]
        assert scenario["resume_text"].strip()
        assert scenario["requirements"]
        ids = set()
        for req in scenario["requirements"]:
            total += 1
            assert req["id"] not in ids
            ids.add(req["id"])
            assert req["expected_status"] in {"matched", "not_matched", "uncertain"}
            assert req["priority"] in {"required", "preferred", "unknown"}
            assert req["rationale"].strip()
            categories.add(req["category"])
    assert total >= 20
    assert {"semantic_paraphrase", "negation", "learning_only", "title_degree_only", "prompt_injection"} <= categories


def test_benchmark_metrics_are_computed_without_touching_production_logic():
    rows = [
        RowResult("s", "R1", "A", "exact", "matched", "matched", "llm_assessed", [], None, None, True),
        RowResult("s", "R2", "B", "absent", "not_matched", "matched", "llm_assessed", [], None, None, False),
        RowResult("s", "R3", "C", "learning_only", "uncertain", "uncertain", "llm_assessed", [], None, None, True),
    ]
    metrics = _metrics(rows)
    assert metrics["total"] == 3
    assert metrics["correct"] == 2
    assert round(metrics["accuracy"], 4) == round(2 / 3, 4)
    assert metrics["matched_precision"] == 0.5
    assert metrics["matched_recall"] == 1.0

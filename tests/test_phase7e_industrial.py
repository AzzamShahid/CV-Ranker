"""Regression tests for Phase 7E benchmark, not the production ranker."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evaluation.compare_industrial import compare
from evaluation.evaluate_industrial import (DEFAULT_DATASET, dataset_hash, evaluate,
                                             load_dataset, rank_metrics, requirement_metrics)


def test_frozen_fixture_counts_and_independent_label_coverage():
    ds = load_dataset(DEFAULT_DATASET)
    assert len(ds["scenarios"]) == 8
    assert ds["candidate_count"] == 40
    assert sum(len(s["candidates"]) * len(s["requirements"]) for s in ds["scenarios"]) == 200
    assert len(dataset_hash(DEFAULT_DATASET, ds)) == 64


def test_quote_tamper_rejected(tmp_path):
    ds = load_dataset(DEFAULT_DATASET)
    one = copy.deepcopy(ds["scenarios"][0])
    jd_source = DEFAULT_DATASET / one["jd_path"]
    resume_source = DEFAULT_DATASET / one["candidates"][0]["resume_path"]
    (tmp_path / one["jd_path"]).parent.mkdir(parents=True)
    (tmp_path / one["jd_path"]).write_bytes(jd_source.read_bytes())
    rp = tmp_path / one["candidates"][0]["resume_path"]
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_bytes(resume_source.read_bytes())
    one["candidates"] = [one["candidates"][0]]
    one["candidates"][0]["labels"][0]["evidence_quote"] = "Claim not actually in CV"
    (tmp_path / "labels.json").write_text(json.dumps({"schema_version": 1, "dataset_id": "bad", "scenarios": [one]}))
    with pytest.raises(ValueError, match="quote absent"):
        load_dataset(tmp_path)


def test_incomplete_or_duplicate_labels_fail_closed(tmp_path):
    ds = load_dataset(DEFAULT_DATASET)
    s = copy.deepcopy(ds["scenarios"][0])
    (tmp_path / s["jd_path"]).parent.mkdir(parents=True)
    (tmp_path / s["jd_path"]).write_bytes((DEFAULT_DATASET / s["jd_path"]).read_bytes())
    c = s["candidates"][0]
    (tmp_path / c["resume_path"]).parent.mkdir(parents=True)
    (tmp_path / c["resume_path"]).write_bytes((DEFAULT_DATASET / c["resume_path"]).read_bytes())
    s["candidates"] = [c]
    c["labels"] = c["labels"][:-1]
    (tmp_path / "labels.json").write_text(json.dumps({"schema_version": 1, "scenarios": [s]}))
    with pytest.raises(ValueError, match="Incomplete"):
        load_dataset(tmp_path)
    c["labels"].append(copy.deepcopy(c["labels"][0]))
    (tmp_path / "labels.json").write_text(json.dumps({"schema_version": 1, "scenarios": [s]}))
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(tmp_path)


def test_dataset_path_escape_rejected(tmp_path):
    (tmp_path / "labels.json").write_text(json.dumps({"schema_version": 1, "scenarios": [{"id": "x", "jd_path": "../escape.txt", "requirements": [], "candidates": []}]}))
    with pytest.raises(ValueError, match="out-of-dataset"):
        load_dataset(tmp_path)


def test_three_class_confusion_metrics_are_not_binary_inflated():
    rows = [
        {"expected": "matched", "predicted": "matched"},
        {"expected": "matched", "predicted": "uncertain"},
        {"expected": "not_matched", "predicted": "matched"},
        {"expected": "uncertain", "predicted": "uncertain"},
        {"expected": "not_matched", "predicted": "missing"},
    ]
    m = requirement_metrics(rows)
    assert m["correct"] == 2 and m["total"] == 5
    assert m["false_positive_matched"] == 1
    assert m["false_negative_matched"] == 1
    assert m["missing_rows"] == 1
    assert m["matched_precision"] == 0.5
    assert m["matched_recall"] == 0.5


def test_rank_metrics_allow_equal_gold_scores_as_ties():
    data = [
        {"id": "A", "gold_matched_required": 3, "gold_required_total": 4, "predicted_score": 75},
        {"id": "B", "gold_matched_required": 3, "gold_required_total": 4, "predicted_score": 75},
        {"id": "C", "gold_matched_required": 1, "gold_required_total": 4, "predicted_score": 25},
    ]
    m = rank_metrics(data, top_k=3)
    assert m["pairs"] == 3 and m["pairwise_accuracy_with_ties"] == 1
    assert m["gold_top_ids"] == ["A", "B"]
    assert m["ndcg_at_k"] == 1
    data[1]["predicted_score"] = 74
    assert rank_metrics(data, top_k=3)["pairwise_accuracy_with_ties"] == 2 / 3


def test_ranking_missing_candidate_is_not_ignored():
    data = [
        {"id": "A", "gold_matched_required": 3, "gold_required_total": 4, "predicted_score": None},
        {"id": "B", "gold_matched_required": 2, "gold_required_total": 4, "predicted_score": 50},
    ]
    metrics = rank_metrics(data, 3)
    assert metrics["failed_candidate_count"] == 1
    assert metrics["pairwise_accuracy_with_ties"] == 0


def test_comparison_rejects_mismatched_ground_truth_hash():
    sample = {"dataset_sha256": "x", "selected_scenarios": ["s"], "scenarios": [],
              "summary": {"requirement_metrics": {}}, "mode": "fallback", "build_id": "a"}
    other = copy.deepcopy(sample)
    other["dataset_sha256"] = "other"
    with pytest.raises(ValueError, match="checksum"):
        compare(sample, other)


def test_comparison_classifies_regressions_and_fixes():
    def item(expected, predicted, rid):
        return {"expected": expected, "predicted": predicted, "requirement_id": rid, "requirement_name": rid}
    def report(items):
        return {"dataset_sha256": "same", "selected_scenarios": ["s"],
                "scenarios": [{"id": "s", "candidates": [{"id": "a", "rows": items}]}],
                "summary": {"requirement_metrics": {}}, "build_id": "x", "mode": "fallback"}
    old = report([item("matched", "not_matched", "1"), item("matched", "matched", "2")])
    new = report([item("matched", "matched", "1"), item("matched", "not_matched", "2")])
    c = compare(old, new)
    assert c["corrected"] == 1 and c["regressed"] == 1


def test_live_and_fallback_filtering_and_actual_pipeline(tmp_path):
    result = evaluate(DEFAULT_DATASET, scenario_ids=["procurement"], mode="fallback")
    assert result["summary"]["labelled_decisions"] == 25
    assert result["summary"]["scenarios"] == 1
    assert result["summary"]["pipeline_failures"] == 0
    assert result["summary"]["candidate_failures"] == 0
    assert result["summary"]["jd_extraction"]["gold"] == 5
    assert result["summary"]["ranking"]["pair_count"] == 10
    with pytest.raises(ValueError, match="Unknown"):
        evaluate(DEFAULT_DATASET, scenario_ids=["alien-role"], mode="fallback")
    with pytest.raises(ValueError, match="mode"):
        evaluate(DEFAULT_DATASET, mode="unapproved")

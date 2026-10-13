"""Compare labelled assessment-only and full-pipeline benchmark JSON results.

This is an offline diagnostic. It never changes scores or runs an LLM.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


DEFAULT_ASSESSMENT = Path(__file__).resolve().parents[1] / "outputs" / "benchmark_assessment.json"
DEFAULT_PIPELINE = Path(__file__).resolve().parents[1] / "outputs" / "benchmark_pipeline.json"


def load_report(path: Path, expected_scope: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("scope") != expected_scope:
        raise ValueError(f"{path.name}: expected {expected_scope!r} scope, got {payload.get('scope')!r}")
    if not isinstance(payload.get("rows"), list) or not payload["rows"]:
        raise ValueError(f"{path.name}: missing/empty rows")
    return payload


def compare(assessment: dict, pipeline: dict) -> dict:
    """Compare identical labelled decisions by (scenario_id, requirement_id)."""
    compatibility = []
    for field in ("model", "build_id", "assessment_protocol", "benchmark_data_sha256"):
        left, right = assessment.get(field), pipeline.get(field)
        if left is None or right is None:
            compatibility.append(f"{field}: missing provenance field in at least one report")
        elif left != right:
            compatibility.append(f"{field}: mismatch ({left!r} vs {right!r})")

    def index(data: dict) -> dict[tuple[str, str], dict]:
        indexed: dict[tuple[str, str], dict] = {}
        for row in data["rows"]:
            key = (row["scenario_id"], row["requirement_id"])
            if key in indexed:
                raise ValueError(f"Duplicate benchmark decision: {key}")
            indexed[key] = row
        return indexed

    a_rows, p_rows = index(assessment), index(pipeline)
    if set(a_rows) != set(p_rows):
        missing_a = sorted(set(p_rows) - set(a_rows))
        missing_p = sorted(set(a_rows) - set(p_rows))
        compatibility.append(f"Labelled row sets differ: absent in assessment={missing_a}; absent in pipeline={missing_p}")
    categories = Counter()
    differences = []
    for key in sorted(set(a_rows) & set(p_rows)):
        a, p = a_rows[key], p_rows[key]
        if a["expected"] != p["expected"] or a["requirement_name"] != p["requirement_name"]:
            compatibility.append(f"Label differs for {key}")
        if p["predicted"] == "missing_requirement":
            category = "jd_requirement_lost_or_renamed"
        elif p["predicted"] == "missing_assessment":
            category = "pipeline_assessment_missing"
        elif a["correct"] and p["correct"]:
            category = "both_correct"
        elif a["correct"] and not p["correct"]:
            category = "assessment_correct_pipeline_wrong"
        elif not a["correct"] and p["correct"]:
            category = "assessment_wrong_pipeline_correct"
        else:
            category = "both_wrong"
        categories[category] += 1
        if category != "both_correct":
            differences.append({
                "scenario_id": key[0], "requirement_id": key[1],
                "requirement_name": a["requirement_name"], "expected": a["expected"],
                "assessment_prediction": a["predicted"], "pipeline_prediction": p["predicted"],
                "assessment_raw_status": a.get("raw_final_status"),
                "pipeline_raw_status": p.get("raw_final_status"),
                "assessment_decision_path": a.get("decision_path"),
                "pipeline_decision_path": p.get("decision_path"),
                "category": category,
                "assessment_mode": a["evaluation_mode"], "pipeline_mode": p["evaluation_mode"],
            })

    a_quality = assessment.get("measurement_quality", {})
    p_quality = pipeline.get("measurement_quality", {})
    clean = (a_quality.get("valid_live_llm_measurement") is True
             and p_quality.get("valid_live_llm_measurement") is True)
    return {
        "comparable": not compatibility,
        "clean_live_llm_measurements": clean,
        "compatibility_issues": compatibility,
        "assessment_accuracy": assessment.get("metrics", {}).get("accuracy"),
        "pipeline_accuracy": pipeline.get("metrics", {}).get("accuracy"),
        "raw_diagnostics": {
            "assessment": assessment.get("raw_model_diagnostics"),
            "pipeline": pipeline.get("raw_model_diagnostics"),
        },
        "counts": dict(sorted(categories.items())),
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the two completed CV Ranker benchmark runs")
    parser.add_argument("--assessment", type=Path, default=DEFAULT_ASSESSMENT)
    parser.add_argument("--pipeline", type=Path, default=DEFAULT_PIPELINE)
    parser.add_argument("--output", type=Path, default=Path("outputs/benchmark_comparison.json"))
    args = parser.parse_args()
    try:
        result = compare(load_report(args.assessment, "assessment"), load_report(args.pipeline, "pipeline"))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"COMPARE FAILED: {exc}", file=sys.stderr)
        return 2

    print("CV RANKER BENCHMARK COMPARISON")
    print("-" * 75)
    for label, key in (("Assessment", "assessment_accuracy"), ("Full pipeline", "pipeline_accuracy")):
        value = result[key]
        print(f"{label} accuracy: {value * 100:.2f}%" if isinstance(value, (float, int)) else f"{label} accuracy: unavailable")
    print(f"Same model, build, dataset and labels: {'YES' if result['comparable'] else 'NO'}")
    print(f"Both runs exclusively used LLM assessment: {'YES' if result['clean_live_llm_measurements'] else 'NO'}")
    for issue in result["compatibility_issues"]:
        print(f"PROVENANCE WARNING: {issue}")
    for scope, diagnostics in result["raw_diagnostics"].items():
        if diagnostics:
            print(f"{scope.capitalize()} raw Qwen coverage: "
                  f"{diagnostics['raw_model_status_coverage']}/{diagnostics['total_rows']}; "
                  f"post-model status changes: {diagnostics['post_model_status_changes']}")
    for category, n in result["counts"].items():
        print(f"{category}: {n}")
    for row in result["differences"]:
        print(f"[{row['category']}] {row['scenario_id']}/{row['requirement_id']} {row['requirement_name']}: "
              f"expected={row['expected']}, assessment={row['assessment_prediction']}, pipeline={row['pipeline_prediction']}")
    print("Interpretation: discrepancies indicate where to investigate, not proof of a specific root cause. No claim of general accuracy.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved comparison: {args.output}")
    if not result["comparable"] or not result["clean_live_llm_measurements"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

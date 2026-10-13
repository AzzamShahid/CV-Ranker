"""Compare evaluation-only batch-size runs, with strict identity/provenance gates.

This never changes a production ranking result or guesses why Qwen differed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare_batch_results(baseline: dict, probe: dict) -> dict:
    required = ("build_id", "assessment_protocol", "benchmark_data_sha256", "scope", "model")
    mismatches = [name for name in required if baseline.get(name) != probe.get(name)]
    if mismatches:
        raise ValueError(f"Cannot compare different runs: {', '.join(mismatches)} differ")
    if baseline.get("assessment_batch_size") == probe.get("assessment_batch_size"):
        raise ValueError("Two different assessment_batch_size values are required")
    def keyed(payload):
        rows = payload.get("rows", [])
        out = {}
        for row in rows:
            key = (row["scenario_id"], row["requirement_id"])
            if key in out:
                raise ValueError(f"Duplicate benchmark ID: {key}")
            out[key] = row
        return out

    before, after = keyed(baseline), keyed(probe)
    if set(before) != set(after) or not before:
        raise ValueError("Benchmark identity sets are empty or different")
    changes = []
    for key in sorted(before):
        a, b = before[key], after[key]
        if a["expected"] != b["expected"] or a["requirement_name"] != b["requirement_name"]:
            raise ValueError(f"Benchmark labels changed for {key}")
        if a["predicted"] != b["predicted"]:
            changes.append({
                "scenario_id": key[0], "requirement_id": key[1],
                "name": a["requirement_name"], "expected": a["expected"],
                "baseline_status": a["predicted"], "probe_status": b["predicted"],
                "baseline_correct": a["correct"], "probe_correct": b["correct"],
            })
    return {
        "scope": baseline["scope"],
        "model": baseline["model"],
        "build_id": baseline["build_id"],
        "baseline_batch_size": baseline["assessment_batch_size"],
        "probe_batch_size": probe["assessment_batch_size"],
        "baseline_accuracy": baseline["metrics"]["accuracy"],
        "probe_accuracy": probe["metrics"]["accuracy"],
        "baseline_live_llm_valid": baseline["measurement_quality"]["valid_live_llm_measurement"],
        "probe_live_llm_valid": probe["measurement_quality"]["valid_live_llm_measurement"],
        "different_statuses": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare batch sizes on identical benchmark data")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    args = parser.parse_args()
    try:
        a = json.loads(args.baseline.read_text(encoding="utf-8"))
        b = json.loads(args.probe.read_text(encoding="utf-8"))
        report = compare_batch_results(a, b)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Comparison invalid: {exc}")
        return 2
    print(f"Batch-size comparison ({report['scope']}, {report['model']}, {report['build_id']})")
    print(f"Batch {report['baseline_batch_size']}: {report['baseline_accuracy']:.2%}")
    print(f"Batch {report['probe_batch_size']}: {report['probe_accuracy']:.2%}")
    print("Qwen-only clean measurement:", "YES" if report["baseline_live_llm_valid"] and report["probe_live_llm_valid"] else "NO")
    print("Status differences:", len(report["different_statuses"]))
    for changed in report["different_statuses"]:
        print(f"  {changed['scenario_id']}/{changed['requirement_id']} ({changed['name']}): "
              f"{changed['baseline_status']} -> {changed['probe_status']} (expected {changed['expected']})")
    print("This isolates batching effects within one build; a single pair of runs is not proof of reliable model improvement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

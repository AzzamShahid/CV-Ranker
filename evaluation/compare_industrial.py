"""Compare two Phase 7E outputs only when they use identical frozen fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _rows(report: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    output = {}
    for scenario in report["scenarios"]:
        for candidate in scenario["candidates"]:
            for row in candidate["rows"]:
                key = (scenario["id"], candidate["id"], row["requirement_id"])
                if key in output:
                    raise ValueError(f"Duplicate row in comparison report: {key}")
                output[key] = row
    return output


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if baseline.get("dataset_sha256") != current.get("dataset_sha256") or not baseline.get("dataset_sha256"):
        raise ValueError("Dataset checksum mismatch: cannot compare different ground truth")
    if baseline.get("selected_scenarios") != current.get("selected_scenarios"):
        raise ValueError("Selected scenarios or their order differ")
    older, newer = _rows(baseline), _rows(current)
    if older.keys() != newer.keys():
        raise ValueError("Incomplete or mismatched labelled row coverage")
    changes = []
    corrected, regressions, switched = 0, 0, 0
    for key in sorted(older):
        before, after = older[key], newer[key]
        if before["expected"] != after["expected"] or before["requirement_name"] != after["requirement_name"]:
            raise ValueError(f"Ground truth differs for {key}")
        if before["predicted"] == after["predicted"]:
            continue
        previous_ok = before["predicted"] == before["expected"]
        current_ok = after["predicted"] == after["expected"]
        classification = "corrected" if current_ok and not previous_ok else "regression" if previous_ok and not current_ok else "changed_but_still_wrong"
        corrected += classification == "corrected"
        regressions += classification == "regression"
        switched += classification == "changed_but_still_wrong"
        changes.append({"scenario": key[0], "candidate": key[1], "requirement_id": key[2],
                        "requirement": before["requirement_name"], "expected": before["expected"],
                        "old": before["predicted"], "new": after["predicted"], "classification": classification})
    return {
        "dataset_sha256": baseline["dataset_sha256"],
        "baseline": {"build": baseline["build_id"], "mode": baseline["mode"], "summary": baseline["summary"]["requirement_metrics"]},
        "current": {"build": current["build_id"], "mode": current["mode"], "summary": current["summary"]["requirement_metrics"]},
        "corrected": corrected, "regressed": regressions, "changed_but_still_wrong": switched,
        "unchanged": len(older) - len(changes), "decision_changes": changes,
        "comparison_note": "If modes differ, changes reflect combined model+validators versus fallback, not isolated Qwen quality.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Compare Phase 7E results with identical labelled source fixtures")
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--current", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("outputs/phase7e_comparison.json"))
    a = p.parse_args(argv)
    try:
        baseline = json.loads(a.baseline.read_text(encoding="utf-8"))
        current = json.loads(a.current.read_text(encoding="utf-8"))
        comparison = compare(baseline, current)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        p.exit(2, f"Invalid comparison: {e}\n")
    print("PHASE 7E BENCHMARK COMPARISON")
    print(f"Corrected={comparison['corrected']} Regressed={comparison['regressed']} Still_wrong_changes={comparison['changed_but_still_wrong']}")
    print(f"Saved: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

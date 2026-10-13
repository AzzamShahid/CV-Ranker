"""Evaluation-only repeated, paired Qwen batch-size comparison.

No benchmark fixtures or production ranking modules are changed by this tool.
A single 21-row pass cannot prove a robust batch-size effect. This runner
collects independent outputs and reports accuracy, instability, false-positive
counts, and the individual requirements whose statuses flip.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Sequence

REQUIRED_IDENTITY = ("build_id", "assessment_protocol", "benchmark_data_sha256", "scope", "model")
STATUS_SET = {"matched", "not_matched", "uncertain"}


def _index_rows(payload: dict) -> dict[tuple[str, str], dict]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Benchmark file has no rows")
    result = {}
    for row in rows:
        key = (row["scenario_id"], row["requirement_id"])
        if key in result:
            raise ValueError(f"Duplicate benchmark row: {key}")
        if row["predicted"] not in STATUS_SET:
            raise ValueError(f"Incomplete benchmark decision for {key}: {row['predicted']}")
        result[key] = row
    return result


def summarize_runs(items: Sequence[tuple[int, int, dict]]) -> dict:
    """Summarize (trial, batch_size, evaluation_json) tuples without running Ollama."""
    if not items:
        raise ValueError("No results to summarize")
    expected_keys = None
    identity = None
    indexed = {}
    labels = {}
    for trial, batch_size, result in items:
        if (trial, batch_size) in indexed:
            raise ValueError(f"Duplicate trial/batch pair: {trial}/{batch_size}")
        if result.get("assessment_batch_size") != batch_size:
            raise ValueError(f"Batch-size mismatch for trial {trial}: {batch_size}")
        marker = tuple(result.get(prop) for prop in REQUIRED_IDENTITY)
        if None in marker:
            raise ValueError("Missing build, protocol, dataset, scope, or model identity")
        if identity is None:
            identity = marker
        elif marker != identity:
            raise ValueError("Different build/model/dataset/scope/protocol in repeated runs")
        rows = _index_rows(result)
        if expected_keys is None:
            expected_keys = set(rows)
            labels = {k: (r["expected"], r["requirement_name"], r["category"]) for k, r in rows.items()}
        if set(rows) != expected_keys:
            raise ValueError("The benchmark requirement set changed between runs")
        for key, row in rows.items():
            if (row["expected"], row["requirement_name"], row["category"]) != labels[key]:
                raise ValueError(f"Requirement name/label/category changed for {key}")
        indexed[(trial, batch_size)] = (result, rows)

    batch_sizes = sorted({b for _, b in indexed})
    trials_by_batch = {b: sorted(t for t, size in indexed if size == b) for b in batch_sizes}
    per_batch = {}
    all_unstable = []
    for size in batch_sizes:
        trials = trials_by_batch[size]
        runs = [(t, *indexed[(t, size)]) for t in trials]
        accuracies = [p["metrics"]["accuracy"] for _, p, _ in runs]
        measured = []
        clean_count = 0
        for t, payload, rows in runs:
            observed_accuracy = sum(row["predicted"] == row["expected"] for row in rows.values()) / len(rows)
            if abs(observed_accuracy - payload["metrics"]["accuracy"]) > 1e-9:
                raise ValueError(f"Reported accuracy inconsistent with rows in trial {t}, batch {size}")
            fp = sum(row["expected"] != "matched" and row["predicted"] == "matched" for row in rows.values())
            fn = sum(row["expected"] == "matched" and row["predicted"] != "matched" for row in rows.values())
            clean = bool(payload["measurement_quality"]["valid_live_llm_measurement"])
            clean_count += int(clean)
            measured.append({
                "trial": t, "accuracy": observed_accuracy, "false_positive_matches": fp,
                "missed_expected_matches": fn, "clean_full_llm_path": clean,
                "raw_qwen_agreement": payload.get("raw_model_diagnostics", {}).get("raw_status_accuracy_on_observed"),
            })
        per_row = []
        for key in sorted(expected_keys):
            statuses = Counter(rows[key]["predicted"] for _, _, rows in runs)
            wrong_count = sum(rows[key]["predicted"] != rows[key]["expected"] for _, _, rows in runs)
            record = {
                "scenario_id": key[0], "requirement_id": key[1],
                "name": labels[key][1], "category": labels[key][2], "expected": labels[key][0],
                "statuses": dict(sorted(statuses.items())), "incorrect_trials": wrong_count,
                "trial_count": len(runs), "unstable": len(statuses) > 1,
            }
            if record["unstable"]:
                all_unstable.append({"batch_size": size, **record})
            per_row.append(record)
        per_batch[str(size)] = {
            "trials": trials, "run_count": len(runs),
            "mean_accuracy": statistics.mean(accuracies),
            "min_accuracy": min(accuracies), "max_accuracy": max(accuracies),
            "accuracy_population_stdev": statistics.pstdev(accuracies),
            "clean_llm_path_runs": clean_count,
            "run_details": measured,
            "unstable_requirement_count": sum(r["unstable"] for r in per_row),
            "requirements": per_row,
        }
    paired = []
    if len(batch_sizes) == 2:
        a, b = batch_sizes
        for trial in sorted(set(trials_by_batch[a]) & set(trials_by_batch[b])):
            acc_a = indexed[(trial, a)][0]["metrics"]["accuracy"]
            acc_b = indexed[(trial, b)][0]["metrics"]["accuracy"]
            paired.append({"trial": trial, f"batch_{a}": acc_a, f"batch_{b}": acc_b, "difference_larger_minus_smaller": acc_b - acc_a})
    return {
        "identity": dict(zip(REQUIRED_IDENTITY, identity)),
        "requirement_count": len(expected_keys),
        "batch_sizes": batch_sizes,
        "per_batch": per_batch,
        "paired_trials": paired,
        "unstable_requirements": all_unstable,
        "interpretation": "Repeated decisions on a small synthetic dataset are diagnostic, not unbiased population accuracy. Mixed/fallback runs cannot be called clean Qwen accuracy. No production batch selection is made.",
    }


def _load_existing_files(output_dir: Path) -> list[tuple[int, int, dict]]:
    imports = []
    for item in sorted(output_dir.glob("trial_*_batch_*.json")):
        try:
            stem = item.stem.split("_")
            trial, size = int(stem[1]), int(stem[3])
        except (ValueError, IndexError):
            raise ValueError(f"Unexpected run filename {item.name}") from None
        imports.append((trial, size, json.loads(item.read_text(encoding="utf-8"))))
    return imports


def _print_summary(summary: dict) -> None:
    print("\nREPEATED BATCH-SIZE DIAGNOSTICS")
    print("=" * 65)
    print("Model:", summary["identity"]["model"], "| build:", summary["identity"]["build_id"])
    print("Labelled requirements:", summary["requirement_count"])
    for size, data in sorted(summary["per_batch"].items(), key=lambda x: int(x[0])):
        print(f"Batch {size}: {data['run_count']} run(s); mean={data['mean_accuracy']:.2%}; "
              f"range={data['min_accuracy']:.2%}..{data['max_accuracy']:.2%}; "
              f"unstable rows={data['unstable_requirement_count']}; "
              f"clean runs={data['clean_llm_path_runs']}/{data['run_count']}")
        for trial in data["run_details"]:
            print(f"  Trial {trial['trial']}: correct={trial['accuracy']:.2%} "
                  f"false-positive matches={trial['false_positive_matches']} "
                  f"missed matches={trial['missed_expected_matches']}")
    for diff in summary["paired_trials"]:
        print(f"Paired trial {diff['trial']}: larger-minus-smaller batch accuracy difference "
              f"{diff['difference_larger_minus_smaller']:+.2%}")
    print("Decision-flipping requirements:", len(summary["unstable_requirements"]))
    for row in summary["unstable_requirements"]:
        print(f"  Batch {row['batch_size']} {row['scenario_id']}/{row['requirement_id']} "
              f"{row['name']}: {row['statuses']} expected={row['expected']}")
    print("WARNING: These outputs are diagnostic; do not describe mixed runs as pure Qwen accuracy.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeated evaluation-only batch-size probe")
    parser.add_argument("--repeats", type=int, default=3, help="Paired runs per batch size (default 3)")
    parser.add_argument("--batch-sizes", type=int, nargs=2, default=[20, 3])
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--scope", choices=("assessment", "pipeline"), default="assessment")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/repeatability_probe"))
    parser.add_argument("--analyze-only", action="store_true", help="Analyze existing trial JSON without Qwen calls")
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 20 or min(args.batch_sizes) < 1 or len(set(args.batch_sizes)) != 2:
        parser.error("Use 1..20 repeats and two distinct positive batch sizes")
    if not args.analyze_only:
        from cv_ranker.runtime_check import assert_runtime_current
        assert_runtime_current()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for trial in range(1, args.repeats + 1):
            # Alternate the order to reduce (not remove) systematic warmup/order effects.
            order = args.batch_sizes if trial % 2 else list(reversed(args.batch_sizes))
            for size in order:
                output = args.output_dir / f"trial_{trial:02d}_batch_{size}.json"
                if output.exists():
                    print(f"Existing result would be overwritten: {output}. Use another --output-dir.", file=sys.stderr)
                    return 2
                command = [sys.executable, "-m", "evaluation.evaluate_benchmark",
                           "--scope", args.scope, "--model", args.model,
                           "--batch-size", str(size), "--output", str(output)]
                print(f"\nTRIAL {trial}/{args.repeats} — batch {size}", flush=True)
                # Do not hide diagnostics: keep console output and capture reproducibility logs.
                with (args.output_dir / f"trial_{trial:02d}_batch_{size}.log").open("w", encoding="utf-8") as logfile:
                    proc = subprocess.run(command, stdout=logfile, stderr=subprocess.STDOUT, check=False)
                if proc.returncode not in (0, 3) or not output.exists():
                    print(f"Benchmark failed for trial {trial}, batch {size}. See .log in {args.output_dir}", file=sys.stderr)
                    return 2
                result = json.loads(output.read_text(encoding="utf-8"))
                print(f"Completed: accuracy={result['metrics']['accuracy']:.2%}; "
                      f"clean_llm_path={result['measurement_quality']['valid_live_llm_measurement']}", flush=True)
    try:
        items = _load_existing_files(args.output_dir)
        summary = summarize_runs(items)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"Repeatability report invalid: {exc}", file=sys.stderr)
        return 2
    target = args.output_dir / "repeatability_summary.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_summary(summary)
    print(f"Saved summary: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

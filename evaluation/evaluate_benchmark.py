"""Run the labelled CV Ranker benchmark.

The benchmark data is evaluation-only. Production ranking code never imports it.
Use --scope assessment to isolate the CV semantic-assessment contract, or
--scope pipeline to exercise JD extraction + CV assessment + deterministic score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from cv_ranker.assessor import assess_resume
from cv_ranker.config import Settings
from cv_ranker.llm import LLMError, StructuredLLM
from cv_ranker.pipeline import CVRanker
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.text_utils import canonical_equivalence_key, canonical_key
from evaluation.trace import RecordingLLM


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "evaluation" / "benchmark_cases.json"
STATUSES = ("matched", "not_matched", "uncertain")


@dataclass
class RowResult:
    scenario_id: str
    requirement_id: str
    requirement_name: str
    category: str
    expected: str
    predicted: str
    evaluation_mode: str
    evidence_ids: list[str]
    evidence: str | None
    matched_term: str | None
    correct: bool
    note: str = ""
    raw_initial_status: str | None = None
    raw_final_status: str | None = None
    raw_evidence_ids: list[str] = field(default_factory=list)
    raw_matched_term: str | None = None
    llm_attempts: int = 0
    decision_path: str = "unobserved"
    model_attempt_history: list[dict] = field(default_factory=list)
    # Source-JD identity tracking; never inferred from the CV assessment result.
    jd_source_resolution: str | None = None


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Benchmark must contain a non-empty scenarios list")
    scenario_ids: set[str] = set()
    for scenario in scenarios:
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id.strip() or scenario_id in scenario_ids:
            raise ValueError(f"Missing/duplicate benchmark scenario ID: {scenario_id!r}")
        scenario_ids.add(scenario_id)
        if not isinstance(scenario.get("resume_text"), str) or not scenario["resume_text"].strip():
            raise ValueError(f"Empty resume in scenario {scenario_id}")
        requirements = scenario.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError(f"No labelled requirements in scenario {scenario_id}")
        req_ids: set[str] = set()
        for req in requirements:
            req_id = req.get("id")
            if not isinstance(req_id, str) or not req_id.strip() or req_id in req_ids:
                raise ValueError(f"Missing/duplicate requirement ID in {scenario_id}: {req_id!r}")
            req_ids.add(req_id)
            if not isinstance(req.get("name"), str) or not req["name"].strip():
                raise ValueError(f"Empty requirement name in {scenario_id}/{req_id}")
            if req.get("expected_status") not in STATUSES:
                raise ValueError(f"Invalid expected_status in {scenario_id}/{req_id}")
            if req.get("priority") not in {"required", "preferred", "unknown"}:
                raise ValueError(f"Invalid priority in {scenario_id}/{req_id}")
    return data


def _requirements(scenario: dict) -> list[ValidatedRequirement]:
    return [
        ValidatedRequirement(
            requirement_id=item["id"],
            name=item["name"],
            priority=item["priority"],
            jd_evidence=item["name"],
        )
        for item in scenario["requirements"]
    ]



def _attach_raw_observation(row: RowResult, observation: dict | None) -> RowResult:
    """Attach model-only status to a benchmark row without influencing ranking."""
    if not observation:
        row.decision_path = "no_structured_llm_row"
        return row
    row.raw_initial_status = observation["first_status"]
    row.raw_final_status = observation["last_status"]
    row.raw_evidence_ids = list(observation["last_evidence_ids"])
    row.raw_matched_term = observation["last_matched_term"]
    row.llm_attempts = observation["attempts"]
    row.model_attempt_history = [dict(attempt) for attempt in observation.get("attempt_history", [])]
    if row.predicted not in STATUSES:
        row.decision_path = "incomplete_pipeline"
    elif row.raw_final_status != row.predicted:
        row.decision_path = "python_or_fallback_changed_status"
    elif observation.get("focused_abbreviation"):
        row.decision_path = "llm_focused_abbreviation_agreed_with_final"
    elif observation.get("second_look"):
        row.decision_path = "llm_second_look_agreed_with_final"
    elif observation["retried"]:
        row.decision_path = "llm_correction_agreed_with_final"
    else:
        row.decision_path = "llm_initial_agreed_with_final"
    return row


def _assessment_rows(scenario: dict, model: str, batch_size: int = 20, second_look: bool = True,
                     focused_abbreviation: bool = True, exact_initialism: bool = False) -> list[RowResult]:
    settings = Settings(model_name=model, max_requirements=50, assessment_batch_size=batch_size,
                        second_look_unmatched=second_look, focused_abbreviation_retry=focused_abbreviation,
                        exact_initialism_guard=exact_initialism)
    llm = RecordingLLM(StructuredLLM(settings))
    requirements = _requirements(scenario)
    assessments, mode, warnings = assess_resume(
        resume_text=scenario["resume_text"],
        requirements=requirements,
        llm=llm,
    )
    by_id = {item.requirement_id: item for item in assessments}
    observed = llm.observations()
    rows: list[RowResult] = []
    for item in scenario["requirements"]:
        assessment = by_id[item["id"]]
        rows.append(
            _attach_raw_observation(RowResult(
                scenario_id=scenario["id"],
                requirement_id=item["id"],
                requirement_name=item["name"],
                category=item["category"],
                expected=item["expected_status"],
                predicted=assessment.status,
                evaluation_mode=mode,
                evidence_ids=list(assessment.evidence_ids),
                evidence=assessment.evidence,
                matched_term=assessment.matched_term,
                correct=assessment.status == item["expected_status"],
                note=" | ".join(warnings),
            ), observed.get(item["id"]))
        )
    return rows


def _pipeline_rows(scenario: dict, model: str, batch_size: int = 20, second_look: bool = True,
                   focused_abbreviation: bool = True, exact_initialism: bool = False) -> list[RowResult]:
    required = [r for r in scenario["requirements"] if r["priority"] == "required"]
    preferred = [r for r in scenario["requirements"] if r["priority"] == "preferred"]
    lines = ["Benchmark Role", "", "Required Skills:"]
    lines.extend(f"- {r['name']}" for r in required)
    if preferred:
        lines.extend(["", "Preferred Skills:"])
        lines.extend(f"- {r['name']}" for r in preferred)
    jd_text = "\n".join(lines) + "\n"

    with TemporaryDirectory(prefix="cv_ranker_benchmark_") as tmp:
        root = Path(tmp)
        jd_path = root / "jd.txt"
        cv_path = root / "resume.txt"
        jd_path.write_text(jd_text, encoding="utf-8")
        cv_path.write_text(scenario["resume_text"], encoding="utf-8")
        ranker = CVRanker(
            Settings(model_name=model, max_requirements=50, assessment_batch_size=batch_size,
                     second_look_unmatched=second_look, focused_abbreviation_retry=focused_abbreviation,
                        exact_initialism_guard=exact_initialism),
            use_llm=True,
        )
        recorder = RecordingLLM(ranker.llm) if ranker.llm is not None else None
        if recorder is not None:
            ranker.llm = recorder
        report = ranker.run(jd_path, [cv_path])

    observed = recorder.observations() if recorder is not None else {}
    candidate = report.candidates[0]
    assessments = {a.requirement_id: a for a in candidate.assessments}
    # Map frozen requirements back to labels by exact source wording. The JD builder
    # uses benchmark requirement names verbatim, so a missing/renamed requirement is
    # counted as an end-to-end failure instead of being silently ignored.
    frozen_by_name = {r.name.casefold(): r for r in report.requirements}
    explicit_diagnostics = {
        entry["source_identity"]: entry
        for entry in report.jd_diagnostics if entry.get("stage") == "explicit_source"
    }
    model_diagnostics = [
        entry for entry in report.jd_diagnostics
        if entry.get("stage") == "jd_model_row" and entry.get("attempt") == "initial"
    ]
    rows: list[RowResult] = []
    for item in scenario["requirements"]:
        source_key = canonical_equivalence_key(item["name"]) or canonical_key(item["name"])
        source_event = explicit_diagnostics.get(source_key)
        if source_event:
            source_resolution = source_event["status"]
        else:
            proposed = [
                entry for entry in model_diagnostics
                if (canonical_equivalence_key(entry.get("proposed_name", "")) or canonical_key(entry.get("proposed_name", ""))) == source_key
            ]
            if proposed:
                source_resolution = "model_row_" + proposed[0]["status"]
            else:
                source_resolution = "not_proposed_by_model_or_structural_parser"
        frozen = frozen_by_name.get(item["name"].casefold())
        if frozen is None:
            rows.append(
                _attach_raw_observation(RowResult(
                    scenario_id=scenario["id"],
                    requirement_id=item["id"],
                    requirement_name=item["name"],
                    category=item["category"],
                    expected=item["expected_status"],
                    predicted="missing_requirement",
                    evaluation_mode=f"jd:{report.jd_validation_mode}",
                    evidence_ids=[],
                    evidence=None,
                    matched_term=None,
                    correct=False,
                    note="Frozen JD requirement was missing or renamed.",
                    jd_source_resolution=source_resolution,
                ), None)
            )
            continue
        assessment = assessments.get(frozen.requirement_id)
        if assessment is None:
            predicted = "missing_assessment"
            evidence_ids: list[str] = []
            evidence = None
            matched_term = None
        else:
            predicted = assessment.status
            evidence_ids = list(assessment.evidence_ids)
            evidence = assessment.evidence
            matched_term = assessment.matched_term
        rows.append(
            _attach_raw_observation(RowResult(
                scenario_id=scenario["id"],
                requirement_id=item["id"],
                requirement_name=item["name"],
                category=item["category"],
                expected=item["expected_status"],
                predicted=predicted,
                evaluation_mode=f"jd:{report.jd_validation_mode};cv:{candidate.evaluation_mode}",
                evidence_ids=evidence_ids,
                evidence=evidence,
                matched_term=matched_term,
                correct=predicted == item["expected_status"],
                note=" | ".join(report.warnings + candidate.errors),
                jd_source_resolution=source_resolution,
            ), observed.get(frozen.requirement_id))
        )
    return rows


def _metrics(rows: list[RowResult]) -> dict:
    total = len(rows)
    correct = sum(r.correct for r in rows)
    expected_matched = sum(r.expected == "matched" for r in rows)
    predicted_matched = sum(r.predicted == "matched" for r in rows)
    true_matched = sum(r.expected == "matched" and r.predicted == "matched" for r in rows)
    precision = true_matched / predicted_matched if predicted_matched else 0.0
    recall = true_matched / expected_matched if expected_matched else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    confusion = Counter((r.expected, r.predicted) for r in rows)
    by_category: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_category[r.category].append(r.correct)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "matched_precision": precision,
        "matched_recall": recall,
        "matched_f1": f1,
        "confusion": confusion,
        "by_category": {k: sum(v) / len(v) for k, v in sorted(by_category.items())},
    }


def _measurement_quality(rows: list[RowResult], scope: str) -> dict:
    """Flag model/fallback contamination; accuracy alone cannot prove a live LLM run."""
    clean_mode = "llm_assessed" if scope == "assessment" else "jd:llm_validated;cv:llm_assessed"
    mode_counts = Counter(r.evaluation_mode for r in rows)
    contaminated = [
        f"{r.scenario_id}/{r.requirement_id} ({r.evaluation_mode})"
        for r in rows if r.evaluation_mode != clean_mode
    ]
    incomplete = [
        f"{r.scenario_id}/{r.requirement_id} ({r.predicted})"
        for r in rows if r.predicted not in STATUSES
    ]
    # The public mode is scoped to a whole candidate/batch. A "mixed" group
    # can contain many decisions that Qwen itself made correctly. Report both
    # the strict, aggregate path and granular status provenance; neither is a
    # claim that unchanged model decisions are semantically correct.
    by_decision_path = Counter(r.decision_path for r in rows)
    changed = [f"{r.scenario_id}/{r.requirement_id}" for r in rows
               if r.decision_path == "python_or_fallback_changed_status"]
    retried = [f"{r.scenario_id}/{r.requirement_id}" for r in rows
               if r.decision_path == "llm_correction_agreed_with_final"]
    second_look = [f"{r.scenario_id}/{r.requirement_id}" for r in rows
                   if r.decision_path == "llm_second_look_agreed_with_final"]
    focused = [f"{r.scenario_id}/{r.requirement_id}" for r in rows
               if any(attempt.get("phase") == "focused_abbreviation"
                      for attempt in r.model_attempt_history)]
    unchanged = [f"{r.scenario_id}/{r.requirement_id}" for r in rows
                 if r.decision_path == "llm_initial_agreed_with_final"]
    return {
        "decision_path_counts": dict(sorted(by_decision_path.items())),
        "qwen_initial_status_unchanged_rows": unchanged,
        "llm_correction_rows": retried,
        "llm_second_look_rows": second_look,
        "llm_focused_abbreviation_rows": focused,
        "post_model_status_changed_rows": changed,
        "valid_live_llm_measurement": bool(rows) and not contaminated and not incomplete,
        "expected_mode": clean_mode,
        "mode_counts": dict(sorted(mode_counts.items())),
        "non_llm_or_mixed_rows": contaminated,
        "incomplete_rows": incomplete,
    }


def _raw_diagnostics(rows: list[RowResult]) -> dict:
    seen = [r for r in rows if r.raw_final_status in STATUSES]
    changes = [r for r in seen if r.predicted != r.raw_final_status]
    revised = [r for r in seen if r.raw_initial_status != r.raw_final_status]
    return {
        "raw_model_status_coverage": len(seen),
        "total_rows": len(rows),
        "raw_status_correct": sum(r.raw_final_status == r.expected for r in seen),
        "raw_status_accuracy_on_observed": (
            sum(r.raw_final_status == r.expected for r in seen) / len(seen)
            if seen else None
        ),
        "post_model_status_changes": len(changes),
        "model_retry_status_changes": len(revised),
        "changed_rows": [f"{r.scenario_id}/{r.requirement_id}: model={r.raw_final_status}, final={r.predicted}" for r in changes],
    }


def _print_report(rows: list[RowResult], metrics: dict, *, scope: str, model: str, batch_size: int = 20,
                  second_look: bool = True, focused_abbreviation: bool = True, exact_initialism: bool = False) -> None:
    quality = _measurement_quality(rows, scope)
    print("=" * 96)
    print("CV RANKER LABELLED BENCHMARK")
    print("=" * 96)
    print(f"Scope: {scope}")
    print(f"Model: {model}")
    print(f"Maximum requirements per CV batch: {batch_size}")
    print(f"Selective second look: {'enabled' if second_look else 'disabled'}")
    print(f"Focused abbreviation clarification: {'enabled' if focused_abbreviation and second_look else 'disabled'}")
    print(f"Optional exact-initialism recovery: {'enabled' if exact_initialism else 'disabled'}")
    print(f"Rows: {metrics['total']}")
    print(f"Requirement-level accuracy: {metrics['accuracy'] * 100:.2f}% ({metrics['correct']}/{metrics['total']})")
    print(f"Matched precision: {metrics['matched_precision'] * 100:.2f}%")
    print(f"Matched recall:    {metrics['matched_recall'] * 100:.2f}%")
    print(f"Matched F1:        {metrics['matched_f1'] * 100:.2f}%")
    print(f"Live LLM measurement valid: {'YES' if quality['valid_live_llm_measurement'] else 'NO'}")
    print(f"Modes: {quality['mode_counts']}")
    print(f"Per-requirement decision paths: {quality['decision_path_counts']}")
    raw = _raw_diagnostics(rows)
    print(f"Raw Qwen status coverage: {raw['raw_model_status_coverage']}/{raw['total_rows']}")
    print(f"Status changes after model response: {raw['post_model_status_changes']}")
    print(f"Status changes during LLM correction: {raw['model_retry_status_changes']}")
    if raw["raw_status_accuracy_on_observed"] is not None:
        print(f"Raw model status agreement (observed rows only): {100 * raw['raw_status_accuracy_on_observed']:.2f}%")
    print("NOTE: Raw statuses are pre-validation proposals; only final statuses determine the actual score.")
    if not quality["valid_live_llm_measurement"]:
        print("WARNING: At least one row used fallback/mixed mode or is missing. The accuracy above is NOT a clean Qwen-only measurement.")
        for item in (quality["non_llm_or_mixed_rows"] + quality["incomplete_rows"])[:15]:
            print(f"  - {item}")
    print()
    print("RESULTS")
    print("-" * 96)
    for row in rows:
        mark = "PASS" if row.correct else "FAIL"
        print(
            f"[{mark}] {row.scenario_id}/{row.requirement_id} | {row.requirement_name} | "
            f"expected={row.expected} predicted={row.predicted} | category={row.category} | mode={row.evaluation_mode}"
        )
        if row.raw_final_status is not None:
            print(f"       raw_model={row.raw_initial_status} -> {row.raw_final_status}; path={row.decision_path}")
        if row.matched_term:
            print(f"       matched_term={row.matched_term!r}")
        if row.evidence_ids:
            print(f"       evidence_ids={row.evidence_ids}")
        if not row.correct and row.evidence:
            print(f"       evidence={row.evidence}")
        if not row.correct and row.model_attempt_history:
            for attempt in row.model_attempt_history:
                print(f"       Qwen attempt [{attempt['phase']}]: status={attempt['status']}, "
                      f"ids={attempt['evidence_ids']}, source_term={attempt['matched_term']!r}")
        if not row.correct and row.note:
            print(f"       diagnostics={row.note}")

    print("\nCATEGORY ACCURACY")
    print("-" * 96)
    for category, value in metrics["by_category"].items():
        print(f"{category:28s} {value * 100:6.2f}%")

    print("\nCONFUSION COUNTS")
    print("-" * 96)
    predicted_labels = sorted({pred for _, pred in metrics["confusion"]})
    for expected in STATUSES:
        parts = [
            f"{pred}={metrics['confusion'].get((expected, pred), 0)}"
            for pred in predicted_labels
        ]
        print(f"expected {expected:11s}: " + ", ".join(parts))

    print("\nInterpretation: this benchmark measures only the labelled cases above. It is not a claim of 99% or general real-world accuracy.")


def _save_json(path: Path, rows: list[RowResult], metrics: dict, *, scope: str, model: str,
               data_path: Path = DEFAULT_DATA, batch_size: int = 20, second_look: bool = True,
               focused_abbreviation: bool = True, exact_initialism: bool = False,
               selected_scenarios: list[str] | None = None) -> None:
    from cv_ranker.build_info import BUILD_ID, ASSESSMENT_PROTOCOL

    payload = {
        "scope": scope,
        "model": model,
        "assessment_batch_size": batch_size,
        "second_look_unmatched": second_look,
        "focused_abbreviation_retry": focused_abbreviation,
        "exact_initialism_guard": exact_initialism,
        "selected_scenarios": selected_scenarios,
        "build_id": BUILD_ID,
        "assessment_protocol": ASSESSMENT_PROTOCOL,
        "benchmark_data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "measurement_quality": _measurement_quality(rows, scope),
        "raw_model_diagnostics": _raw_diagnostics(rows),
        "metrics": {
            "total": metrics["total"],
            "correct": metrics["correct"],
            "accuracy": metrics["accuracy"],
            "matched_precision": metrics["matched_precision"],
            "matched_recall": metrics["matched_recall"],
            "matched_f1": metrics["matched_f1"],
            "by_category": metrics["by_category"],
            "confusion": {
                f"{exp}->{pred}": count
                for (exp, pred), count in sorted(metrics["confusion"].items())
            },
        },
        "rows": [r.__dict__ for r in rows],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the labelled CV Ranker benchmark")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--scope", choices=("assessment", "pipeline"), default="assessment")
    parser.add_argument("--batch-size", type=int, default=20, help="Maximum CV requirements per Qwen call; evaluation-only, default 20")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON result path")
    parser.add_argument("--no-second-look", action="store_true", help="Disable both grouped and focused second-look calls")
    parser.add_argument("--no-focused-abbreviation", action="store_true", help="Disable only focused acronym calls; leave grouped second look enabled")
    parser.add_argument("--exact-initialism", action="store_true",
                        help="Opt in to conservative literal 3+ letter initialism recovery (not a semantic alias map)")
    parser.add_argument("--scenario", action="append", help="Run only the named scenario ID (may be repeated)")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")

    try:
        data = _load(args.data)
        rows: list[RowResult] = []
        selected = set(args.scenario or [])
        if selected:
            unknown = selected - {scenario["id"] for scenario in data["scenarios"]}
            if unknown:
                raise ValueError(f"Unknown benchmark scenario(s): {sorted(unknown)}")
        for scenario in data["scenarios"]:
            if selected and scenario["id"] not in selected:
                continue
            # Preserve the legacy five-argument evaluation call contract unless
            # the new experimental flag was explicitly requested.
            initialism_args = (True,) if args.exact_initialism else ()
            if args.scope == "assessment":
                rows.extend(_assessment_rows(scenario, args.model, args.batch_size,
                                             not args.no_second_look, not args.no_focused_abbreviation, *initialism_args))
            else:
                rows.extend(_pipeline_rows(scenario, args.model, args.batch_size,
                                           not args.no_second_look, not args.no_focused_abbreviation, *initialism_args))
    except (LLMError, RuntimeError, ValueError, OSError) as exc:
        print(f"BENCHMARK FAILED: {exc}", file=sys.stderr)
        return 2

    metrics = _metrics(rows)
    _print_report(rows, metrics, scope=args.scope, model=args.model, batch_size=args.batch_size,
                  second_look=not args.no_second_look, focused_abbreviation=not args.no_focused_abbreviation, exact_initialism=args.exact_initialism)
    if args.output:
        _save_json(args.output, rows, metrics, scope=args.scope, model=args.model, data_path=args.data,
                   batch_size=args.batch_size, second_look=not args.no_second_look,
                   focused_abbreviation=not args.no_focused_abbreviation, exact_initialism=args.exact_initialism,
                   selected_scenarios=args.scenario)
        print(f"\nSaved: {args.output}")
    if not _measurement_quality(rows, args.scope)["valid_live_llm_measurement"]:
        print("BENCHMARK INCOMPLETE: fallback/mixed execution cannot be reported as clean Qwen accuracy.", file=sys.stderr)
        return 3
    # A benchmark is a measurement, not a test requiring 100% model accuracy.
    # Exit zero for a complete, provenance-clean run even if the model makes mistakes.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

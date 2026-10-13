"""Phase 7E: independent, file-backed multi-JD evaluation of the unchanged ranker.

These hand-authored synthetic labels do not originate from CVRanker or from a
model prediction. They are NOT external expert adjudications or hiring outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cv_ranker.config import Settings
from cv_ranker.pipeline import CVRanker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evaluation" / "industrial_dataset"
STATES = ("matched", "not_matched", "uncertain")
MISSING = "missing"


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return obj


def _safe_path(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"Unsafe dataset path: {raw!r}")
    candidate = (root / raw).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        raise ValueError(f"Missing or out-of-dataset input: {raw!r}")
    if candidate.suffix.lower() not in {".txt", ".md"}:
        raise ValueError("Industrial dataset supports only explicit text fixtures")
    return candidate


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def load_dataset(root: Path) -> dict[str, Any]:
    """Fail closed on missing, duplicated, ungrounded or internally inconsistent labels."""
    root = root.resolve()
    dataset = _load_json(root / "labels.json")
    if dataset.get("schema_version") != 1 or not isinstance(dataset.get("scenarios"), list):
        raise ValueError("Unsupported dataset schema")
    if not dataset["scenarios"]:
        raise ValueError("Dataset has no scenarios")
    scenario_ids: set[str] = set()
    total_candidates = 0
    for scenario in dataset["scenarios"]:
        sid = scenario.get("id")
        if not isinstance(sid, str) or not sid or sid in scenario_ids:
            raise ValueError(f"Missing or duplicate scenario: {sid!r}")
        scenario_ids.add(sid)
        _safe_path(root, scenario.get("jd_path"))
        reqs = scenario.get("requirements")
        candidates = scenario.get("candidates")
        if not isinstance(reqs, list) or not reqs or not isinstance(candidates, list) or not candidates:
            raise ValueError(f"Missing requirements/candidates in {sid}")
        rids: set[str] = set()
        rnames: set[str] = set()
        for r in reqs:
            rid = r.get("id")
            name = r.get("name")
            if not isinstance(rid, str) or not rid or rid in rids or not isinstance(name, str) or not name.strip() or _key(name) in rnames:
                raise ValueError(f"Duplicate/invalid requirement in {sid}")
            if r.get("priority") not in ("required", "preferred") or not isinstance(r.get("category"), str) or not r["category"]:
                raise ValueError(f"Invalid requirement metadata in {sid}/{rid}")
            if _key(name) not in _key(_safe_path(root, scenario["jd_path"]).read_text(encoding="utf-8")):
                raise ValueError(f"Gold requirement not present verbatim in JD: {sid}/{name}")
            rids.add(rid)
            rnames.add(_key(name))
        cids: set[str] = set()
        for c in candidates:
            cid = c.get("id")
            if not isinstance(cid, str) or not cid or cid in cids:
                raise ValueError(f"Missing/duplicate candidate in {sid}: {cid!r}")
            cids.add(cid)
            resume_text = _safe_path(root, c.get("resume_path")).read_text(encoding="utf-8")
            labels = c.get("labels")
            if not isinstance(labels, list) or len(labels) != len(reqs):
                raise ValueError(f"Incomplete gold labels in {sid}/{cid}")
            label_ids: set[str] = set()
            for label in labels:
                lid = label.get("requirement_id")
                if lid not in rids or lid in label_ids or label.get("status") not in STATES:
                    raise ValueError(f"Invalid/duplicate status in {sid}/{cid}/{lid}")
                label_ids.add(lid)
                quote = label.get("evidence_quote")
                if quote is not None and (not isinstance(quote, str) or not quote.strip() or quote not in resume_text):
                    raise ValueError(f"Gold evidence quote absent from source: {sid}/{cid}/{lid}")
                if label["status"] in {"matched", "uncertain"} and not quote:
                    raise ValueError(f"Positive/uncertain label requires source quote: {sid}/{cid}/{lid}")
            total_candidates += 1
    dataset["candidate_count"] = total_candidates
    return dataset


def dataset_hash(root: Path, dataset: dict[str, Any]) -> str:
    """Pin the exact original labels, JD texts and resume bytes in every report."""
    names = {"labels.json"}
    for s in dataset["scenarios"]:
        names.add(s["jd_path"])
        names.update(c["resume_path"] for c in s["candidates"])
    h = hashlib.sha256()
    for name in sorted(names):
        path = _safe_path(root, name) if name != "labels.json" else root / name
        h.update(name.encode("utf-8") + b"\x00")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def _safe_div(a: float, b: float) -> float | None:
    return (a / b) if b else None


def requirement_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    confusion = {expected: {pred: 0 for pred in (*STATES, MISSING)} for expected in STATES}
    for row in rows:
        confusion[row["expected"]][row["predicted"]] += 1
    n = len(rows)
    correct = sum(r["expected"] == r["predicted"] for r in rows)
    tp = confusion["matched"]["matched"]
    fp = sum(confusion[x]["matched"] for x in ("not_matched", "uncertain"))
    fn = sum(confusion["matched"][x] for x in ("not_matched", "uncertain", MISSING))
    p = _safe_div(tp, tp + fp)
    r = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * tp, 2 * tp + fp + fn)
    return {
        "total": n, "correct": correct, "exact_status_accuracy": _safe_div(correct, n),
        "confusion": confusion,
        "matched_precision": p, "matched_recall": r, "matched_f1": f1,
        "false_positive_matched": fp, "false_negative_matched": fn,
        "false_positive_match_rate": _safe_div(fp, sum(confusion[x][p] for x in ("not_matched", "uncertain") for p in (*STATES, MISSING))),
        "false_negative_match_rate": _safe_div(fn, sum(confusion["matched"].values())),
        "uncertain_recall": _safe_div(confusion["uncertain"]["uncertain"], sum(confusion["uncertain"].values())),
        "missing_rows": sum(row["predicted"] == MISSING for row in rows),
    }


def rank_metrics(candidates: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    """Compare equal-weight required coverage only; treat true ties as ties."""
    ordered = sorted(candidates, key=lambda c: c["id"])
    agreements = pairs = strict_pairs = strict_agree = gold_ties = correct_ties = 0
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            pairs += 1
            ga = (a["gold_matched_required"], a["gold_required_total"])
            gb = (b["gold_matched_required"], b["gold_required_total"])
            gd = ga[0] * gb[1] - gb[0] * ga[1]  # exact fractions: no rounding error
            sa, sb = a["predicted_score"], b["predicted_score"]
            if sa is None or sb is None:
                continue
            pd = (sa > sb) - (sa < sb)
            gs = (gd > 0) - (gd < 0)
            agreements += pd == gs
            if gs:
                strict_pairs += 1
                strict_agree += pd == gs
            else:
                gold_ties += 1
                correct_ties += pd == 0
    gold_best = max(c["gold_matched_required"] / c["gold_required_total"] for c in ordered)
    winners_gold = {c["id"] for c in ordered if c["gold_matched_required"] / c["gold_required_total"] == gold_best}
    scored = [c for c in ordered if c["predicted_score"] is not None]
    winners_pred: set[str] = set()
    if scored:
        maximum = max(c["predicted_score"] for c in scored)
        winners_pred = {c["id"] for c in scored if c["predicted_score"] == maximum}
    k = min(top_k, len(ordered))

    def dcg(seq: list[dict[str, Any]]) -> float:
        return sum((2 ** c["gold_matched_required"] - 1) / math.log2(i + 2) for i, c in enumerate(seq[:k]))

    # Unscored candidates are ranked last; alphabetic tie handling follows the
    # existing ranker's documented deterministic presentation order. Pairwise
    # tie agreement is the tie-safe primary ordering metric.
    predicted_order = sorted(ordered, key=lambda c: (c["predicted_score"] is None, -(c["predicted_score"] or 0), c["id"]))
    ideal = sorted(ordered, key=lambda c: (-c["gold_matched_required"] / c["gold_required_total"], c["id"]))
    ideal_dcg = dcg(ideal)
    return {
        "candidate_count": len(ordered), "pairs": pairs,
        "pairwise_accuracy_with_ties": _safe_div(agreements, pairs),
        "strict_gold_pairs": sum((a["gold_matched_required"] * b["gold_required_total"] != b["gold_matched_required"] * a["gold_required_total"]) for i,a in enumerate(ordered) for b in ordered[i+1:]),
        "strict_pairwise_accuracy": _safe_div(strict_agree, strict_pairs) if strict_pairs else None,
        "gold_tie_pairs_evaluated": gold_ties, "correct_gold_tie_pairs": correct_ties,
        "gold_top_ids": sorted(winners_gold), "predicted_top_ids": sorted(winners_pred),
        "top_group_overlap": _safe_div(len(winners_gold & winners_pred), len(winners_gold | winners_pred)) if (winners_gold | winners_pred) else None,
        "ndcg_at_k": _safe_div(dcg(predicted_order), ideal_dcg), "k": k,
        "failed_candidate_count": len(ordered) - len(scored),
    }


def evaluate_scenario(root: Path, scenario: dict[str, Any], *, model: str, use_llm: bool, top_k: int, exact_initialism: bool = False) -> dict[str, Any]:
    reqs = scenario["requirements"]
    required = [r for r in reqs if r["priority"] == "required"]
    paths = [_safe_path(root, c["resume_path"]) for c in scenario["candidates"]]
    run_error = None
    report = None
    try:
        report = CVRanker(Settings(model_name=model, max_requirements=50, exact_initialism_guard=exact_initialism), use_llm=use_llm).run(_safe_path(root, scenario["jd_path"]), paths)
    except Exception as exc:
        run_error = f"{type(exc).__name__}: {exc}"

    frozen_by_name: dict[str, Any] = {}
    extra_requirements: list[str] = []
    duplicate_requirement_names: list[str] = []
    gold_names = {_key(r["name"]) for r in reqs}
    if report is not None:
        for r in report.requirements:
            k = _key(r.name)
            if k in frozen_by_name:
                duplicate_requirement_names.append(r.name)
            frozen_by_name[k] = r
            if k not in gold_names:
                extra_requirements.append(r.name)

    candidate_by_path = {Path(c.candidate_source).resolve(): c for c in report.candidates} if report else {}
    cand_results = []
    decision_rows = []
    for c in scenario["candidates"]:
        cand = candidate_by_path.get(_safe_path(root, c["resume_path"]).resolve())
        labels = {x["requirement_id"]: x for x in c["labels"]}
        assessments = {a.requirement_id: a for a in cand.assessments} if cand else {}
        gold_n = sum(labels[r["id"]]["status"] == "matched" for r in required)
        row_bundle = []
        for req in reqs:
            frozen = frozen_by_name.get(_key(req["name"]))
            assessment = assessments.get(frozen.requirement_id) if frozen else None
            actual = assessment.status if assessment else MISSING
            reference = labels[req["id"]]
            row = {
                "scenario": scenario["id"], "department": scenario["department"],
                "candidate": c["id"], "requirement_id": req["id"],
                "requirement_name": req["name"], "priority": req["priority"],
                "category": req["category"], "expected": reference["status"],
                "predicted": actual, "correct": actual == reference["status"],
                "ground_truth_quote": reference["evidence_quote"],
                "prediction_evidence_ids": list(assessment.evidence_ids) if assessment else [],
                "prediction_evidence": assessment.evidence if assessment else None,
                "frozen_requirement_found": frozen is not None,
                "jd_priority_correct": frozen.priority == req["priority"] if frozen else False,
            }
            row_bundle.append(row)
            decision_rows.append(row)
        cand_results.append({
            "id": c["id"], "file": c["resume_path"],
            "evaluation_mode": cand.evaluation_mode if cand else "failed",
            "predicted_score": cand.primary_score if cand else None,
            "predicted_rank": cand.rank if cand else None,
            "gold_matched_required": gold_n,
            "gold_required_total": len(required),
            "gold_primary_score": round(100.0 * gold_n / len(required), 2) if required else None,
            "eligibility_status": cand.eligibility.status if cand else "evaluation_failed",
            "errors": list(cand.errors) if cand else [run_error or "Candidate result missing"],
            "rows": row_bundle,
        })

    gold_count = len(reqs)
    retrieved_count = len(report.requirements) if report else 0
    matched_names = sum(_key(r["name"]) in frozen_by_name for r in reqs)
    correct_priorities = sum(_key(r["name"]) in frozen_by_name and frozen_by_name[_key(r["name"])].priority == r["priority"] for r in reqs)
    return {
        "id": scenario["id"], "department": scenario["department"],
        "run_error": run_error, "jd_mode": report.jd_validation_mode if report else "failed",
        "jd_metrics": {"gold": gold_count, "retrieved": retrieved_count, "matched": matched_names,
                       "precision": _safe_div(matched_names, retrieved_count), "recall": _safe_div(matched_names, gold_count),
                       "priority_correct": correct_priorities, "priority_accuracy": _safe_div(correct_priorities, gold_count),
                       "extra_requirements": extra_requirements, "duplicate_names": duplicate_requirement_names,
                       "missing_requirements": [r["name"] for r in reqs if _key(r["name"]) not in frozen_by_name]},
        "row_metrics": requirement_metrics(decision_rows),
        "rank_metrics": rank_metrics(cand_results, top_k),
        "candidates": cand_results,
        "warnings": list(report.warnings) if report else [],
    }


def evaluate(root: Path, *, scenario_ids: list[str] | None = None, model: str = "qwen2.5:3b", mode: str = "fallback", top_k: int = 3, exact_initialism: bool = False) -> dict[str, Any]:
    if mode not in {"fallback", "live"}:
        raise ValueError("mode must be fallback or live")
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be >= 1")
    dataset = load_dataset(root)
    known = {s["id"] for s in dataset["scenarios"]}
    if scenario_ids and not set(scenario_ids).issubset(known):
        raise ValueError(f"Unknown scenario IDs: {sorted(set(scenario_ids) - known)}")
    selected = [s for s in dataset["scenarios"] if not scenario_ids or s["id"] in scenario_ids]
    records = [evaluate_scenario(root, s, model=model, use_llm=(mode == "live"), top_k=top_k, exact_initialism=exact_initialism) for s in selected]
    rows = [r for s in records for c in s["candidates"] for r in c["rows"]]
    group_by_category: dict[str, list] = defaultdict(list)
    group_by_dept: dict[str, list] = defaultdict(list)
    for row in rows:
        group_by_category[row["category"]].append(row)
        group_by_dept[row["department"]].append(row)
    modes = Counter(c["evaluation_mode"] for s in records for c in s["candidates"])
    jd_totals = {field: sum(s["jd_metrics"][field] for s in records) for field in ("gold", "retrieved", "matched", "priority_correct")}
    macro_pairwise = [s["rank_metrics"]["pairwise_accuracy_with_ties"] for s in records]
    macro_ndcg = [s["rank_metrics"]["ndcg_at_k"] for s in records if s["rank_metrics"]["ndcg_at_k"] is not None]
    return {
        "schema_version": 1, "run_utc": datetime.now(timezone.utc).isoformat(),
        "build_id": __import__("cv_ranker.build_info", fromlist=["BUILD_ID"]).BUILD_ID,
        "dataset_id": dataset["dataset_id"], "dataset_sha256": dataset_hash(root, dataset),
        "label_origin": dataset.get("label_origin"), "mode": mode, "model": model if mode == "live" else None,
        "exact_initialism_guard": exact_initialism,
        "selected_scenarios": [s["id"] for s in selected],
        "measurement_note": "Mixed Qwen/Python outcome, not standalone Qwen accuracy" if mode == "live" else "Deterministic no-LLM fallback and validators; not Qwen accuracy",
        "summary": {
            "scenarios": len(records), "candidates": sum(len(s["candidates"]) for s in records), "labelled_decisions": len(rows),
            "requirement_metrics": requirement_metrics(rows),
            "by_category": {name: requirement_metrics(data) for name, data in sorted(group_by_category.items())},
            "by_department": {name: requirement_metrics(data) for name, data in sorted(group_by_dept.items())},
            "jd_extraction": {**jd_totals, "precision": _safe_div(jd_totals["matched"], jd_totals["retrieved"]), "recall": _safe_div(jd_totals["matched"], jd_totals["gold"]),
                              "priority_accuracy": _safe_div(jd_totals["priority_correct"], jd_totals["gold"])},
            "ranking": {
                "macro_pairwise_accuracy_with_ties": _safe_div(sum(macro_pairwise), len(macro_pairwise)),
                "macro_ndcg_at_k": _safe_div(sum(macro_ndcg), len(macro_ndcg)), "top_k": top_k,
                "top_group_overlap_macro": _safe_div(sum(s["rank_metrics"]["top_group_overlap"] or 0 for s in records), len(records)),
                "pair_count": sum(s["rank_metrics"]["pairs"] for s in records),
            },
            "evaluation_modes": dict(sorted(modes.items())),
            "pipeline_failures": sum(s["run_error"] is not None for s in records),
            "candidate_failures": sum(c["predicted_score"] is None for s in records for c in s["candidates"]),
        }, "scenarios": records,
    }


def _fmt(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "N/A"


def write_markdown(report: dict[str, Any], output: Path) -> None:
    info = report["summary"]
    m = info["requirement_metrics"]
    jd = info["jd_extraction"]
    rank = info["ranking"]
    lines = [
        "# Phase 7E — Independent Synthetic Benchmark Report", "",
        f"- Build: `{report['build_id']}`", f"- Mode: `{report['mode']}`", f"- Dataset: `{report['dataset_id']}`",
        f"- Dataset SHA-256: `{report['dataset_sha256']}`", f"- Exact initialism recovery: `{report.get('exact_initialism_guard', False)}`", "",
        "**Scope warning:** Hand-authored synthetic labels are not external HR adjudications, real hiring outcomes, or production accuracy. "
        "The fallback run contains no Qwen inference. The live run represents the combined Qwen/Python system, not pure Qwen accuracy.", "",
        "## Aggregate", "",
        f"- Scenarios / candidates / labelled decisions: **{info['scenarios']} / {info['candidates']} / {info['labelled_decisions']}**",
        f"- Exact requirement status accuracy: **{_fmt(m['exact_status_accuracy'])}** ({m['correct']}/{m['total']})",
        f"- Matched precision / recall / F1: **{_fmt(m['matched_precision'])} / {_fmt(m['matched_recall'])} / {_fmt(m['matched_f1'])}**",
        f"- False-positive matched: **{m['false_positive_matched']}**; missed matches: **{m['false_negative_matched']}**",
        f"- Uncertain recall: **{_fmt(m['uncertain_recall'])}**",
        f"- JD extraction precision / recall: **{_fmt(jd['precision'])} / {_fmt(jd['recall'])}**",
        f"- JD priority accuracy: **{_fmt(jd['priority_accuracy'])}**",
        f"- Mean pairwise ranking agreement, including ties: **{_fmt(rank['macro_pairwise_accuracy_with_ties'])}**",
        f"- Mean nDCG@{rank['top_k']}: **{_fmt(rank['macro_ndcg_at_k'])}**",
        f"- Pipeline / candidate failures: **{info['pipeline_failures']} / {info['candidate_failures']}**", "",
        "## Per-department results", "",
        "| Department | Requirement accuracy | Matched precision | Matched recall | Pairwise ranking | JD recall |", "|---|---:|---:|---:|---:|---:|",
    ]
    for s in report["scenarios"]:
        m = s["row_metrics"]
        lines.append(f"| {s['department']} | {_fmt(m['exact_status_accuracy'])} | {_fmt(m['matched_precision'])} | {_fmt(m['matched_recall'])} | {_fmt(s['rank_metrics']['pairwise_accuracy_with_ties'])} | {_fmt(s['jd_metrics']['recall'])} |")
    lines.extend(["", "## Highest-priority errors", "", "These failures should be reviewed before tuning any model or Python rule:", ""])
    failures = [r for s in report["scenarios"] for c in s["candidates"] for r in c["rows"] if not r["correct"]]
    for r in failures[:40]:
        quote = (r["ground_truth_quote"] or "<no source excerpt>").replace("|", "\\|")
        lines.append(f"- `{r['scenario']}/{r['candidate']}/{r['requirement_id']}` **{r['requirement_name']}**: expected `{r['expected']}`, predicted `{r['predicted']}`. Gold excerpt: {quote}")
    if len(failures) > 40:
        lines.append(f"- ...plus {len(failures) - 40} additional errors. See the JSON.")
    if not failures:
        lines.append("- No errors on the selected dataset (this does not establish general reliability).")
    lines.extend(["", "## Known limitations", "", "- Every CV and JD is a short text fixture; PDF/DOCX/OCR quality is NOT measured.",
                  "- The manually authored labels are not independently reviewed by HR domain experts.",
                  "- No protected characteristics or actual applicant data were used; fairness and real-world validity are NOT established.",
                  "- Gold ranking derives from the same documented required-coverage policy; it is not a hiring-outcome ground truth.",
                  "- Eligibility labels and external credential authenticity are outside this benchmark.",
                  "- For live runs, preserve the JSON and note that Python validators and fallback can change Qwen statuses.", ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 7E frozen-JD multi-candidate quality evaluation")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", choices=("fallback", "live"), default="fallback")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--scenario", action="append", help="Repeatable scenario/department filter")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--exact-initialism", action="store_true", help="Opt in to Phase 6D literal initialism recovery; results are Python-assisted, not model-only")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "phase7e_benchmark.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "outputs" / "phase7e_supervisor_report.md")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.dataset.resolve(), scenario_ids=args.scenario, model=args.model, mode=args.mode, top_k=args.top_k, exact_initialism=args.exact_initialism)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(report, args.markdown)
    except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Dataset/benchmark error: {exc}\n")
    m = report["summary"]["requirement_metrics"]
    rank = report["summary"]["ranking"]
    jd = report["summary"]["jd_extraction"]
    print("PHASE 7E — EXPANDED INDEPENDENT SYNTHETIC BENCHMARK")
    print(f"Build: {report['build_id']} | Mode: {report['mode']} | Exact initialism: {report['exact_initialism_guard']}")
    print(f"Dataset: {report['dataset_id']} | SHA256: {report['dataset_sha256']}")
    print(f"Scenarios={report['summary']['scenarios']} Candidates={report['summary']['candidates']} Decisions={m['total']}")
    print(f"Status accuracy: {_fmt(m['exact_status_accuracy'])} ({m['correct']}/{m['total']})")
    print(f"Matched precision={_fmt(m['matched_precision'])} recall={_fmt(m['matched_recall'])} F1={_fmt(m['matched_f1'])}")
    print(f"False-positive matches={m['false_positive_matched']} Missed matches={m['false_negative_matched']}")
    print(f"JD recall={_fmt(jd['recall'])} JD precision={_fmt(jd['precision'])}")
    print(f"Macro pairwise rank agreement={_fmt(rank['macro_pairwise_accuracy_with_ties'])} nDCG@{args.top_k}={_fmt(rank['macro_ndcg_at_k'])}")
    print(f"Modes: {report['summary']['evaluation_modes']}")
    print("WARNING: Synthetic labels are not external hiring ground truth. No production accuracy claim.")
    print(f"Saved: {args.output} | {args.markdown}")
    return 0 if report["summary"]["pipeline_failures"] == 0 and report["summary"]["candidate_failures"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())

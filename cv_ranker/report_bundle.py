"""One-click, self-contained supervisor export of the current assessed run."""
from __future__ import annotations

import csv
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from .schemas import RankingReport
from .ranking_reasoning import candidate_reasoning, comparative_reasoning
from .ui_support import review_label_for_candidate
from .ui.unified_decisions import reconcile_unified_candidate
from .weighted_scoring import ScoreWeights, weighted_leaderboard


def complete_results_zip(
    report: RankingReport, weights: ScoreWeights,
    *, final_results: dict[str, dict] | None = None,
    source_ledgers: dict[str, list[dict]] | None = None,
    technical: dict | None = None,
) -> bytes:
    """Build from already-published state, not by rerunning the model.

    Source texts are intentionally included: this is an explicitly requested,
    sensitive reviewer export. The archive contains no API configuration,
    environment variables, uploaded file paths, or credentials.
    """
    ledgers = source_ledgers or {}
    # Derive the per-requirement Why and verdict from the canonical assessed
    # source when no independent UI projection was supplied. A caller's UI
    # projection may add highlights but cannot contradict the persisted record.
    finals = {}
    for index, candidate in enumerate(report.candidates):
        key = str(index)
        proposed = (final_results or {}).get(key)
        if proposed is None:
            proposed = reconcile_unified_candidate(report, index, ledgers.get(key, []))
        original_rows = {row.get("ID"): row for row in proposed.get("Criteria", [])
                         if isinstance(row, dict)}
        for assessment in candidate.assessments:
            record = assessment.current_decision
            if record is None:
                continue  # Historical material retains its own interpretation.
            expected = (record.verdict if record.processing_state == "completed"
                        else "Assessment incomplete")
            current = original_rows.get(assessment.requirement_id)
            if current is not None and current.get("Result") != expected:
                raise ValueError("UI/export decision disagrees with the canonical assessment record: "
                                 + assessment.requirement_id)
        finals[key] = proposed
    leaderboard = weighted_leaderboard(report, weights)
    # Match the UI's separate completion and human-review states in all
    # supervisor-facing exports; weighted scoring remains authoritative.
    review_labels = {str(index): review_label_for_candidate(candidate, finals.get(str(index)))
                     for index, candidate in enumerate(report.candidates)}
    result = io.BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED, compresslevel=7) as archive:
        def add_json(name: str, data: object) -> None:
            archive.writestr(name, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

        if report.original_jd_text is not None:
            archive.writestr("original_job_description.txt", report.original_jd_text)
        else:
            archive.writestr("original_job_description_unavailable.txt",
                             "This report predates retention of the original JD text. "
                             "The original submission cannot be reconstructed from frozen criteria.\n")
        add_json("approved_jd_requirements.json", [r.model_dump() for r in report.requirements])
        add_json("scoring_weights.json", weights.as_dict())
        add_json("weighted_requirement_allocations.json", [
            {"candidate_index": row["candidate_index"],
             "candidate": row["candidate"],
             "contributions": row["breakdown"].get("requirement_contributions", [])}
            for row in leaderboard])
        add_json("complete_assessment.json", report.model_dump())
        add_json("final_decisions_all_candidates.json", finals)
        add_json("overall_ranking_reasoning.json", comparative_reasoning(report, weights, finals, ledgers))
        add_json("technical_diagnostics.json", technical or {})

        table = io.StringIO()
        fields = ["Rank", "Candidate", "Weighted score (%)", "Score status", "Possible ceiling (%)", "Experience matched",
                  "Education matched", "JD matched", "Required JD matched", "Preferred JD matched",
                  "Transferable", "Review"]
        writer = csv.DictWriter(table, fieldnames=fields)
        writer.writeheader()

        def csv_cell(value):
            # Spreadsheet viewers may execute formulas even inside quoted CSV
            # fields. Untrusted candidate names and reviewer text are data.
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                return "'" + value
            return value

        for row in leaderboard:
            idx = str(row["candidate_index"])
            final = finals.get(idx, {})
            writer.writerow({key: csv_cell(value) for key, value in {
                "Rank": (f"Provisional {row['rank']}" if row.get("provisional") else row["rank"])
                        if row["rank"] is not None else "Unavailable",
                "Candidate": row["candidate"],
                "Weighted score (%)": row["weighted_score"],
                "Score status": row["score_status"],
                "Possible ceiling (%)": row["breakdown"].get("possible_ceiling"),
                "Experience matched": row["experience"],
                "Education matched": row["education"],
                "JD matched": row["jd_overall"],
                "Required JD matched": row["required"],
                "Preferred JD matched": row["preferred"],
                "Transferable": final.get("Transferable", "Not checked"),
                "Review": review_labels.get(idx, row["review"]),
            }.items()})
        archive.writestr("weighted_leaderboard.csv", table.getvalue().encode("utf-8-sig"))

        for row in leaderboard:
            index = str(row["candidate_index"])
            final = finals.get(index)
            candidate = report.candidates[int(index)]
            # Positional references remain unambiguous, even for identical CV names.
            path = f"candidates/candidate_{int(index) + 1:03d}"
            add_json(path + "_results.json", {
                "candidate": candidate.model_dump(),
                "weighted_result": {**row, "review": review_labels.get(index, row["review"])},
                "final_decisions": final,
                "why": ([{"requirement": item.get("Requirement"),
                           "decision": item.get("Result"),
                           "reason": item.get("Why"),
                           "checkpoints": item.get("Checkpoints", [])}
                          for item in final.get("Criteria", [])] if final else []),
                "candidate_ranking_why": candidate_reasoning(
                    report, int(index), weights, finals, ledgers),
            })
            if index in ledgers:
                add_json(path + "_original_cv_segments.json", ledgers[index])
        add_json("export_info.json", {
            "build_id": report.build_id, "candidate_count": len(report.candidates),
            "includes_original_jd": report.original_jd_text is not None,
            "original_jd_source": report.job_description_source,
            "weighted_rank_basis": "Verified Found credit only with editable requirement shares; incomplete candidates have no official score or rank; separately labeled provisional bounds may be shown",
            "important": "CV claims are self-reported; Transferable never earns direct credit."
        })
    return result.getvalue()

"""Keep the reconciled leaderboard visible and consistent with the detail table."""

from pathlib import Path
from types import SimpleNamespace
import pytest

from cv_ranker.ui_support import final_leaderboard_rows
from cv_ranker.schemas import CandidateResult
from cv_ranker.scoring import assign_ranks


def _candidate(name, required=0, total=9, preferred=0, preferred_total=7, failed=False):
    return CandidateResult(
        candidate_name=name, matched_required=required, total_required=total,
        matched_preferred=preferred, total_preferred=preferred_total,
        primary_score=None if failed else round(100 * required / total, 2),
        preferred_score=None if failed else round(100 * preferred / preferred_total, 2),
        evaluation_mode="failed" if failed else "llm_assessed",
        errors=[],
    )


def _final(required, preferred, transferable=0, provisional=False):
    return {
        "Required matched": required, "Required total": 9,
        "Preferred matched": preferred, "Preferred total": 7,
        "Transferable": transferable, "Provisional": provisional,
    }


def test_leaderboard_uses_final_counts_and_preferred_tiebreak():
    report = SimpleNamespace(candidates=[
        _candidate("Candidate B", required=8, preferred=2),
        _candidate("Candidate C", required=7, preferred=7),
        _candidate("Candidate A", required=8, preferred=3),
    ])
    assign_ranks(report.candidates)
    finals = {
        "0": _final(8, 2, transferable=3),
        "1": _final(7, 7, transferable=5),
        "2": _final(8, 3, transferable=0, provisional=True),
    }
    rows = final_leaderboard_rows(report, finals)
    assert [row["Candidate"] for row in rows] == ["Candidate A", "Candidate B", "Candidate C"]
    assert [row["Rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["Score"] == 88.9
    assert rows[0]["Required"] == "8/9"
    assert rows[0]["Preferred"] == "3/7"
    assert rows[0]["Review"] == "Provisional · review"
    assert rows[1]["Transferable"] == 3
    assert rows[1]["Score"] == 88.9  # transferability never awards extra points
    assert rows[2]["Score"] == 77.8


def test_unfinished_candidates_do_not_appear_as_zero_percent_matches():
    report = SimpleNamespace(candidates=[
        _candidate("Failed CV", failed=True),
        _candidate("Earlier CV", required=5, preferred=2),
        _candidate("Final CV", required=9, preferred=7),
    ])
    assign_ranks(report.candidates)
    rows = final_leaderboard_rows(report, {"2": _final(9, 7)})
    assert [r["Candidate"] for r in rows] == ["Final CV", "Earlier CV", "Failed CV"]
    assert rows[1]["Required"] == "5/9"
    assert rows[1]["Preferred"] == "2/7"
    assert rows[1]["Transferable"] == "Not checked"
    assert rows[1]["Review"] == "Earlier run · rerun"
    assert rows[2]["Score"] is None
    assert rows[2]["Review"] == "Assessment unavailable · rerun"
    assert rows[2]["Required"] == "Not assessed"


def test_inconsistent_detail_cannot_override_source_of_truth_score():
    report = SimpleNamespace(candidates=[_candidate("Audited", required=8, preferred=2)])
    with pytest.raises(ValueError, match="Leaderboard/detail count mismatch"):
        final_leaderboard_rows(report, {"0": _final(9, 2)})


def test_page_renders_leaderboard_before_candidate_details():
    source = (Path(__file__).resolve().parents[1] /
              "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    results_block = source.split("with results:", 1)[1].split("with sources:", 1)[0]
    assert results_block.index("_summary(report)") < results_block.index("_ranking(report)")
    assert results_block.index("_ranking(report)") < results_block.index("_candidate_evidence(report)")

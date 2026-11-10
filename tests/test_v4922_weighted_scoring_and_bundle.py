"""Configurable 10/10/80 ranking and a complete, self-contained run export."""
import csv
import io
import json
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.schemas import (CandidateResult, RankingReport, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.weighted_scoring import (
    ScoreWeights, criterion_bucket_counts, weighted_candidate, weighted_leaderboard,
)


def req(rid, kind="skill", priority="required", *, minimum_years=None):
    return ValidatedRequirement(requirement_id=rid, name=rid, priority=priority,
                                jd_evidence=rid, constraint=RequirementConstraint(
                                    kind=kind, minimum_years=minimum_years))


def candidate(name, statuses, *, unverified=False):
    return CandidateResult(candidate_name=name, primary_score=None if unverified else 50.0,
                           required_score=None if unverified else 50.0,
                           assessments=[RequirementAssessment(
                               requirement_id=rid,
                               status="matched" if status == "Found" else "not_matched",
                               unified_status="Unverified" if unverified else status,
                               assessment_state="unverified" if unverified else "verified",
                           ) for rid, status in statuses.items()])


def report(requirements, candidates, original="Required: ..."):
    return RankingReport(job_description_source="uploaded JD", original_jd_text=original,
                         jd_validation_mode="llm_validated", yake_candidates=[],
                         requirements=requirements, candidates=candidates)


def test_ten_ten_eighty_is_disjoint_and_out_of_100():
    requests = [req("role", "experience", minimum_years=3), req("degree", "education"),
                req("python"), req("docker")]
    cv = candidate("A", {"role": "Found", "degree": "Found",
                         "python": "Found", "docker": "Not Found"})
    scored = weighted_candidate(report(requests, [cv]), cv, ScoreWeights())
    assert scored["score"] == 60.0  # 10 + 10 + 80*(1/2)
    assert sum(scored["effective_weights"].values()) == 100.0
    assert scored["components"]["jd_required"]["total"] == 2


def test_jd_counts_exclude_numeric_tenure_and_degrees_but_keep_qualitative_work():
    requests = [
        req("tenure", "experience", minimum_years=3),
        req("degree", "education"),
        req("python"),
        req("prod_apis", "experience", "preferred"),
        req("cloud", priority="preferred"),
    ]
    cv = candidate("Engineer", {"tenure": "Found", "degree": "Found",
                                "python": "Found", "prod_apis": "Found",
                                "cloud": "Not Found"})
    frozen = report(requests, [cv])
    counts = criterion_bucket_counts(frozen, cv)
    assert counts == {
        "experience": {"found": 1, "total": 1},
        "education": {"found": 1, "total": 1},
        "jd_required": {"found": 1, "total": 1},
        "jd_preferred": {"found": 1, "total": 2},
    }
    leaderboard = weighted_leaderboard(frozen, ScoreWeights())
    assert leaderboard[0]["required"] == "1/1"
    assert leaderboard[0]["preferred"] == "1/2"
    assert leaderboard[0]["experience"] == "1/1"
    assert leaderboard[0]["education"] == "1/1"
    assert leaderboard[0]["jd_overall"] == "2/3"
    assert leaderboard[0]["weighted_score"] == 73.33
    split_score = weighted_candidate(frozen, cv, ScoreWeights(split_jd=True,
                                                             required_share=75))
    assert split_score["score"] == 73.33


def test_missing_categories_are_neutral_and_remaining_weights_rebalance():
    requests = [req("a"), req("b")]
    cv = candidate("A", {"a": "Found", "b": "Not Found"})
    scored = weighted_candidate(report(requests, [cv]), cv, ScoreWeights())
    assert scored["score"] == 50.0
    assert scored["effective_weights"]["jd"] == 100
    assert scored["effective_weights"]["experience"] == 0
    assert scored["effective_weights"]["education"] == 0


def test_required_preferred_split_is_display_only_and_does_not_change_credit():
    requests = [req("required"), req("preferred", priority="preferred")]
    cv = candidate("A", {"required": "Not Found", "preferred": "Found"})
    frozen = report(requests, [cv])
    assert weighted_candidate(frozen, cv, ScoreWeights())["score"] == 50
    weights = ScoreWeights(split_jd=True, required_share=75)
    assert weighted_candidate(frozen, cv, weights)["score"] == 50
    assert weights.as_dict()["jd_allocation"] == "pooled"
    assert weights.as_dict()["jd_preferred_share"] is None


def test_one_preferred_cannot_take_half_of_jd_allocation_when_nine_required_match():
    requirements = ([req("tenure", "experience", minimum_years=3),
                     req("degree", "education")]
                    + [req(f"R{i}") for i in range(9)]
                    + [req("P0", priority="preferred")])
    statuses = {"tenure": "Found", "degree": "Found", "P0": "Not Found"}
    statuses.update({f"R{i}": "Found" for i in range(9)})
    cv = candidate("Nearly complete", statuses)
    frozen = report(requirements, [cv])
    for show_split in (False, True):
        for legacy_share in (0, 50, 100):
            result = weighted_candidate(
                frozen, cv, ScoreWeights(split_jd=show_split, required_share=legacy_share))
            assert result["score"] == 92.0
            assert result["jd_combined"] == {"found": 9, "total": 10}
            assert result["effective_weights"] == {
                "experience": 10.0, "education": 10.0, "jd": 80.0}
    statuses["P0"] = "Found"
    full = candidate("Full match", statuses)
    assert weighted_candidate(report(requirements, [full]), full, ScoreWeights())["score"] == 100


def test_equal_pooled_scores_rank_equally_regardless_of_required_preferred_mix():
    requirements = [req("R1"), req("R2"), req("P1", priority="preferred")]
    frozen = report(requirements, [
        candidate("Required first", {"R1": "Found", "R2": "Found", "P1": "Not Found"}),
        candidate("Preferred first", {"R1": "Found", "R2": "Not Found", "P1": "Found"}),
    ])
    rows = weighted_leaderboard(frozen, ScoreWeights())
    assert {r["weighted_score"] for r in rows} == {66.67}
    assert {r["rank"] for r in rows} == {1}
    assert {r["jd_overall"] for r in rows} == {"2/3"}


def test_default_jd_score_includes_all_preferred_criteria_and_matches_export_example():
    requirements = ([req("tenure", "experience", minimum_years=3),
                     req("degree", "education")]
                    + [req(f"R{i}") for i in range(9)]
                    + [req(f"P{i}", priority="preferred") for i in range(7)])
    statuses = {"tenure": "Found", "degree": "Not Found"}
    statuses.update({f"R{i}": "Found" if i < 8 else "Not Found" for i in range(9)})
    statuses.update({f"P{i}": "Not Found" for i in range(7)})
    cv = candidate("Example", statuses)
    frozen = report(requirements, [cv])
    result = weighted_candidate(frozen, cv, ScoreWeights())
    # 10% * 1/1 experience + 10% * 0/1 education + 80% * 8/16 JD.
    assert result["score"] == 50.0
    assert result["components"]["jd_required"] == {"found": 8, "total": 9}
    assert result["components"]["jd_preferred"] == {"found": 0, "total": 7}
    assert result["jd_combined"] == {"found": 8, "total": 16}
    assert result["effective_weights"] == {
        "experience": 10.0, "education": 10.0, "jd": 80.0,
    }
    leaderboard = weighted_leaderboard(frozen, ScoreWeights())
    assert leaderboard[0]["weighted_score"] == 50.0
    with ZipFile(io.BytesIO(complete_results_zip(frozen, ScoreWeights()))) as archive:
        exported = next(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
    assert exported["Weighted score (%)"] == "50.0"
    assert exported["JD matched"] == "8/16"
    assert exported["Required JD matched"] == "8/9"
    assert exported["Preferred JD matched"] == "0/7"


def test_preferred_found_affects_default_score_without_split():
    requirements = [req("required"), req("preferred", priority="preferred")]
    frozen = report(requirements, [
        candidate("Both", {"required": "Found", "preferred": "Found"}),
        candidate("One", {"required": "Found", "preferred": "Not Found"}),
    ])
    rows = weighted_leaderboard(frozen, ScoreWeights())
    assert [row["weighted_score"] for row in rows] == [100, 50]
    assert ScoreWeights().as_dict()["jd_allocation"] == "pooled"
    assert ScoreWeights().as_dict()["jd_preferred_share"] is None


def test_preferred_only_jd_receives_its_full_applicable_weight():
    requests = [req("preferred", priority="preferred")]
    cv = candidate("A", {"preferred": "Found"})
    assert weighted_candidate(report(requests, [cv]), cv, ScoreWeights())["score"] == 100


def test_unverified_cannot_become_numeric_or_ranked():
    requests = [req("skill")]
    good = candidate("Good", {"skill": "Found"})
    failed = candidate("Unverified", {"skill": "Not Found"}, unverified=True)
    frozen = report(requests, [failed, good])
    results = weighted_leaderboard(frozen, ScoreWeights())
    assert results[0]["candidate"] == "Good"
    assert results[0]["weighted_score"] == 100
    assert results[1]["weighted_score"] is None
    assert results[1]["rank"] is None


def test_no_positive_weights_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        ScoreWeights(0, 0, 0)


@pytest.mark.parametrize("values", [(10, 10, 70), (10, 10, 90), (90, 20, 0)])
def test_weights_must_allocate_exactly_one_hundred_marks(values):
    with pytest.raises(ValueError, match="exactly 100"):
        ScoreWeights(*values)


def test_first_page_contains_weightage_and_results_navigation_without_demo_picker():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(
        encoding="utf-8")
    form = source.split("def _run_form(", 1)[1].split("@st.fragment", 1)[0]
    sidebar = source.split("def _sidebar(", 1)[1].split("def _uploaded_identity(", 1)[0]
    assert "weights_valid = _weightage_panel(approved.requirements)" in form
    assert form.index("_review_jd_panel(settings, pending)") < form.index("_weightage_panel(approved.requirements)")
    assert "Allocate exactly 100 marks before extracting" not in form
    assert "Continue to Results" in form
    assert 'args=("02  Rankings & evidence",)' in form
    assert 'key="cv_active_page", on_change="rerun"' in source
    assert "Select bundled demo" not in form
    assert "Analyze demo CVs" not in form
    assert "Sample candidates" not in form
    assert "Session controls" in sidebar
    assert "Clear current results" in sidebar
    assert "Changing one share automatically rebalances" in source


def test_compact_weightage_split_and_employer_policy_controls_are_in_correct_places():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(
        encoding="utf-8")
    weightage = source.split("def _weightage_panel(", 1)[1].split("def _get_report(", 1)[0]
    sidebar = source.split("def _sidebar(", 1)[1].split("def _uploaded_identity(", 1)[0]
    form = source.split("def _run_form(", 1)[1].split("@st.fragment", 1)[0]

    assert 'with st.expander(' in weightage
    assert 'Step 4 · Category weightage' in weightage
    assert 'Step 5 · Edit individual JD allocations' in weightage
    assert 'Weightage presets' not in source
    assert 'cv_weight_split_button' in sidebar
    assert 'cv_weight_split_button' not in weightage
    assert '"Required share of JD"' not in weightage
    assert 'Employer policies · optional' in sidebar
    assert 'key="approved_aliases"' in sidebar
    assert 'Optional HR policies (advanced)' not in form
    assert 'YAKE candidate phrases limit' in sidebar
    assert 'key="cv_yake_top_k"' in sidebar
    assert 'yake_top_k=yake_limit' in sidebar
    assert 'Recognize literal initials' not in sidebar
    assert 'LLM suggestions for ambiguous JD types' not in sidebar
    assert 'Frozen JD requirement processing limit' in sidebar
    assert 'Automatically resume unfinished cloud assessments' in sidebar


def test_yake_display_is_ranked_by_raw_lower_is_better_scores():
    from cv_ranker.schemas import YakeCandidate
    from cv_ranker.ui.dashboard import _yake_display_rows

    rows = _yake_display_rows([
        YakeCandidate(keyword="Cloud", score=0.018),
        YakeCandidate(keyword="Deep learning", score=0.003),
        YakeCandidate(keyword="NLP", score=0.011),
    ])
    assert [row["JD phrase"] for row in rows] == ["Deep learning", "NLP", "Cloud"]
    assert [row["Rank"] for row in rows] == [1, 2, 3]
    assert [row["YAKE score"] for row in rows] == [0.003, 0.011, 0.018]


def test_yake_candidate_limit_is_forwarded_to_keyword_extractor(monkeypatch):
    from cv_ranker.config import Settings
    from cv_ranker.yake_extractor import extract_yake_candidates

    requested = []

    class FakeExtractor:
        def __init__(self, **kwargs):
            requested.append(kwargs["top"])

        def extract_keywords(self, text):
            return [("medical imaging", 0.012)]

    monkeypatch.setitem(sys.modules, "yake", SimpleNamespace(KeywordExtractor=FakeExtractor))
    for limit in (10, 40, 95, 200):
        phrases = extract_yake_candidates(
            "Medical imaging research and clinical inference tools",
            Settings(llm_provider="ollama", yake_top_k=limit),
        )
        assert [item.keyword for item in phrases] == ["medical imaging"]
    assert requested == [10, 40, 95, 200]


def test_results_button_switches_stateful_streamlit_tab():
    from streamlit.testing.v1 import AppTest

    def page():
        import streamlit as st

        st.tabs(["01  Analyze", "02  Rankings & evidence"],
                default="01  Analyze", key="cv_active_page", on_change="rerun")
        st.button("Continue to Results", on_click=lambda: st.session_state.__setitem__(
            "cv_active_page", "02  Rankings & evidence"))

    app = AppTest.from_function(page).run(timeout=12)
    assert not app.exception
    assert app.session_state["cv_active_page"] == "01  Analyze"
    app.button[0].click().run(timeout=12)
    assert not app.exception
    assert app.session_state["cv_active_page"] == "02  Rankings & evidence"


def test_one_click_zip_contains_original_jd_all_candidates_reasons_and_cv_segments():
    requests = [req("R001"), req("R002", priority="preferred")]
    left = candidate("Candidate A", {"R001": "Found", "R002": "Not Found"})
    right = candidate("Candidate B", {"R001": "Not Found", "R002": "Found"})
    frozen = report(requests, [left, right], original="Original JD\nPython\nRequired work\n")
    finals = {"0": {"Transferable": 0, "Criteria": [
                  {"Requirement": "R001", "Result": "Found", "Why": "Direct API evidence",
                   "Checkpoints": [{"Segment": "S001", "Text": "Built API"}]}]},
              "1": {"Transferable": 1, "Criteria": [
                  {"Requirement": "R001", "Result": "Not Found", "Why": "No comparable work",
                   "Checkpoints": []}]}}
    ledgers = {"0": [{"segment_id": "S001", "section": "experience", "text": "Built API"}],
               "1": [{"segment_id": "S001", "section": "skills", "text": "Python"}]}
    contents = complete_results_zip(frozen, ScoreWeights(), final_results=finals,
                                    source_ledgers=ledgers)
    with ZipFile(io.BytesIO(contents)) as archive:
        assert archive.testzip() is None
        assert archive.read("original_job_description.txt").decode() == frozen.original_jd_text
        assert "complete_assessment.json" in archive.namelist()
        assert "scoring_weights.json" in archive.namelist()
        assert "candidates/candidate_001_original_cv_segments.json" in archive.namelist()
        assert "candidates/candidate_002_original_cv_segments.json" in archive.namelist()
        first = json.loads(archive.read("candidates/candidate_001_results.json"))
        assert first["why"][0]["reason"] == "Direct API evidence"
        assert first["why"][0]["checkpoints"][0]["Text"] == "Built API"
        rows = list(csv.DictReader(io.StringIO(archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
        assert len(rows) == 2
        assert {r["Candidate"] for r in rows} == {"Candidate A", "Candidate B"}
        assert "Weighted score (%)" in rows[0]
        assert "Required score (%)" not in rows[0]
        assert "Required JD matched" in rows[0]
        assert "Preferred JD matched" in rows[0]
        assert "JD matched" in rows[0]
        assert "Experience matched" in rows[0]
        assert "Education matched" in rows[0]


def test_earlier_report_without_original_jd_is_honest_in_export():
    frozen = report([], [], original="")
    frozen.original_jd_text = None
    with ZipFile(io.BytesIO(complete_results_zip(frozen, ScoreWeights()))) as archive:
        assert "original_job_description.txt" not in archive.namelist()
        assert "original_job_description_unavailable.txt" in archive.namelist()

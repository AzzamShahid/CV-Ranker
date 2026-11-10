"""Supervisor view helpers may never add or alter candidate matching decisions."""
from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.ui_support import (
    candidate_assessment_rows,
    review_semantic_import,
    supervisor_csv_bytes,
)


def report():
    return RankingReport(
        job_description_source="synthetic.txt", jd_validation_mode="llm_validated",
        yake_candidates=[],
        requirements=[ValidatedRequirement(requirement_id="R001", name="FastAPI", priority="required", jd_evidence="FastAPI")],
        candidates=[CandidateResult(candidate_name="a.txt", candidate_source="sample_data/a.txt", rank=1,
                                    primary_score=100.0, matched_primary=1, total_primary=1,
                                    matched_required=1, total_required=1, required_score=100.0,
                                    evaluation_mode="llm_assessed")],
    )


def semantic():
    return {"mode": "qwen_transferability_shadow_not_scoring", "scoring_unchanged": True, "complete": True,
            "candidates": [{"candidate_name": "a.txt", "original_primary_score": 100.0,
                            "original_rank": 1, "status": "completed_provisional", "assessments": []}]}


def test_csv_includes_primary_and_mode():
    data = supervisor_csv_bytes(report()).decode("utf-8-sig")
    assert "Candidate" in data and "Primary score" in data and "a.txt" in data and "100.0" in data
    assert "sample_data/a.txt" not in data


def test_rows_respect_unassessed_without_automatic_credit():
    data = candidate_assessment_rows(report(), 0)
    assert data[0]["Result"] == "Not evaluated"
    assert data[0]["Requirement"] == "FastAPI"


def test_semantic_import_accepts_sanity_match_with_warning():
    valid, warning = review_semantic_import(semantic(), report())
    assert valid and "JD identity" in warning


def test_semantic_import_rejects_mismatched_candidate():
    raw = semantic()
    raw["candidates"][0]["candidate_name"] = "other.txt"
    assert review_semantic_import(raw, report())[0] is False


def test_semantic_import_rejects_changed_rank_and_score():
    raw = semantic()
    raw["candidates"][0]["original_primary_score"] = 95.0
    assert review_semantic_import(raw, report())[0] is False
    raw = semantic()
    raw["candidates"][0]["original_rank"] = 2
    assert review_semantic_import(raw, report())[0] is False


def test_semantic_import_rejects_incomplete_results():
    raw = semantic()
    raw["complete"] = False
    assert review_semantic_import(raw, report())[0] is False
    raw = semantic()
    raw["candidates"][0]["status"] = "failed"
    assert review_semantic_import(raw, report())[0] is False


def test_semantic_import_rejects_unrecognized_or_missing_files():
    assert review_semantic_import([], report())[0] is False
    assert review_semantic_import({"mode": "fake"}, report())[0] is False


def test_semantic_import_rejects_duplicate_candidate_names():
    rep = report()
    rep = rep.model_copy(update={"candidates": [rep.candidates[0], rep.candidates[0]]})
    raw = semantic()
    raw["candidates"].append(dict(raw["candidates"][0]))
    assert review_semantic_import(raw, rep)[0] is False

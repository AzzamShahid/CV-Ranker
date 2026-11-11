"""Restart-safe reviewer exports and realistic no-network end-to-end checks."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from cv_ranker import CVRanker, Settings
from cv_ranker.build_info import BUILD_ID
from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
from cv_ranker.recovery_bundle import (
    MAX_ARCHIVE_BYTES, export_recovery_checkpoint,
    import_recovery_checkpoint, local_signing_key,
)
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.schemas import RankingReport
from cv_ranker.ui.dashboard import _restore_portable_run
from cv_ranker.weighted_scoring import ScoreWeights, weighted_leaderboard


@pytest.fixture
def signed_run(tmp_path):
    """Run a real typed-JD and multi-CV pipeline without provider requests."""
    jd = tmp_path / "jd.txt"
    jd.write_text(
        "Required Skills:\nPrepare monthly financial statements\n"
        "Bachelor's degree in Accounting\n3 years of accounting experience\n"
        "Preferred Skills:\nSpreadsheet reporting\n",
        encoding="utf-8",
    )
    first = tmp_path / "candidate_one.txt"
    first.write_text(
        "Bachelor of Accounting.\nWork Experience: 5 years of accounting experience.\n"
        "Prepared monthly financial statements and spreadsheet reporting.\n",
        encoding="utf-8",
    )
    second = tmp_path / "candidate_two.txt"
    second.write_text(
        "General office administration. Scheduling meetings and preparing agendas.\n",
        encoding="utf-8",
    )
    ranker = CVRanker(Settings(), use_llm=False)
    draft = ranker.prepare_jd_review(jd)
    reviewed_rows = editable_jd_rows(draft)
    # Structural no-model extraction conservatively excludes action-only
    # sentences. The reviewer can restore an actually stated JD criterion,
    # with a literal source quote, without teaching the engine a profession.
    reviewed_rows.append({
        "ID": "", "Priority": "required",
        "Requirement": "Prepare monthly financial statements",
        "Type": "responsibility",
        "JD source": "Prepare monthly financial statements",
    })
    approved = approve_jd_rows(
        draft=draft, rows=reviewed_rows,
        jd_text=jd.read_text(encoding="utf-8"),
        max_requirements=ranker.settings.max_requirements,
    )
    assert approved.approved and approved.edited
    report = ranker.run(jd, [first, second], approved_jd=approved)
    assert report.jd_review_approved
    assert report.build_id == BUILD_ID
    assert len(report.candidates) == 2
    assert len(report.requirements) >= 4
    assert all(candidate.primary_score is not None for candidate in report.candidates)
    weights = ScoreWeights(experience=15, education=15, jd=70)
    state = {
        "cv_ranking_report": report.model_dump(mode="json"),
        "cv_run_label": "Reviewer test run",
        "cv_run_provider": "offline exact fallback",
        "cv_source_ledgers": ranker.source_ledgers,
        "cv_request_metrics": {"actual_model_request_attempts": 0},
        "cv_weight_slider_experience": weights.experience,
        "cv_weight_slider_education": weights.education,
        "cv_weight_slider_jd": weights.jd,
        "cv_weight_split": False,
        "cv_requirement_allocations": {},
    }
    return report, weights, state


def test_multi_candidate_jd_to_scoring_to_export_to_recovery(signed_run):
    report, weights, state = signed_run
    original_scores = weighted_leaderboard(report, weights)
    results = complete_results_zip(report, weights)
    with ZipFile(io.BytesIO(results)) as archive:
        rows = list(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
        assert len(rows) == len(report.candidates)
        for actual, exported in zip(original_scores, rows):
            assert float(exported["Weighted score (%)"]) == actual["weighted_score"]
            assert exported["Candidate"] == actual["candidate"]
        assert any("financial statements" in req.name.lower()
                   for req in report.requirements)

    archive = export_recovery_checkpoint(state, b"K" * 32)
    restored = import_recovery_checkpoint(archive, b"K" * 32)
    restored_report = RankingReport.model_validate(restored["cv_ranking_report"])
    restored_weights = ScoreWeights(
        restored["cv_weight_slider_experience"],
        restored["cv_weight_slider_education"],
        restored["cv_weight_slider_jd"],
    )
    assert weighted_leaderboard(restored_report, restored_weights) == original_scores
    assert restored["cv_source_ledgers"] == state["cv_source_ledgers"]
    assert restored["cv_request_metrics"] == {"actual_model_request_attempts": 0}
    with ZipFile(io.BytesIO(archive)) as saved:
        assert sorted(saved.namelist()) == ["checkpoint.hmac", "checkpoint.json"]
        assert b"API_KEY" not in saved.read("checkpoint.json")


def test_imported_report_restores_weight_widgets_and_archives_prior_run(signed_run):
    _report, _weights, saved = signed_run
    existing = {"cv_ranking_report": {"old": "report"},
                "cv_run_label": "Old report",
                "cv_weight_slider_jd": 100,
                "cv_weight_number_jd": 100,
                "cv_item_share_old_dead": 42,
                "cv_candidate_selector": 9,
                "cv_jd_review_pending": {"old": "approval"},
                "cv_auto_resume_state": {"running": False}}
    checkpoint = import_recovery_checkpoint(
        export_recovery_checkpoint(saved, b"K" * 32), b"K" * 32)
    _restore_portable_run(existing, checkpoint)
    assert existing["cv_run_label"] == "Reviewer test run"
    assert existing["cv_active_page"] == "02  Rankings & evidence"
    assert existing["cv_weight_number_jd"] == 70
    assert existing["cv_weight_slider_jd"] == 70
    assert existing["cv_run_history"][0]["cv_run_label"] == "Old report"
    assert "cv_candidate_selector" not in existing
    assert "cv_jd_review_pending" not in existing
    assert "cv_auto_resume_state" not in existing
    assert "cv_item_share_old_dead" not in existing


def test_checkpoint_contains_remaining_budget_and_incomplete_candidate(signed_run):
    report, _weights, saved = signed_run
    # The authenticated checkpoint preserves the already consumed HTTP budget
    # while requiring the unchanged original inputs before the worker can resume.
    frozen = report.model_dump(mode="json")
    saved["cv_resume_cache"] = {
        "context_key": "f" * 64,
        "report": frozen,
        "candidates": {"candidate-key": report.candidates[0].model_dump(mode="json")},
        "assessment_http_attempts_total": 7,
    }
    saved["cv_request_metrics"] = {"assessment_http_attempts_cumulative": 7}
    restored = import_recovery_checkpoint(
        export_recovery_checkpoint(saved, b"K" * 32), b"K" * 32)
    assert restored["cv_resume_cache"]["assessment_http_attempts_total"] == 7
    assert restored["cv_resume_cache"]["context_key"] == "f" * 64


@pytest.mark.parametrize("wrong", ["x", "", "0" * 64])
def test_edited_or_wrong_key_rejected(signed_run, wrong):
    _report, _weights, state = signed_run
    archive = export_recovery_checkpoint(state, b"K" * 32)
    if wrong == "x":
        with ZipFile(io.BytesIO(archive)) as infile:
            files = {name: infile.read(name) for name in infile.namelist()}
        files["checkpoint.json"] = files["checkpoint.json"].replace(
            b"Reviewer test run", b"Tampered test run")
        rebuilt = io.BytesIO()
        with ZipFile(rebuilt, "w") as outfile:
            for name, body in files.items():
                outfile.writestr(name, body)
        archive = rebuilt.getvalue()
        key = b"K" * 32
    else:
        key = b"L" * 32
    with pytest.raises(ValueError, match="signature did not match"):
        import_recovery_checkpoint(archive, key)


def test_modified_cloud_budget_or_unknown_state_cannot_be_signed(signed_run):
    report, _weights, state = signed_run
    state["cv_resume_cache"] = {
        "context_key": "f" * 64,
        "report": report.model_dump(mode="json"),
        "candidates": {},
        "assessment_http_attempts_total": 7,
    }
    state["cv_request_metrics"] = {"assessment_http_attempts_cumulative": 0}
    with pytest.raises(ValueError, match="counters disagreed"):
        export_recovery_checkpoint(state, b"K" * 32)
    state.pop("cv_resume_cache")
    state["cv_run_provider"] = "offline"
    state["cv_request_metrics"] = {}
    state["cv_extra_untrusted_control"] = "ignored"
    with ZipFile(io.BytesIO(export_recovery_checkpoint(state, b"K" * 32))) as archive:
        assert "cv_extra_untrusted_control" not in json.loads(
            archive.read("checkpoint.json"))["snapshot"]


def test_invalid_request_metrics_are_rejected_cleanly(signed_run):
    _report, _weights, state = signed_run
    state["cv_request_metrics"] = ["malformed"]
    with pytest.raises(ValueError, match="request metrics"):
        export_recovery_checkpoint(state, b"K" * 32)
    state["cv_request_metrics"] = {"assessment_http_attempts_cumulative": -2}
    with pytest.raises(ValueError, match="cloud-request metrics"):
        export_recovery_checkpoint(state, b"K" * 32)


def test_incompatible_report_build_rejected(signed_run):
    _report, _weights, state = signed_run
    state["cv_ranking_report"]["build_id"] = "unrelated-build"
    with pytest.raises(ValueError, match="different assessment build"):
        export_recovery_checkpoint(state, b"K" * 32)


def test_recovery_rejects_unexpected_zip_member(signed_run):
    _report, _weights, state = signed_run
    original = export_recovery_checkpoint(state, b"K" * 32)
    with ZipFile(io.BytesIO(original)) as source:
        content = {name: source.read(name) for name in source.namelist()}
    rebuilt = io.BytesIO()
    with ZipFile(rebuilt, "w") as destination:
        for name, raw in content.items():
            destination.writestr(name, raw)
        destination.writestr("../unsafe.txt", b"do not trust")
    with pytest.raises(ValueError, match="unexpected"):
        import_recovery_checkpoint(rebuilt.getvalue(), b"K" * 32)


def test_archive_size_limit_enforced_before_decompression():
    with pytest.raises(ValueError, match="size is invalid"):
        import_recovery_checkpoint(b"not a ZIP" * (MAX_ARCHIVE_BYTES // 9 + 1),
                                   b"K" * 32)


def test_signing_key_survives_restart_without_entering_recovery_file(tmp_path):
    path = tmp_path / ".cv_ranker_cache" / "recovery_signing.key"
    first = local_signing_key(path)
    second = local_signing_key(path)
    assert first == second and len(first) == 32
    if path.exists():
        assert path.stat().st_mode & 0o077 == 0
    assert path.read_bytes() == first
    path.unlink()
    path.symlink_to(tmp_path / "untrusted-key")
    with pytest.raises(ValueError, match="symbolic link"):
        local_signing_key(path)


def test_source_packager_cannot_include_local_recovery_signing_key():
    from scripts.rebuild_manifest import EXCLUDED_DIRS, EXCLUDED_SECRET_SUFFIXES

    assert ".cv_ranker_cache" in EXCLUDED_DIRS
    assert ".key" in EXCLUDED_SECRET_SUFFIXES

from pathlib import Path

import pytest

from cv_ranker.schemas import CandidateResult, RankingReport
from cv_ranker.ui_support import ranking_rows, report_json_bytes, safe_upload_name, save_uploaded_bytes


def test_safe_upload_name_strips_paths_and_keeps_supported_extension():
    assert safe_upload_name(r"..\folder\resume.pdf") == "resume.pdf"
    assert safe_upload_name("../../resume.docx") == "resume.docx"


def test_safe_upload_name_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        safe_upload_name("resume.exe")


def test_save_uploaded_bytes_isolates_duplicate_names(tmp_path: Path):
    first = save_uploaded_bytes(
        root=tmp_path,
        group="resumes",
        index=1,
        filename="resume.txt",
        data=b"candidate one",
    )
    second = save_uploaded_bytes(
        root=tmp_path,
        group="resumes",
        index=2,
        filename="resume.txt",
        data=b"candidate two",
    )
    assert first.name == second.name == "resume.txt"
    assert first != second
    assert first.read_bytes() == b"candidate one"
    assert second.read_bytes() == b"candidate two"


def test_report_helpers_are_serializable():
    report = RankingReport(
        job_description_source="jd.txt",
        jd_validation_mode="fallback_structural",
        yake_candidates=[],
        requirements=[],
        candidates=[
            CandidateResult(
                candidate_name="a.txt",
                candidate_source="a.txt",
                rank=1,
                primary_score=75.0,
                matched_primary=3,
                total_primary=4,
                required_score=75.0,
                matched_required=3,
                total_required=4,
                evaluation_mode="fallback_exact",
            )
        ],
        warnings=[],
    )
    data = report_json_bytes(report)
    assert b'"candidate_name": "a.txt"' in data
    rows = ranking_rows(report)
    assert rows[0]["Rank"] == 1
    assert rows[0]["Primary score"] == 75.0
    assert rows[0]["Required coverage"] == 75.0


def test_safe_upload_name_handles_windows_reserved_names():
    assert safe_upload_name("CON.txt") == "_CON.txt"
    assert safe_upload_name("nul.pdf") == "_nul.pdf"


def test_safe_upload_name_truncates_pathological_long_names():
    name = ("a" * 300) + ".pdf"
    safe = safe_upload_name(name)
    assert safe.endswith(".pdf")
    assert len(Path(safe).stem) <= 120

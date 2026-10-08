from pathlib import Path

import fitz
from docx import Document
import pytest

from cv_ranker.documents import DocumentError, collect_resume_paths, extract_text


def test_extract_text_txt(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text("Candidate has Python and Docker experience.", encoding="utf-8")
    assert "Python" in extract_text(path)


def test_extract_text_docx_includes_paragraphs_and_tables(tmp_path: Path):
    path = tmp_path / "resume.docx"
    doc = Document()
    doc.add_paragraph("Candidate has Payroll Processing experience.")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Skill"
    table.cell(0, 1).text = "Microsoft Excel"
    doc.save(path)
    text = extract_text(path)
    assert "Payroll Processing" in text
    assert "Microsoft Excel" in text


def test_extract_text_pdf(tmp_path: Path):
    path = tmp_path / "resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Candidate has Python, PostgreSQL, and Docker experience.")
    doc.save(path)
    doc.close()
    text = extract_text(path)
    assert "Python" in text
    assert "PostgreSQL" in text


def test_extract_text_rejects_tiny_or_image_only_like_content(tmp_path: Path):
    path = tmp_path / "tiny.txt"
    path.write_text("Too short", encoding="utf-8")
    with pytest.raises(DocumentError):
        extract_text(path)


def test_collect_resume_paths_deduplicates_same_file(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text("Candidate has enough text for extraction testing.", encoding="utf-8")
    result = collect_resume_paths([str(path), str(path), str(tmp_path)])
    assert result == [path]

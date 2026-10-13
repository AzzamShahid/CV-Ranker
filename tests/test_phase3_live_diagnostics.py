"""Phase 3: source-line fidelity and live-doctor regression guards."""
from doctor import write_live_ranker_fixtures
from cv_ranker.documents import extract_text, DocumentError
from cv_ranker.pipeline import CVRanker
from cv_ranker.segments import segment_resume


def test_doctor_fixture_passes_actual_document_contract(tmp_path):
    jd, cv = write_live_ranker_fixtures(tmp_path)
    assert extract_text(jd).strip() == "Required Skills:\nPython"
    text = extract_text(cv)
    assert "Python" in text and len(text.strip()) >= 20
    report = CVRanker(use_llm=False).run(jd, [cv])
    assert [r.name for r in report.requirements] == ["Python"]
    assert report.candidates[0].primary_score == 100.0
    assert report.candidates[0].matched_primary == 1
    assert report.candidates[0].total_primary == 1
    assert report.candidates[0].assessments[0].evidence  # legacy literal fallback has no segment IDs


def test_compact_standalone_skill_lines_are_distinct_evidence():
    source = "Summary:\nDeveloped production services.\nSkills:\nPython\nNLP\nGCP\nPyTorch\n"
    skills = [s for s in segment_resume(source) if s.section == "skills"]
    assert [s.text for s in skills] == ["Python", "NLP", "GCP", "PyTorch"]
    assert len(set(s.segment_id for s in skills)) == 4


def test_bulleted_skill_rows_keep_original_lines():
    source = "Skills:\n- Python\n- NLP\n- PyTorch\n"
    skills = [s for s in segment_resume(source) if s.section == "skills"]
    assert [s.text for s in skills] == ["Python", "NLP", "PyTorch"]


def test_pdf_wrap_continues_labelled_skill_line():
    source = "Skills:\nAI/ML: TensorFlow, PyTorch, model\nevaluation\nProgramming: Python, C++\n"
    skills = [s.text for s in segment_resume(source)]
    assert "AI/ML: TensorFlow, PyTorch, model evaluation" in skills
    assert "Programming: Python, C++" in skills


def test_generic_prompt_guard_does_not_hardcode_benchmark_technology_pairs():
    from cv_ranker.assessor import SYSTEM_PROMPT, CORRECTION_PROMPT
    assert "Do not give transferable credit" in SYSTEM_PROMPT
    assert "Functional overlap is not equivalence" in CORRECTION_PROMPT
    assert "FastAPI is not Django" not in SYSTEM_PROMPT
    assert "PostgreSQL is not Redis" not in SYSTEM_PROMPT

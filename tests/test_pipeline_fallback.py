from pathlib import Path

from cv_ranker.config import Settings
from cv_ranker.documents import collect_resume_paths
from cv_ranker.pipeline import CVRanker


def test_full_pipeline_without_llm_backend_demo():
    root = Path(__file__).resolve().parents[1]
    jd = root / "sample_data" / "backend_jd.txt"
    resumes = collect_resume_paths([str(root / "sample_data" / "backend_resumes")])
    report = CVRanker(Settings(), use_llm=False).run(jd, resumes)
    assert len(report.requirements) >= 8
    assert len(report.candidates) == 4
    assert report.candidates[0].primary_score is not None
    assert report.candidates[0].primary_score >= report.candidates[-1].primary_score

"""Single-CV accuracy checkpoints on the original V4 engine, not V5."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cv_ranker.assessor import (
    _assess_batch, _direct_source_guard, _literal_initialism_guard, _validate_rows,
)
from cv_ranker.documents import extract_text
from cv_ranker.schemas import (
    CandidateResult, LLMAssessmentItem, LLMCandidateAssessmentResponse,
    RankingReport, ValidatedRequirement,
)
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.integration import run_shadow_retrieval
from cv_ranker.ui.evidence_inspection import literal_mentions, resume_segments, segment_ledger
from cv_ranker.ui_support import candidate_assessment_rows


ROOT = Path(__file__).resolve().parents[1]
SARA_PDF = ROOT / "sample_data/applied_ai_documents/pdf/03_sara_functional_transfer.pdf"


def requirement(name: str) -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id="R001", name=name, priority="required", jd_evidence=name
    )


def sara():
    content = extract_text(SARA_PDF)
    return content, segment_resume(content)


def test_sara_pdf_has_multiple_explicit_python_source_checkpoints():
    content, segments = sara()
    result = _direct_source_guard(requirement("Python"), content, segments)
    assert result.status == "matched"
    assert len(result.evidence_segments) >= 2
    assert all("Python" in item.text for item in result.evidence_segments)
    assert len(result.evidence_ids) == len(set(result.evidence_ids))


def test_sara_pdf_nlp_acronym_is_direct_not_absent():
    _, segments = sara()
    result = _literal_initialism_guard(requirement("Natural Language Processing"), segments)
    assert result is not None and result.status == "matched"
    assert result.matched_term == "NLP"
    assert len(result.evidence_segments) >= 2
    assert any(item.section == "skills" for item in result.evidence_segments)
    assert all("NLP" in item.text for item in result.evidence_segments)


def test_cv_mention_ledger_preserves_every_pdf_segment_and_source_line():
    _, segments = sara()
    round_trip = resume_segments(segment_ledger(segments))
    assert round_trip == segments
    assert all(item.source_lines for item in round_trip)
    nlp_hits = literal_mentions(requirement("Natural Language Processing"), round_trip)
    assert len(nlp_hits) >= 3
    assert any(item["Finding"] == "Explicit CV skill claim" for item in nlp_hits)
    assert any(item["Section"] == "experience" for item in nlp_hits)


def test_project_mention_visible_without_automatically_claiming_mastery():
    text = "Projects:\nOpen-source audit notes: Python, Redis, and Docker."
    hits = literal_mentions(requirement("Python"), segment_resume(text))
    assert hits
    assert hits[0]["Finding"] == "Name mentioned, but capability not established"


def test_negative_and_copied_sources_remain_visible_but_excluded():
    text = "Skills:\nCurrently learning Python\nRequired skills:\nPython"
    hits = literal_mentions(requirement("Python"), segment_resume(text))
    assert any("Qualified/learning" in item["Finding"] for item in hits)
    assert any("Excluded" in item["Finding"] for item in hits)
    assert not any(item["Finding"] == "Explicit CV skill claim" for item in hits)


def test_bad_python_model_citation_is_reanchored_to_real_python_source():
    content, segments = sara()
    other = next(item for item in segments if "Docker" in item.text and "Python" not in item.text)
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status="matched", evidence_ids=[other.segment_id],
        matched_term="Docker", reason="Docker proves Python",  # maliciously incorrect model rationale
    )])
    decisions, invalid, warnings, corrected = _validate_rows(
        response=response, requirements=[requirement("Python")],
        resume_text=content, segments=segments,
    )
    assert not invalid and corrected
    result = decisions["R001"]
    assert result.status == "matched"
    assert all("Python" in item.text for item in result.evidence_segments)
    assert "Docker proves Python" not in result.reason
    assert any("anchored" in warning for warning in warnings)


def test_llm_nlp_false_negative_recovered_with_cv_source_ids():
    class Model:
        settings = SimpleNamespace(exact_initialism_guard=True, second_look_unmatched=False)

        def invoke_structured(self, **kwargs):
            return LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
                requirement_id="R001", status="not_matched", evidence_ids=[],
                reason="NLP not found",
            )])

    content, _ = sara()
    decisions, mode, warnings = _assess_batch(
        resume_text=content, requirements=[requirement("Natural Language Processing")],
        llm=Model(),
    )
    assert decisions[0].status == "matched"
    assert all("NLP" in citation.text for citation in decisions[0].evidence_segments)
    assert "NLP not found" not in decisions[0].reason
    assert mode == "mixed"
    assert any("literal initialism" in warning for warning in warnings)


def test_primary_table_preview_contains_actual_named_term():
    content, segments = sara()
    assessment = _direct_source_guard(requirement("Python"), content, segments)
    report = RankingReport(
        job_description_source="one JD", jd_validation_mode="test", yake_candidates=[],
        requirements=[requirement("Python")],
        candidates=[CandidateResult(candidate_name="Sara", assessments=[assessment])],
    )
    row = candidate_assessment_rows(report, 0)[0]
    assert row["Result"] == "Matched"
    assert "Python" in row["Evidence"]


def test_shadow_retrieval_cannot_miss_explicit_nlp_due_to_top_k(tmp_path):
    class BlindEncoder:
        fingerprint = "uniform-v4-regression"

        def embed_documents(self, texts):
            return np.tile(np.array([1.0, 0.0], dtype=np.float32), (len(texts), 1))

        def embed_queries(self, texts):
            return self.embed_documents(texts)

    report = RankingReport(
        job_description_source="JD", jd_validation_mode="test", yake_candidates=[],
        requirements=[requirement("Natural Language Processing")],
        candidates=[CandidateResult(
            candidate_name="Sara", candidate_source=str(SARA_PDF),
            primary_score=100.0, evaluation_mode="mixed", rank=1,
        )],
    )
    retrieval = run_shadow_retrieval(
        report, cache_path=tmp_path / "blindretrieval.db", encoder=BlindEncoder(), top_k=1,
    )
    hits = retrieval["candidates"][0]["hits_by_requirement"]["R001"]
    assert len(hits) > 1  # the ordinary vector top_k=1 cannot erase literal NLP hits
    assert any("NLP" in hit["original_text"] for hit in hits)
    assert any(hit["literal_source_inclusion"] for hit in hits)
    for hit in hits:
        if hit["literal_source_inclusion"]:
            assert hit["cosine_similarity"] is None  # no made-up similarity score


def test_v4_ui_keeps_separate_segment_inspection_tab():
    source = (ROOT / "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    assert "03  CV source segments" in source
    assert "segment_ledger(" in source
    assert "Evidence segment {n}" in source
    assert "Why this segment matters:" in source
    assert "AI evidence checkpoint {checkpoint}" in source

"""Domain-neutral R008 and supervisor-visible explanation regression checks."""

import json
from pathlib import Path
from types import SimpleNamespace

from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.unified import UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse


def test_model_evaluation_from_bilal_pdf_is_valid_source_grounded_found(tmp_path):
    """The example CV performs evaluation even without the exact skill label."""
    pdf = (Path(__file__).resolve().parents[1] / "sample_data" /
           "applied_ai_documents" / "pdf" / "02_bilal_direct_fullstack.pdf")
    resume_text = extract_text(pdf)
    segments = segment_resume(resume_text)
    qualifying = next(segment for segment in segments
                      if "held-out evaluation" in segment.text.casefold()
                      or "tracked retrieval recall" in segment.text.casefold())
    requirement = ValidatedRequirement(requirement_id="R008", name="Model evaluation",
                                        priority="required", jd_evidence="Model evaluation")

    class ConfirmedLLM:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.calls += 1
            payload = json.loads(user_prompt)
            assert [r["id"] for r in payload["requirements"]] == ["R008"]
            assert qualifying.segment_id in [source["id"] for source in payload["sources"]]
            return UnifiedResponse(assessments=[UnifiedItem(
                requirement_id="R008", decision="found", relation="entailed",
                evidence_ids=[qualifying.segment_id],
                # Optional source highlight is inaccurate, but the independent
                # performed-action source and semantic relationship are valid.
                matched_term="Model evaluation",
                reason="Prepared held-out evaluation sets and tracked model quality metrics.")])

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = ConfirmedLLM()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=qualifying.segment_id))]})
    try:
        assessments, metrics = engine.assess(
            [requirement], segments, resume_text, candidate_id="bilal_pdf_offline")
    finally:
        # The isolated test engine has no embedding-cache connection.
        pass
    assert assessments[0].assessment_state == "verified"
    assert assessments[0].unified_status == "Found"
    assert qualifying.segment_id in assessments[0].evidence_ids
    assert metrics.unresolved_criteria == 0


def test_all_steps_are_prominent_and_in_order_and_status_is_visible():
    source = (Path(__file__).resolve().parents[1] /
              "cv_ranker" / "ui" / "dashboard.py").read_text(encoding="utf-8")
    for index, phrase in enumerate((
        "Step 1 · Upload documents", "Step 2 · Extract JD requirements",
        "Step 3 · Review extracted JD requirements",
        "Step 4 · Category weightage",
        "Step 5 · Edit individual JD allocations",
        "Step 6 · Assess candidates against the approved JD",
    ), 1):
        # V4.9.40 renders its numbered headings as accessible, coordinated
        # section cards instead of bare Markdown H4s.
        assert source.count('_section_title("' + phrase + '"') == 1, (
            f"Step {index} not a visible section heading")
    assert '<h3 class="cv-section-heading">' in source
    assert 'st.status("Assessing candidates in the background", state="running"' in source
    assert 'st.status("Recovering unfinished CV assessments", state="running"' in source


def test_supervisor_rank_explanations_omit_internal_source_ids():
    from cv_ranker.ranking_reasoning import _fallback_reason, _reader_reason

    result = _reader_reason("Verified by segment S008 and source S012.")
    assert "S008" not in result and "S012" not in result
    fallback = _fallback_reason("Model evaluation", "Found", ["S001"])
    assert "S001" not in fallback

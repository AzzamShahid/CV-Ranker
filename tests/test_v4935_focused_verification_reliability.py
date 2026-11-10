"""Regression coverage for repeated model/source validation failures.

The examples use a real bundled PDF and fake model replies: no remote CV
transmission, API key or cloud budget is required.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.llm import ModelStructuredResponseError, StructuredLLM
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.unified import (_independently_adjudicate, _proof_excerpt_in_source,
                               UnifiedEvidenceEngine,
                               UnifiedItem, UnifiedResponse)


def _bilal():
    path = (Path(__file__).resolve().parents[1] / "sample_data" /
            "applied_ai_documents" / "pdf" / "02_bilal_direct_fullstack.pdf")
    text = extract_text(path)
    segments = segment_resume(text)
    candidate_segment = next(s for s in segments if "held-out evaluation sets" in s.text.casefold())
    requirement = ValidatedRequirement(requirement_id="R008", name="Model evaluation",
                                       priority="required", jd_evidence="Model evaluation")
    return text, segments, candidate_segment, requirement


def _independent_reply(source_id: str, proof: str):
    return {"R008": {"decision": "found", "relation": "entailed",
                     "evidence_ids": [source_id], "proof_excerpt": proof,
                     "reason": "The candidate prepared held-out tests and tracked evaluation results."}}


def test_independent_accepts_same_exact_words_when_pdf_punctuation_differs():
    _, segments, source, req = _bilal()

    class Reply:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate(_independent_reply(
                source.segment_id,
                "Prepared held out evaluation sets tracked retrieval recall 5"))

    checked, proposed, rejected = _independently_adjudicate(
        Reply(), [req], "{}", {source.segment_id},
        {s.segment_id: s for s in segments})
    assert not rejected
    assert proposed["R008"].decision == "found"
    assert checked.assessments[0].evidence_ids == [source.segment_id]


def test_independent_rejects_fabricated_quote_with_no_original_source_overlap():
    _, segments, source, req = _bilal()

    class Reply:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate(_independent_reply(
                source.segment_id, "candidate built a spacecraft launch system"))

    reasons = {}
    discarded = []
    checked, proposal, rejected = _independently_adjudicate(
        Reply(), [req], "{}", {source.segment_id},
        {s.segment_id: s for s in segments}, rejection_reasons=reasons,
        normalization_notices=discarded)
    assert rejected == {"R008"}
    assert not checked.assessments and not proposal
    assert "no substantial overlap" in reasons["R008"]
    assert not discarded


def test_excerpt_normalization_does_not_accept_loosely_related_keywords():
    original = "Conducted an evaluation of validation metrics for product quality."
    assert not _proof_excerpt_in_source("validation evaluation product quality", original)
    assert not _proof_excerpt_in_source("invented completed training deployment", original)


def test_unverified_r008_is_recovered_by_a_valid_focused_final_judgment():
    text, segments, source, req = _bilal()

    class LLM:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.calls += 1
            if self.calls <= 2:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R008", decision="uncertain", relation="uncertain",
                    evidence_ids=[], reason="Unable to reach a verdict for this row")])
            return schema.model_validate(_independent_reply(
                source.segment_id,
                "Prepared held out evaluation sets tracked retrieval recall 5"))

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = LLM()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=source.segment_id))]})

    assessments, metrics = engine.assess([req], segments, text, candidate_id="bilal")
    assert engine.llm.calls == 3
    assert assessments[0].assessment_state == "verified"
    assert assessments[0].unified_status == "Found"
    assert metrics.unresolved_ids == []


def test_fabricated_final_excerpt_still_withholds_credit_and_explains_why():
    text, segments, source, req = _bilal()

    class LLM:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, schema, **_):
            self.calls += 1
            if self.calls <= 2:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R008", decision="uncertain", relation="uncertain",
                    evidence_ids=[], reason="Unable to reach a verdict for this row")])
            return schema.model_validate(_independent_reply(
                source.segment_id, "invented completed training deployment"))

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = LLM()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=source.segment_id))]})
    assessments, metrics = engine.assess([req], segments, text, candidate_id="bilal")

    assert engine.llm.calls == 3
    assert assessments[0].assessment_state == "unverified"
    assert metrics.unresolved_ids == ["R008"]
    assert any("no substantial overlap" in note for note in metrics.warnings)


def test_final_model_schema_failure_has_requirement_specific_diagnostic():
    text, segments, source, req = _bilal()

    class LLM:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, **_):
            self.calls += 1
            if self.calls <= 2:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R008", decision="uncertain", relation="uncertain",
                    evidence_ids=[], reason="Cannot decide without a valid source citation")])
            raise ModelStructuredResponseError("model reply was not valid JSON")

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = LLM()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=source.segment_id))]})
    assessments, metrics = engine.assess([req], segments, text, candidate_id="bilal")

    assert assessments[0].assessment_state == "unverified"
    assert any(note.startswith("R008: final independent verification could not complete:")
               and "structured JSON" in note for note in metrics.warnings)


def test_cloud_schema_failure_changes_response_mode_instead_of_identical_retry(monkeypatch):
    from pydantic import BaseModel, ConfigDict

    class Reply(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        ok: bool

    settings = Settings(llm_provider="openrouter", openrouter_api_key="fake-key",
                        llm_retries=1)
    llm = StructuredLLM(settings)
    modes = []

    def fake_post(payload):
        modes.append(payload["response_format"]["type"])
        content = '{"ok": "incorrect_type"}' if len(modes) == 1 else '{"ok": true}'
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}

    monkeypatch.setattr(llm, "_post_chat", fake_post)
    assert llm.invoke_structured(system_prompt="Return JSON", user_prompt="Hi", schema=Reply).ok
    assert modes == ["json_schema", "json_object"]

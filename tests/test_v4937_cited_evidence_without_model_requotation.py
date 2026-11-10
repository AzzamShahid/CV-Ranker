"""The original segment IDs, not LLM-written quotation metadata, are proof.

Regression for an R008 result repeatedly withheld although the bundled CV
contained a source-attested skill entry and a completed LLM-integrated service.
"""

from pathlib import Path
from types import SimpleNamespace

from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import segment_resume
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse,
                               _independently_adjudicate)


def _bilal_integration():
    path = Path(__file__).resolve().parents[1] / "sample_data" / "applied_ai_documents" / "pdf" / "02_bilal_direct_fullstack.pdf"
    text = extract_text(path)
    segments = segment_resume(text)
    skills = next(s for s in segments if "hosted LLM API integrations" in s.text)
    work = next(s for s in segments if "Architected an LLM-enabled" in s.text)
    req = ValidatedRequirement(requirement_id="R008", name="LLM integrations",
                               priority="required", jd_evidence="LLM integrations")
    return text, segments, skills, work, req


def test_repeated_incorrect_highlight_and_paraphrased_final_quote_no_longer_withhold():
    text, segments, skills, work, req = _bilal_integration()

    class Model:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, schema, **_):
            self.calls += 1
            if self.calls == 1:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R008", decision="found", relation="direct",
                    evidence_ids=[skills.segment_id, work.segment_id],
                    matched_term="LLM integrations",  # not a verbatim CV phrase
                    reason="Reported hosted LLM API integrations and built an LLM-enabled service.")])
            return schema.model_validate({"R008": {
                "decision": "found", "relation": "entailed",
                "evidence_ids": [skills.segment_id, work.segment_id],
                # Semantically correct but NOT copied verbatim from either CV segment.
                "proof_excerpt": "Integrated hosted LLM APIs into a document review application",
                "reason": "Architected an LLM-enabled document review service and listed hosted LLM API integrations.",
            }})

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = Model()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=sid))
                 for sid in (skills.segment_id, work.segment_id)]})
    rows, metrics = engine.assess([req], segments, text, candidate_id="bilal")
    assert engine.llm.calls == 2
    assert metrics.correction_calls == 0
    assert metrics.final_verification_calls == 1
    assert metrics.unresolved_ids == []
    assert rows[0].assessment_state == "verified"
    assert rows[0].unified_status == "Found"
    assert set(rows[0].evidence_ids) == {skills.segment_id, work.segment_id}
    assert all(any(source.segment_id == original.segment_id and
                       source.text == original.text for original in segments)
               for source in rows[0].evidence_segments)
    assert "Integrated hosted LLM APIs into a document review application" not in rows[0].evidence
    assert any("ignored non-verbatim model quotation" in msg
               for msg in metrics.resolved_validation_notices)


def test_independent_rejects_fabricated_or_out_of_scope_segment_id_even_with_good_reason():
    _, segments, skills, work, req = _bilal_integration()

    class Model:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate({"R008": {
                "decision": "found", "relation": "entailed",
                "evidence_ids": ["S999"], "proof_excerpt": "hosted LLM API integrations",
                "reason": "The candidate reports hosted LLM API integrations.",
            }})

    checked, proposals, invalid = _independently_adjudicate(
        Model(), [req], "{}", {skills.segment_id, work.segment_id},
        {source.segment_id: source for source in segments})
    assert invalid == {"R008"}
    assert not checked.assessments and not proposals


def test_independent_rejects_contradictory_decision_relation_even_when_cited():
    _, segments, skills, work, req = _bilal_integration()

    class Model:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate({"R008": {
                "decision": "found", "relation": "overlap",
                "evidence_ids": [skills.segment_id], "proof_excerpt": None,
                "reason": "The candidate reports hosted LLM API integrations.",
            }})

    checked, proposals, invalid = _independently_adjudicate(
        Model(), [req], "{}", {skills.segment_id, work.segment_id},
        {source.segment_id: source for source in segments})
    assert invalid == {"R008"}
    assert not checked.assessments and not proposals


def test_final_review_needs_no_model_written_quote_when_original_citation_exists():
    _, segments, skills, work, req = _bilal_integration()

    class Model:
        def invoke_structured(self, *, schema, **_):
            return schema.model_validate({"R008": {
                "decision": "found", "relation": "direct",
                "evidence_ids": [skills.segment_id], "proof_excerpt": None,
                "reason": "The skills section reports hosted LLM API integrations.",
            }})

    checked, proposals, invalid = _independently_adjudicate(
        Model(), [req], "{}", {skills.segment_id, work.segment_id},
        {source.segment_id: source for source in segments})
    assert not invalid
    assert checked.assessments[0].evidence_ids == [skills.segment_id]
    assert proposals["R008"].decision == "found"


def test_failed_independent_source_validation_still_withholds_credit():
    text, segments, skills, work, req = _bilal_integration()

    class Model:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, schema, **_):
            self.calls += 1
            if self.calls == 1:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R008", decision="found", relation="direct",
                    evidence_ids=[skills.segment_id],
                    matched_term="LLM integrations", reason="Reported integrations.")])
            return schema.model_validate({"R008": {
                "decision": "found", "relation": "direct",
                "evidence_ids": ["S999"], "proof_excerpt": None,
                "reason": "The candidate reports hosted LLM API integrations.",
            }})

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = Model()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R008": [SimpleNamespace(source=SimpleNamespace(segment_id=skills.segment_id))]})
    rows, metrics = engine.assess([req], segments, text, candidate_id="bilal")
    assert engine.llm.calls == 2
    assert rows[0].assessment_state == "unverified"
    assert rows[0].unified_status == "Unverified"
    assert metrics.unresolved_ids == ["R008"]
    assert any("cited source was not among" in warning for warning in metrics.warnings)

"""Cross-domain checks for first-pass transferable/skill-scope contradictions.

No profession-specific dictionary grants Found. An independent source-grounded
verdict must still establish exact satisfaction; unrelated tool experience,
intentions and extra JD conditions are negative controls.
"""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (UnifiedEvidenceEngine,
                               _needs_independent_overlap_review)


def requirement(name, kind="skill"):
    return ValidatedRequirement(
        requirement_id="R001", name=name, jd_evidence=name, priority="preferred",
        constraint=RequirementConstraint(kind=kind, operator="single",
                                         origin="source_rules"),
    )


def first_row(source, reason):
    return RequirementAssessment(
        requirement_id="R001", status="not_matched",
        unified_status="Transferable", reason=reason,
        evidence_ids=[source.segment_id],
        evidence_segments=[EvidenceCitation(
            segment_id=source.segment_id, section=source.section, text=source.text)],
    )


@pytest.mark.parametrize("name, source_text, reason", [
    (
        "Medical imaging",
        "Designed a medical-image triage research pilot on public data.",
        "The candidate has experience with medical imaging research pilots. "
        "While not performed in a production setting, the work is substantially related.",
    ),
    (
        "Inventory control",
        "Designed inventory control and stock reconciliation research workflows.",
        "The candidate designed inventory control research workflows but lacks "
        "large-scale commercial deployment.",
    ),
    (
        "Payroll reconciliation",
        "Performed payroll reconciliation in a completed departmental pilot.",
        "The candidate performed payroll reconciliation in a departmental pilot, "
        "but lacks enterprise-scale deployment.",
    ),
])
def test_completed_work_with_affirmed_named_skill_requires_scope_review(name, source_text, reason):
    source = ResumeSegment("S001", "projects", source_text)
    assert _needs_independent_overlap_review(
        requirement(name), first_row(source, reason), {"S001": source}, source_text)


def test_other_tool_is_not_misidentified_as_the_named_skill():
    source = ResumeSegment("S001", "projects",
                           "Built LLM pipelines with Haystack; never used LangChain.")
    reason = ("The candidate has experience building LLM pipelines with Haystack "
              "that may transfer to LangChain, but has not used LangChain.")
    assert not _needs_independent_overlap_review(
        requirement("LangChain"), first_row(source, reason), {"S001": source}, source.text)


def test_learning_intention_cannot_trigger_skill_scope_recheck():
    source = ResumeSegment("S001", "projects",
                           "Plans to learn inventory control next year.")
    reason = "The candidate has experience with inventory control pilots."
    assert not _needs_independent_overlap_review(
        requirement("Inventory control"), first_row(source, reason),
        {"S001": source}, source.text)


def test_more_specific_non_skill_requirement_does_not_get_skill_review():
    source = ResumeSegment("S001", "projects",
                           "Designed an imaging prototype for public research data.")
    reason = "The candidate designed a medical imaging prototype, not a clinical deployment."
    assert not _needs_independent_overlap_review(
        requirement("Clinical medical imaging deployment", kind="responsibility"),
        first_row(source, reason), {"S001": source}, source.text)


class FlatEncoder:
    fingerprint = "v4915-scope-consistency"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class TwoPassProvider:
    disabled_reason = None

    def __init__(self, *, first_reason, final_decision="found"):
        self.settings = Settings(llm_provider="ollama")
        self.first_reason = first_reason
        self.final_decision = final_decision
        self.calls = 0
        self.independent_source = None

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        payload = json.loads(user_prompt)
        source = payload["sources"][0]
        if "second, independent" in system_prompt:
            self.independent_source = source
            assert "frozen JD" in payload["task"]
            return schema.model_validate({"R001": {
                "decision": self.final_decision,
                "relation": "entailed" if self.final_decision == "found" else "overlap",
                "evidence_ids": [source["id"]],
                "proof_excerpt": source["text"][:40],
                "reason": ("Completed named-skill work directly establishes the skill."
                           if self.final_decision == "found" else
                           "Completed work overlaps but the requested named tool is absent."),
            }})
        return schema.model_validate({"R001": {
            "decision": "transferable", "relation": "overlap",
            "evidence_ids": [source["id"]],
            "matched_term": None, "reason": self.first_reason,
        }})


def test_independent_verdict_can_correct_skill_scope_and_preserve_proof(tmp_path):
    provider = TwoPassProvider(first_reason=(
        "The candidate has experience with inventory control research workflows "
        "but not in enterprise-scale production."))
    source = ResumeSegment("S001", "projects",
                           "Designed stock reconciliation and item tracking workflows "
                           "for a completed warehouse pilot.")
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=4,
                               cache_path=tmp_path / "semantic.sqlite") as engine:
        rows, metrics = engine.assess([requirement("Inventory control")],
                                      [source], source.text, candidate_id="inventory")
    assert provider.calls == 2, (rows, metrics.public())
    assert metrics.final_verification_calls == 1
    assert provider.independent_source["text"] == source.text
    assert rows[0].status == "matched"
    assert rows[0].unified_status == "Found"
    assert rows[0].evidence_ids == ["S001"]


def test_independent_overlap_cannot_be_promoted_to_found(tmp_path):
    provider = TwoPassProvider(
        first_reason="The candidate performed stock audit, which is related to inventory control.",
        final_decision="transferable")
    source = ResumeSegment("S001", "projects",
                           "Performed stock audits during a logistics pilot.")
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=4,
                               cache_path=tmp_path / "semantic.sqlite") as engine:
        rows, metrics = engine.assess([requirement("Inventory control")],
                                      [source], source.text, candidate_id="stock-audit")
    assert provider.calls == 1, (rows, metrics.public())
    assert metrics.final_verification_calls == 0
    assert rows[0].unified_status == "Transferable"
    assert rows[0].status != "matched"

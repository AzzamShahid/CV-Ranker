"""Skill-list claims, frozen JD scope, and visible rejected-source citations.

Names and tools here are synthetic test inputs, never matching dictionaries.
The independent model owns all nonliteral semantic-equivalence judgments.
"""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.schemas import RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (
    UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse, _skill_inventory_recall_leads,
    _independently_adjudicate, _map_response, _keyed_response_schema,
)


def req(name, *, jd=None):
    return ValidatedRequirement(
        requirement_id="R001", name=name, jd_evidence=jd or name,
        priority="preferred", constraint=RequirementConstraint(
            kind="skill", operator="single", origin="source_rules"))


@pytest.mark.parametrize("name,source", [
    ("Google Cloud", "GCP Cloud Run, BigQuery, Docker"),
    ("Inventory control", "Inventory counts, WMS scanner, Excel"),
    ("Data analysis", "Data profiling, dashboards, reporting"),
    ("Medical imaging", "Medical-image segmentation, Python"),
])
def test_positive_related_skill_entries_recalled_without_domain_dictionary(name, source):
    segments = {"S099": ResumeSegment("S099", "skills", source)}
    assert _skill_inventory_recall_leads(req(name), segments) == ["S099"]


@pytest.mark.parametrize("source", [
    "Never used Cloud Run", "Plans to learn Cloud Run next year",
    "No experience with Cloud Run", "Currently studying Cloud Run",
    "Not familiar with Cloud Run",
])
def test_negative_or_learning_entry_cannot_become_positive_skill_lead(source):
    segments = {"S011": ResumeSegment("S011", "skills", source)}
    assert _skill_inventory_recall_leads(req("Cloud Run"), segments) == []


def test_explicit_professional_jd_not_reduced_to_skills_listing():
    segments = {"S011": ResumeSegment("S011", "skills", "Google Cloud")}
    assert _skill_inventory_recall_leads(
        req("Google Cloud", jd="Professional experience using Google Cloud"),
        segments) == []


class FlatEncoder:
    fingerprint = "v4918-skill-claim-source-contract"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class SkillClaimProvider:
    disabled_reason = None

    def __init__(self, *, confirmed=True):
        self.settings = Settings(llm_provider="ollama")
        self.confirmed = confirmed
        self.calls = 0
        self.first_source_ids = []
        self.review_source_ids = []

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        sources = json.loads(user_prompt)["sources"]
        ids = [source["id"] for source in sources]
        if "second, independent" in system_prompt:
            self.review_source_ids = ids
            if self.confirmed:
                return schema.model_validate({"R001": {
                    "decision": "found", "relation": "entailed",
                    "evidence_ids": ["S099"], "proof_excerpt": "GCP Cloud Run",
                    "reason": "The CV positively reports a service of the requested cloud platform.",
                }})
            return schema.model_validate({"R001": {
                "decision": "not_found", "relation": "absent",
                "evidence_ids": ["S099"], "proof_excerpt": None,
                "reason": "The cited item is a different named capability, not the requested skill.",
            }})
        self.first_source_ids = ids
        return schema.model_validate({"R001": {
            "decision": "not_found", "relation": "absent",
            "evidence_ids": ["S099"] if "S099" in ids else [],
            "reason": "The named skill is not explicitly present in work experience.",
        }})


@pytest.mark.parametrize("confirmed,final", [(True, "Found"), (False, "Not Found")])
def test_gcp_listed_service_visible_before_model_decides_without_project_use(
        confirmed, final, tmp_path):
    provider = SkillClaimProvider(confirmed=confirmed)
    # Misleading embeddings: the relevant skills entry is after numerous
    # low-information sources, outside the retriever's initial top 2.
    segments = [ResumeSegment(f"S{i:03d}", "experience",
                              f"Operated an unrelated workflow stage {i}")
                for i in range(1, 13)]
    segments.append(ResumeSegment("S099", "skills", "GCP Cloud Run, BigQuery, Docker"))
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=2,
                               cache_path=tmp_path / "skill_inventory.sqlite") as engine:
        rows, metrics = engine.assess([req("Google Cloud")], segments,
                                      "\n".join(s.text for s in segments),
                                      candidate_id=f"semantic-listed-{confirmed}")
    assert provider.calls == 2
    assert "S099" in provider.first_source_ids
    assert "S099" in provider.review_source_ids
    assert rows[0].unified_status == final
    assert rows[0].evidence_ids == ["S099"]
    assert rows[0].evidence_segments[0].text == "GCP Cloud Run, BigQuery, Docker"
    assert metrics.final_verification_calls == 1
    assert (rows[0].status == "matched") == confirmed


def test_first_pass_schema_allows_original_checked_source_on_not_found():
    schema = _keyed_response_schema(("R001",), strict_relation=True)
    parsed = schema.model_validate({"R001": {
        "decision": "not_found", "relation": "absent",
        "evidence_ids": ["S011"], "matched_term": None,
        "reason": "Considered a relevant source but it establishes a different product.",
    }})
    converted, proposals, invalid = _map_response(
        UnifiedResponse(assessments=[UnifiedItem(
            requirement_id="R001", **parsed.R001.model_dump())]),
        [req("Cloud Run")], {"S011"})
    assert not invalid
    assert converted.assessments[0].status == "not_matched"
    assert converted.assessments[0].evidence_ids == ["S011"]
    assert proposals["R001"].decision == "not_found"


def test_supervisor_shows_original_checkpoint_even_when_not_credited():
    from cv_ranker.schemas import (CandidateResult, EvidenceCitation,
                                   RankingReport, RequirementAssessment)
    from cv_ranker.ui.unified_decisions import reconcile_unified_candidate

    report = RankingReport(
        job_description_source="JD", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[req("Google Cloud")],
        candidates=[CandidateResult(
            candidate_name="Candidate", assessments=[RequirementAssessment(
                requirement_id="R001", status="not_matched",
                unified_status="Not Found", evidence_ids=["S011"],
                evidence_segments=[EvidenceCitation(
                    segment_id="S011", section="skills",
                    text="GCP Cloud Run, BigQuery, Docker")],
                reason="The cited item was inspected but not accepted as the named skill.")])])
    ledger = [{"segment_id": "S011", "section": "skills",
               "text": "GCP Cloud Run, BigQuery, Docker", "source_lines": []}]
    result = reconcile_unified_candidate(report, 0, ledger)
    row = result["Criteria"][0]
    assert row["Result"] == "Not Found"
    assert result["Preferred matched"] == 0
    assert row["Total checkpoints considered"] == 1
    assert row["Checkpoints"][0]["Validated against CV"]
    assert "reviewed but not credited" in row["Checkpoints"][0]["Sources"][0]


@pytest.mark.parametrize("denial", [
    "Never used GCP Cloud Run.",
    "No professional use of GCP Cloud Run.",
    "No experience with GCP Cloud Run.",
])
def test_llm_cannot_override_original_negated_semantic_skill_with_false_found(denial):
    from cv_ranker.assessor import _validate_rows
    from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse

    validated, invalid, _, _ = _validate_rows(
        response=LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
            requirement_id="R001", status="matched", evidence_ids=["S011"],
            reason="The candidate reports the named platform skill.")]),
        requirements=[req("Google Cloud")], resume_text=denial,
        segments=[ResumeSegment("S011", "skills", denial)],
        semantic_grounded=True,
    )
    assert not invalid
    assert validated["R001"].status != "matched"

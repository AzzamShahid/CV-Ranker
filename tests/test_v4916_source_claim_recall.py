"""A model's unsupported experience threshold must not erase skills-list evidence.

This is a cross-domain, source-grounded *recall* path, not a Python synonym
dictionary and not an automatic score recovery.
"""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.schemas import RequirementAssessment, RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.unified import (UnifiedEvidenceEngine,
                               _needs_independent_overlap_review,
                               _reason_admitted_skill_claim_sources)


def requirement(name):
    return ValidatedRequirement(
        requirement_id="R001", name=name, jd_evidence=name, priority="preferred",
        constraint=RequirementConstraint(kind="skill", operator="single",
                                         origin="source_rules"))


def negative(reason):
    return RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason=reason)


@pytest.mark.parametrize("jd,claim,reason", [
    ("Google Cloud", "GCP Cloud Run, BigQuery, Docker",
     "The CV does not mention Google Cloud. While GCP Cloud Run is listed under "
     "skills, it is not stated as used in a professional project."),
    ("Inventory management", "WMS scanner, Excel, stock tracking",
     "WMS scanner is listed under technical skills, but no warehouse "
     "management project is described."),
    ("Database development", "PostgreSQL, Excel, Power BI",
     "PostgreSQL appears in the skills section, yet it is not demonstrated "
     "in the work-history section."),
])
def test_model_admitted_source_claim_is_recalled_without_equivalence_assumption(jd, claim, reason):
    source = ResumeSegment("S009", "skills", claim)
    row = negative(reason)
    original = {source.segment_id: source}
    assert _reason_admitted_skill_claim_sources(row, original) == ["S009"]
    assert _needs_independent_overlap_review(requirement(jd), row, original, claim)


@pytest.mark.parametrize("claim,reason", [
    ("Plans to learn Cloud Run next year",
     "Cloud Run is listed under skills, but no experience is described."),
    ("Never used Cloud Run professionally",
     "Cloud Run is listed under skills, but experience is missing."),
    ("Python, Docker",
     "Cloud Run is listed under skills, but experience is missing."),
    ("Cloud Run, Docker",
     "No Cloud Run skills are listed or mentioned in this CV."),
])
def test_no_unearned_recall_without_an_original_positive_admitted_claim(claim, reason):
    source = ResumeSegment("S009", "skills", claim)
    assert not _reason_admitted_skill_claim_sources(negative(reason), {"S009": source})


class FlatEncoder:
    fingerprint = "v4916-claim-recall"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class ReviewProvider:
    disabled_reason = None

    def __init__(self, final_decision="found"):
        self.settings = Settings(llm_provider="ollama")
        self.final_decision = final_decision
        self.calls = 0
        self.review_source = None

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        payload = json.loads(user_prompt)
        if "second, independent" in system_prompt:
            source = payload["sources"][0]
            self.review_source = source
            return schema.model_validate({"R001": {
                "decision": self.final_decision,
                "relation": ("direct" if self.final_decision == "found" else "absent"),
                "evidence_ids": ([source["id"]] if self.final_decision == "found" else []),
                "proof_excerpt": (source["text"][:20] if self.final_decision == "found" else None),
                "reason": ("The reported platform service belongs to the requested "
                           "cloud platform and is a positive CV skill claim."
                           if self.final_decision == "found" else
                           "The cited technology does not establish the named skill."),
            }})
        return schema.model_validate({"R001": {
            "decision": "not_found", "relation": "absent", "evidence_ids": [],
            "reason": ("Google Cloud is not named explicitly. While GCP Cloud Run "
                       "is listed under skills, no experience project uses it."),
        }})


@pytest.mark.parametrize("verdict,expected", [
    ("found", "Found"), ("not_found", "Not Found"),
])
def test_semantic_review_decides_admitted_skill_claim_not_python(verdict, expected, tmp_path):
    provider = ReviewProvider(final_decision=verdict)
    source = ResumeSegment("S009", "skills", "GCP Cloud Run, BigQuery, Docker")
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=4,
                               cache_path=tmp_path / "semantic.sqlite") as engine:
        rows, metrics = engine.assess([requirement("Google Cloud")],
                                      [source], source.text, candidate_id="skill-claim")
    assert provider.calls == 2, (rows, metrics.public())
    assert metrics.final_verification_calls == 1
    assert provider.review_source["id"] == "S009"
    assert rows[0].unified_status == expected
    assert (rows[0].status == "matched") == (verdict == "found")
    if verdict == "found":
        assert rows[0].evidence_ids == ["S009"]
    else:
        # V4.9.19 keeps noncreditable original source checkpoints visible on
        # Not Found even if the independent model omitted negative citations.
        assert rows[0].evidence_ids == ["S009"]
        assert rows[0].review_checkpoint_origin == "retrieval"
        assert "model omitted" not in rows[0].reason


def test_sara_pdf_keeps_the_original_positive_cloud_claim():
    from pathlib import Path
    path = (Path(__file__).resolve().parents[1] /
            "sample_data/applied_ai_documents/pdf/03_sara_functional_transfer.pdf")
    originals = {seg.segment_id: seg for seg in segment_resume(extract_text(path))}
    leads = _reason_admitted_skill_claim_sources(negative(
        "GCP Cloud Run is listed under skills, but not explicitly used in experience."),
        originals)
    assert len(leads) == 1
    assert "GCP Cloud Run" in originals[leads[0]].text

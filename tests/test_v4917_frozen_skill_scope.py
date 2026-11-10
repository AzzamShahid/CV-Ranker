"""Frozen-JD evidence standards are enforced after every semantic verdict.

Candidate-specific names in these fixtures are NOT production matching rules.
Only literal source claims may be recovered deterministically; any semantic
equivalence still requires the independently cited model judgment.
"""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.criteria_scope import ordinary_named_skill, unstated_work_objection
from cv_ranker.schemas import RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem,
                               _enforce_frozen_skill_scope, _final_unified_row)
from cv_ranker.schemas import RequirementAssessment


def req(name, *, kind="skill", jd=None):
    return ValidatedRequirement(
        requirement_id="R001", name=name, jd_evidence=jd or name,
        priority="preferred", constraint=RequirementConstraint(
            kind=kind, operator="single", origin="source_rules"))


@pytest.mark.parametrize("name", [
    "Medical imaging", "Inventory control", "Python", "Production Planning",
    "Google Cloud", "Financial forecasting",
])
def test_bare_named_skill_uses_reported_claim_evidence_standard(name):
    assert ordinary_named_skill(req(name))


@pytest.mark.parametrize("name,jd,kind", [
    ("Python", "Minimum 3 years professional experience with Python", "skill"),
    ("Experience with Python", "Experience with Python", "skill"),
    ("Google Cloud", "Hands-on experience with Google Cloud", "skill"),
    ("Clinical deployment", "Clinical deployment", "responsibility"),
    ("3 years of payroll experience", "3 years of payroll experience", "skill"),
])
def test_explicit_jd_work_conditions_cannot_be_downgraded(name, jd, kind):
    assert not ordinary_named_skill(req(name, jd=jd, kind=kind))


@pytest.mark.parametrize("reason", [
    "GCP Cloud Run is listed in skills but not demonstrated in professional experience.",
    "It is not explicitly shown in the experience section.",
    "The skill lacks production deployment in a commercial role.",
    "There is no hands-on project experience documented for this skill.",
])
def test_unsupported_professional_use_objections_are_not_valid_for_plain_skills(reason):
    assert unstated_work_objection(req("Google Cloud"), reason)
    assert not unstated_work_objection(
        req("Google Cloud", jd="Professional experience using Google Cloud"), reason)


def test_no_false_scope_objection_for_compliant_reason():
    assert not unstated_work_objection(
        req("Inventory control"),
        "Professional experience is not required; no skill is claimed in the CV.")


def test_exact_affirmative_skill_can_be_recovered_without_model_extra_threshold():
    requirement = req("Python")
    source = ResumeSegment("S003", "skills", "Python, FastAPI, PostgreSQL")
    initial = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason="Python is not demonstrated in professional experience.")
    proposal = UnifiedItem(requirement_id="R001", decision="not_found",
                           relation="absent", reason=initial.reason)
    row = _final_unified_row(initial, proposal, requirement, {"S003": source})
    assert row.status == "matched" and row.unified_status == "Found"
    assert row.evidence_ids == ["S003"]
    assert "applicant-reported" in row.reason


def test_negated_and_learning_named_skills_are_not_recovered():
    requirement = req("Python")
    initial = RequirementAssessment(requirement_id="R001", status="not_matched",
                                    unified_status="Not Found", reason="No Python experience.")
    proposal = UnifiedItem(requirement_id="R001", decision="not_found",
                           relation="absent", reason=initial.reason)
    for text in ("Never used Python.", "Plans to learn Python next year."):
        source = ResumeSegment("S003", "skills", text)
        row = _final_unified_row(initial, proposal, requirement, {"S003": source})
        assert row.status != "matched"
        assert row.unified_status != "Found"


def test_admitted_but_semantically_ambiguous_claim_is_unverified_not_wrongly_rejected():
    requirement = req("Google Cloud")
    source = ResumeSegment("S011", "skills", "GCP Cloud Run, BigQuery, Docker")
    row = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason="GCP Cloud Run is listed under skills, but not demonstrated in professional experience.")
    audited = _enforce_frozen_skill_scope(requirement, row, {"S011": source})
    assert audited.unified_status == "Unverified"
    assert audited.assessment_state == "unverified"
    assert audited.evidence_ids == ["S011"]
    assert audited.review_recommended
    assert "review leads" in audited.reason


def test_unsupported_reason_with_no_actual_positive_claim_keeps_not_found():
    requirement = req("Medical imaging")
    source = ResumeSegment("S011", "skills", "Python, Docker")
    row = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason="Medical imaging is not demonstrated in professional experience.")
    audited = _enforce_frozen_skill_scope(requirement, row, {"S011": source})
    assert audited.unified_status == "Not Found"
    assert audited.assessment_state == "verified"
    assert "No source-grounded evidence" in audited.reason


class FlatEncoder:
    fingerprint = "v4917-frozen-scope"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class PersistentlyWrongProvider:
    disabled_reason = None

    def __init__(self):
        self.settings = Settings(llm_provider="ollama")
        self.calls = 0

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        if "second, independent" in system_prompt:
            return schema.model_validate({"R001": {
                "decision": "not_found", "relation": "absent", "evidence_ids": [],
                "proof_excerpt": None,
                "reason": ("GCP Cloud Run is listed under skills, but not "
                           "demonstrated in professional experience."),
            }})
        return schema.model_validate({"R001": {
            "decision": "not_found", "relation": "absent", "evidence_ids": [],
            "reason": ("GCP Cloud Run is listed under skills, but not "
                       "demonstrated in professional experience."),
        }})


def test_repeated_same_invalid_reason_never_becomes_verified_negative(tmp_path):
    provider = PersistentlyWrongProvider()
    source = ResumeSegment("S011", "skills", "GCP Cloud Run, BigQuery, Docker")
    with UnifiedEvidenceEngine(provider.settings, provider,
                               encoder=FlatEncoder(), top_k=4,
                               cache_path=tmp_path / "semantic.sqlite") as engine:
        rows, metrics = engine.assess([req("Google Cloud")], [source],
                                      source.text, candidate_id="scope-contradiction")
    assert provider.calls == 2
    assert metrics.final_verification_calls == 1
    assert rows[0].unified_status == "Unverified"
    assert rows[0].assessment_state == "unverified"
    assert rows[0].evidence_ids == ["S011"]
    assert metrics.unresolved_criteria == 1

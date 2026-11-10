"""Regression for source-stated degree families, not an accepted-major lookup.

These are deterministic interface tests. They do not measure actual live LLM
accuracy or grant a candidate a credential without a model/cited CV judgment.
"""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.jd import SYSTEM_PROMPT as JD_SYSTEM_PROMPT
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.qualification_validation import (
    _jd_requests_field_category,
    apply_qualification_checks,
    check_qualification,
)
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.unified import (
    FINAL_ADJUDICATION_PROMPT,
    UNIFIED_PROMPT,
    UnifiedEvidenceEngine,
    _needs_independent_overlap_review,
    _payload,
)


def typed(jd: str) -> ValidatedRequirement:
    item = ValidatedRequirement(
        requirement_id="R002", name=jd, jd_evidence=jd, priority="required")
    return item.model_copy(update={"constraint": classify_requirement(item, jd)})


def claimed_row(cv: str, *, status: str = "matched"):
    segments = segment_resume(cv)
    degree = next(s for s in segments if any(
        marker in s.text.casefold()
        for marker in ("bs ", "msc ", "bachelor's degree")))
    row = RequirementAssessment(
        requirement_id="R002", status=status,
        unified_status="Found" if status == "matched" else "Not Found",
        evidence_ids=[degree.segment_id],
        evidence_segments=[EvidenceCitation(
            segment_id=degree.segment_id, section=degree.section, text=degree.text)],
        evidence=degree.text,
        reason="The CV reports a completed bachelor's degree that is within the JD's field family.",
    )
    return segments, row


@pytest.mark.parametrize("major", [
    "Computer Science", "Software Engineering", "Information Technology",
])
def test_indefinite_singular_computing_program_allows_semantic_membership(major):
    jd = "Completed Bachelor's degree in a Computer Program"
    requirement = typed(jd)
    assert requirement.constraint.kind == "education"
    assert requirement.constraint.degree_level == "bachelor"
    assert requirement.constraint.field_of_study == "a Computer Program"
    assert _jd_requests_field_category(requirement)
    cv = f"EDUCATION\nBS {major} | Example University, 2022"
    segments, model_found = claimed_row(cv)
    check = check_qualification(requirement, cv, segments)
    assert check.outcome == "field_semantic", check
    checked, _, _ = apply_qualification_checks(
        requirements=[requirement], assessments=[model_found], resume_text=cv)
    final = reconcile_final_assessments(
        requirements=[requirement], assessments=checked)[0]
    assert final.status == "matched"
    assert final.unified_status == "Found"
    assert final.evidence_ids and final.evidence_segments[0].text.startswith("BS ")
    assert final.review_recommended  # model family interpretation, not verified credential


@pytest.mark.parametrize("jd,major", [
    ("Completed Bachelor's degree in computing programs.", "Software Engineering"),
    ("Completed Bachelor's degree in a business discipline.", "Accounting"),
    ("Completed Bachelor's degree in an engineering field.", "Mechanical Engineering"),
    ("Completed Bachelor's degree in any healthcare programme.", "Nursing"),
])
def test_degree_family_grammar_is_domain_neutral(jd, major):
    requirement = typed(jd)
    cv = f"EDUCATION\nBS {major} | Example University, 2022"
    assert _jd_requests_field_category(requirement)
    assert check_qualification(requirement, cv).outcome == "field_semantic"


def test_named_academic_field_is_not_silently_broadened():
    req = typed("Completed Bachelor's degree in Computer Science.")
    assert not _jd_requests_field_category(req)
    cv = "EDUCATION\nBS Software Engineering | Example University, 2022"
    segments, model_found = claimed_row(cv)
    assert check_qualification(req, cv).outcome == "mismatch"
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[model_found], resume_text=cv)
    assert reconcile_final_assessments(
        requirements=[req], assessments=checked)[0].unified_status != "Found"


def test_named_degree_program_does_not_automatically_become_field_family():
    req = typed("Completed Bachelor's degree in Computer Science program.")
    assert not _jd_requests_field_category(req)


def test_related_or_unrelated_field_is_never_automatically_credited():
    req = typed("Completed Bachelor's degree in a Computer Program")
    for major in ["Software Engineering", "Music Performance"]:
        cv = f"EDUCATION\nBS {major} | Example University, 2022"
        originals, negative_model_row = claimed_row(cv, status="not_matched")
        checked, _, _ = apply_qualification_checks(
            requirements=[req], assessments=[negative_model_row], resume_text=cv)
        assert reconcile_final_assessments(
            requirements=[req], assessments=checked)[0].unified_status == "Not Found"
        # The existing capped verification call may reassess the semantic
        # relationship; this predicate never decides it by Python alone.
        assert _needs_independent_overlap_review(
            req, checked[0], {s.segment_id: s for s in originals}, cv)


@pytest.mark.parametrize("candidate", [
    "EDUCATION\nCurrently pursuing BS Software Engineering, expected 2027",
    "EDUCATION\nMSc Software Engineering | Example University, 2022",
    "EDUCATION\nNo bachelor's degree in Software Engineering",
])
def test_incomplete_higher_level_or_denied_degree_not_automatically_found(candidate):
    req = typed("Completed Bachelor's degree in a Computer Program")
    segments, row = claimed_row(candidate)
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[row], resume_text=candidate)
    assert reconcile_final_assessments(
        requirements=[req], assessments=checked)[0].status != "matched"


def test_broad_degree_families_are_explicitly_disambiguated_in_model_input():
    broad = typed("Completed Bachelor's degree in a Computer Program")
    exact = typed("Completed Bachelor's degree in Computer Science")
    for requirement, expected in [(broad, "inclusive_category"),
                                  (exact, "exact_named_field")]:
        cv = "EDUCATION\nBS Software Engineering | Example University, 2022"
        segment = next(s for s in segment_resume(cv) if "BS " in s.text)
        data = json.loads(_payload(
            [requirement], {segment.segment_id: segment},
            {requirement.requirement_id: [segment.segment_id]}, 5))
        assert data["requirements"][0]["education_field_scope"] == expected
        assert data["requirements"][0]["jd_evidence"] == requirement.jd_evidence
    assert "generic singular academic family" in JD_SYSTEM_PROMPT
    assert "Indefinite singular" in UNIFIED_PROMPT
    assert "indefinite singular family" in FINAL_ADJUDICATION_PROMPT


class ConstantEncoder:
    fingerprint = "broad-degree-grammatical-recall-test"

    def embed_documents(self, values):
        return np.ones((len(values), 4), dtype=np.float32)

    def embed_queries(self, values):
        return np.ones((len(values), 4), dtype=np.float32)


class InitialLiteralDegreeRejection:
    disabled_reason = None

    def __init__(self):
        self.calls = 0

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        if system_prompt == FINAL_ADJUDICATION_PROMPT:
            return schema.model_validate({"R002": {
                "decision": "found", "relation": "entailed",
                "evidence_ids": ["S001"],
                "proof_excerpt": "BS in Software Engineering",
                "reason": "The completed BS in Software Engineering belongs to the JD's permitted computing-program family.",
            }})
        return schema.model_validate({"R002": {
            "decision": "not_found", "evidence_ids": [], "matched_term": None,
            "reason": "The literal degree title does not repeat Computer Program.",
        }})


def test_capped_independent_verification_can_repair_literal_family_false_negative(tmp_path):
    req = typed("Completed Bachelor's degree in a Computer Program")
    segment = ResumeSegment("S001", "education",
                            "BS in Software Engineering, completed 2022.")
    llm = InitialLiteralDegreeRejection()
    with UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                               encoder=ConstantEncoder(),
                               cache_path=tmp_path / "degree-family.db") as engine:
        rows, metrics = engine.assess(
            [req], [segment], segment.text, candidate_id="category-false-negative")
    assert llm.calls == 2
    assert metrics.final_verification_calls == 1
    assert metrics.unresolved_criteria == 0
    assert rows[0].status == "matched"
    assert rows[0].unified_status == "Found"
    assert rows[0].evidence_ids == ["S001"]


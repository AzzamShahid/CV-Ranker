"""Cross-domain source linkage for dated job roles and related education."""

import json

import numpy as np
import pytest

from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.qualification_validation import apply_qualification_checks
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import segment_resume
from cv_ranker.unified import _needs_independent_overlap_review
from cv_ranker.unified import UnifiedEvidenceEngine
from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from pathlib import Path


def role_req(subject):
    jd = f"Minimum 3 years of professional experience in {subject}."
    return ValidatedRequirement(
        requirement_id="R001", priority="required", name=jd, jd_evidence=jd,
        constraint=RequirementConstraint(kind="experience", origin="source_rules",
                                         minimum_years=3, subject=subject))


def assessed(req, segments, status="matched", cited=None):
    ids = cited if cited is not None else [s.segment_id for s in segments]
    return RequirementAssessment(
        requirement_id=req.requirement_id, status=status,
        unified_status="Found" if status == "matched" else "Not Found",
        evidence_ids=ids,
        evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                            section=s.section, text=s.text)
                           for s in segments if s.segment_id in ids],
        reason="The cited dated role and its actual duties establish relevant tenure.",
    )


@pytest.mark.parametrize("subject,role,duty", [
    ("machine-learning software", "Applied Software Engineer", "Built deployed machine-learning software APIs."),
    ("warehouse operations", "Warehouse Supervisor", "Managed warehouse operations and shift dispatch."),
    ("hospital patient care", "Clinical Nurse", "Provided hospital patient care and supervised wards."),
    ("quality assurance", "QA Analyst", "Performed quality assurance inspection and released reports."),
])
def test_dated_role_and_following_duty_can_satisfy_model_verified_experience(
        subject, role, duty):
    req = role_req(subject)
    cv = f"Experience\n{role} | Example Company | Jan 2022 - Oct 2026\n- {duty}"
    segments = segment_resume(cv)
    result = check_experience(req, cv, segments)
    assert result.outcome == "role_semantic"
    assert result.role_tenure[0].lower_years == 4.75
    linked = result.role_tenure[0]
    cited = [linked.role_segment_id, linked.duty_segment_ids[0]]
    verdict = assessed(req, segments, cited=cited)
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[verdict], resume_text=cv)
    assert checked[0].status == "matched"
    assert checked[0].review_recommended


def test_dated_role_without_cited_duty_cannot_earn_experience_point():
    req = role_req("clinical research")
    cv = "Experience\nClinical Research Officer | Hospital | Jan 2022 - Oct 2026\n- Conducted clinical research." 
    segments = segment_resume(cv)
    evidence = check_experience(req, cv, segments).role_tenure[0]
    verdict = assessed(req, segments, cited=[evidence.role_segment_id])
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[verdict], resume_text=cv)
    assert checked[0].status != "matched"


def test_dated_unrelated_role_not_automatically_upgraded_from_model_nonmatch():
    req = role_req("machine-learning engineering")
    cv = ("Experience\nIT Support Assistant | Helpdesk | Jan 2020 - Oct 2026\n"
          "- Managed inventory tickets, repaired desktops and completed service requests.\n"
          "No hands-on professional machine-learning engineering performed.")
    segments = segment_resume(cv)
    verdict = assessed(req, segments, status="not_matched", cited=[])
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[verdict], resume_text=cv)
    assert checked[0].status != "matched"


def test_different_short_roles_cannot_be_summed_without_source_proof():
    req = role_req("warehouse operations")
    cv = ("Experience\nWarehouse Associate | Depot A | Jan 2022 - Jun 2023\n"
          "- Managed warehouse operations.\n"
          "Warehouse Coordinator | Depot B | Jul 2023 - Oct 2024\n"
          "- Supported warehouse operations.")
    result = check_experience(req, cv, segment_resume(cv))
    assert result.outcome != "sufficient"
    assert result.outcome != "role_semantic"


def test_two_relevant_nonoverlapping_roles_can_jointly_establish_years():
    req = role_req("quality assurance")
    cv = ("Experience\nQuality Analyst | Company A | Jan 2022 - Dec 2023\n"
          "- Performed quality assurance reviews for product releases.\n"
          "Quality Lead | Company B | Jan 2024 - Oct 2026\n"
          "- Conducted quality assurance audits and evaluated reports.")
    segments = segment_resume(cv)
    check = check_experience(req, cv, segments)
    assert check.outcome == "role_semantic"
    assert len(check.role_groups[0]) == 2
    ids = [sid for role in check.role_groups[0]
           for sid in (role.role_segment_id, role.duty_segment_ids[0])]
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[assessed(req, segments, cited=ids)],
        resume_text=cv)
    assert checked[0].status == "matched"
    # Citing the years of BOTH roles but the duties of only ONE cannot earn it.
    unchecked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[assessed(req, segments, cited=ids[:-1])],
        resume_text=cv)
    assert unchecked[0].status != "matched"


def test_simultaneous_roles_cannot_double_count_experience_months():
    req = role_req("quality assurance")
    cv = ("Experience\nQuality Analyst | Company A | Jan 2023 - Jan 2025\n"
          "- Conducted quality assurance reviews.\n"
          "Quality Reviewer | Company B | Jan 2023 - Jan 2025\n"
          "- Performed quality assurance audits.")
    check = check_experience(req, cv, segment_resume(cv))
    assert check.outcome not in {"sufficient", "role_semantic"}


def test_multi_role_sources_remain_deduplicated_and_all_citable(tmp_path):
    req = role_req("quality assurance")
    cv = ("Experience\nQuality Analyst | Company A | Jan 2022 - Dec 2023\n"
          "- Performed quality assurance reviews for product releases.\n"
          "Quality Lead | Company B | Jan 2024 - Oct 2026\n"
          "- Conducted quality assurance audits and evaluated reports.")

    class MultiRoleProvider(SourceCapture):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            payload = json.loads(user_prompt)
            self.prompts.append(payload)
            source_ids = [source["id"] for source in payload["sources"]]
            return schema.model_validate({"R001": {
                "decision": "found", "evidence_ids": source_ids,
                "matched_term": None,
                "reason": "Both dated roles describe the required performed work.",
            }})

    provider = MultiRoleProvider()
    engine = UnifiedEvidenceEngine(provider.settings, provider,
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=FlatEncoder(), top_k=1)
    try:
        decisions, metrics = engine.assess([req], segment_resume(cv), cv,
                                           candidate_id="two-relevant-roles")
    finally:
        engine.close()
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=decisions, resume_text=cv)
    assert checked[0].status == "matched", (metrics.warnings[:3],
                                            metrics.resolved_validation_notices[:3])
    assert len(provider.prompts[0]["sources"]) == 4
    assert metrics.llm_calls == 1


def test_missed_role_link_is_eligible_for_only_existing_independent_group():
    req = role_req("quality assurance")
    cv = ("Experience\nQuality Officer | Company | Jan 2022 - Oct 2026\n"
          "- Conducted quality assurance reviews and built release checklists.")
    segments = segment_resume(cv)
    verdict = assessed(req, segments, status="not_matched", cited=[])
    originals = {s.segment_id: s for s in segments}
    assert _needs_independent_overlap_review(req, verdict, originals, cv)


def test_related_degree_remains_unscored_even_if_llm_says_transferable():
    req = ValidatedRequirement(
        requirement_id="R002", priority="required",
        name="Completed Bachelor's degree in Computer Science",
        jd_evidence="Completed Bachelor's degree in Computer Science",
        constraint=RequirementConstraint(kind="education", degree_level="bachelor",
                                         field_of_study="Computer Science", origin="source_rules"))
    cv = "Education\nBS Software Engineering | Example University, 2022"
    segments = segment_resume(cv)
    original = assessed(req, segments, status="not_matched",
                        cited=[segments[0].segment_id]).model_copy(update={
                            "unified_status": "Transferable"})
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[original], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].unified_status == "Transferable"


@pytest.mark.parametrize("span,minimum,expected", [
    ("Sept 2021 - Oct 2026", 3, True),
    ("2020 - 2024", 3, True),
    ("2022 - 2024", 3, False),
])
def test_conservative_month_and_year_only_role_intervals(span, minimum, expected):
    req = role_req("supply planning")
    cv = f"Experience\nSupply Planner | Organization | {span}\n- Delivered supply planning reports."
    result = check_experience(req, cv, segment_resume(cv))
    assert (result.outcome == "role_semantic") is expected


class FlatEncoder:
    fingerprint = "v497-selection-synthetic"
    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)
    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class SourceCapture:
    disabled_reason = None
    def __init__(self):
        self.settings = Settings(llm_provider="ollama")
        self.prompts = []
    def prompt_fits(self, *_):
        return True
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        payload = json.loads(user_prompt)
        self.prompts.append(payload)
        if "second, independent" in system_prompt:
            return schema.model_validate({"R001": {
                "decision": "not_found", "relation": "absent", "evidence_ids": [],
                "proof_excerpt": None, "reason": "No independently confirmed overlap.",
            }})
        ids = [s["id"] for s in payload["sources"]
               if "2022 - Oct 2026" in s["text"] or "Performed quality" in s["text"]]
        return schema.model_validate({"R001": {
            "decision": "found", "evidence_ids": ids,
            "matched_term": None, "reason": "The dated role and performed duty establish the JD.",
        }})


def test_source_selection_includes_role_date_and_its_duty_with_small_top_k(tmp_path):
    req = role_req("quality assurance")
    cv = ("Experience\nSupport Officer | Division | Jan 2020 - Jan 2021\n"
          "- Coordinated unrelated routine tickets.\n"
          "Quality Analyst | Division | Jan 2022 - Oct 2026\n"
          "- Performed quality assurance audits and released reports.")
    segments = segment_resume(cv)
    provider = SourceCapture()
    engine = UnifiedEvidenceEngine(provider.settings, provider,
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=FlatEncoder(), top_k=1)
    try:
        decisions, metrics = engine.assess([req], segments, cv,
                                           candidate_id="cross-domain-role")
    finally:
        engine.close()
    cited_sources = {s["text"] for s in provider.prompts[0]["sources"]}
    assert any("Jan 2022 - Oct 2026" in text for text in cited_sources)
    assert any("Performed quality assurance" in text for text in cited_sources)
    assert decisions[0].status == "matched", (
        decisions[0].status, decisions[0].reason, decisions[0].evidence_ids,
        metrics.warnings, metrics.resolved_validation_notices, metrics.llm_calls,
        [p.get('task') for p in provider.prompts])
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=decisions, resume_text=cv)
    assert checked[0].status == "matched"
    assert metrics.llm_calls == 1


@pytest.mark.parametrize("claimed_degree", [
    "BS Software Engineering | Example University, 2022",
    "MSc Artificial Intelligence | Example University, 2022",
])
def test_degree_qualification_is_recalled_for_independent_transfer_review(
        tmp_path, claimed_degree):
    requirement = ValidatedRequirement(
        requirement_id="R002", priority="required",
        name="Completed Bachelor's degree in Computer Science",
        jd_evidence="Completed Bachelor's degree in Computer Science",
        constraint=RequirementConstraint(kind="education", degree_level="bachelor",
                                         field_of_study="Computer Science", origin="source_rules"))

    class RelatedQualificationProvider(SourceCapture):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            payload = json.loads(user_prompt)
            self.prompts.append(payload)
            degree = next(source for source in payload["sources"]
                          if claimed_degree in source["text"])
            if "second, independent" in system_prompt:
                return schema.model_validate({"R002": {
                    "decision": "transferable", "relation": "overlap",
                    "evidence_ids": [degree["id"]],
                    "proof_excerpt": claimed_degree,
                    "reason": ("The claimed completed degree has substantive nearby "
                               "academic overlap, but it is not the exact named major."),
                }})
            return schema.model_validate({"R002": {
                "decision": "not_found", "evidence_ids": [],
                "matched_term": None,
                "reason": "The exact Computer Science degree is not documented.",
            }})

    cv = f"Education\n{claimed_degree}"
    provider = RelatedQualificationProvider()
    engine = UnifiedEvidenceEngine(provider.settings, provider,
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=FlatEncoder(), top_k=1)
    try:
        decisions, metrics = engine.assess(
            [requirement], segment_resume(cv), cv, candidate_id="degree-transfer")
    finally:
        engine.close()
    checked, _, _ = apply_qualification_checks(
        requirements=[requirement], assessments=decisions, resume_text=cv)
    assert len(provider.prompts) == 2  # initial group + ONE independent group
    assert metrics.final_verification_calls == 1
    assert checked[0].unified_status == "Transferable"
    assert checked[0].status != "matched"
    assert checked[0].evidence_segments[0].text == claimed_degree
    assert checked[0].review_recommended


@pytest.mark.parametrize("cv_name,requirement_name,required_snippets", [
    ("02_bilal_direct_fullstack.pdf", "Completed Bachelor's degree in Computer Science",
     ("BS Software Engineering",)),
    ("03_sara_functional_transfer.pdf", "LangChain",
     ("Haystack document retrieval", "Has not used LangChain")),
])
def test_real_pdf_recall_does_not_discard_core_relation_sources(
        tmp_path, cv_name, requirement_name, required_snippets):
    root = Path(__file__).resolve().parents[1]
    cv = extract_text(root / "sample_data" / "applied_ai_documents" / "pdf" / cv_name)
    if "degree" in requirement_name:
        req = ValidatedRequirement(
            requirement_id="R002", priority="required", name=requirement_name,
            jd_evidence=requirement_name,
            constraint=RequirementConstraint(kind="education", degree_level="bachelor",
                                             field_of_study="Computer Science", origin="source_rules"))
        rid = "R002"
    else:
        req = ValidatedRequirement(
            requirement_id="R009", priority="required", name=requirement_name,
            jd_evidence=requirement_name,
            constraint=RequirementConstraint(kind="skill", origin="source_rules"))
        rid = "R009"

    class SourceOnlyProvider(SourceCapture):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.prompts.append(json.loads(user_prompt))
            if "second, independent" in system_prompt:
                return schema.model_validate({rid: {
                    "decision": "not_found", "relation": "absent",
                    "evidence_ids": [], "proof_excerpt": None,
                    "reason": "No independent confirmation in this synthetic model.",
                }})
            return schema.model_validate({rid: {
                "decision": "not_found", "evidence_ids": [],
                "matched_term": None,
                "reason": "This mock only records retrieved evidence context.",
            }})

    provider = SourceOnlyProvider()
    engine = UnifiedEvidenceEngine(provider.settings, provider,
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=FlatEncoder(), top_k=8)
    try:
        engine.assess([req], segment_resume(cv), cv, candidate_id=cv_name)
    finally:
        engine.close()
    selected = [source["text"] for source in provider.prompts[0]["sources"]]
    for phrase in required_snippets:
        assert any(phrase.casefold() in text.casefold() for text in selected), (
            phrase, [text[:63] for text in selected])

"""Forensic regressions: original v4.9.61 failure shapes, no paid providers.

Source provenance, deterministic score and boundary tests use fictional data.
These do not certify live model correctness or remote deployment security.
"""
from __future__ import annotations

import csv
import email.message
import io
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import BaseHandler, ProxyHandler, build_opener
from urllib.response import addinfourl
from zipfile import ZipFile

import fitz
import pytest
from docx import Document

from cv_ranker.assessor import _validate_rows, _named_condition_groups
from cv_ranker.config import Settings
from cv_ranker.documents import DocumentError, extract_text
from cv_ranker.fallback import fallback_requirements
from cv_ranker.llm import OpenRouterStructuredLLM, OpenRouterHTTPError, _RejectProviderRedirects
from cv_ranker.recovery_bundle import local_signing_key
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.resume import _ASSESSMENT_LOGIC_FILES
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.schemas import (
    LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement,
    CandidateResult, RequirementAssessment, RankingReport,
)
from cv_ranker.segments import ResumeSegment
from cv_ranker.weighted_scoring import ScoreWeights, weighted_candidate, weighted_leaderboard
from evaluation.evaluate_supervisor import run_suite


def req(text, *, priority="required", rid="R001"):
    old = ValidatedRequirement(requirement_id=rid, name=text,
                               priority=priority, jd_evidence=text)
    return old.model_copy(update={"constraint": classify_requirement(old, text)})


def citation_result(jd, cv, *, section="experience"):
    requirement = req(jd)
    segment = ResumeSegment("S001", section, cv)
    provider = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="matched",
                          evidence_ids=["S001"], reason="Fixed incorrect or correct model proposal.")])
    accepted, invalid, why, _ = _validate_rows(
        response=provider, requirements=[requirement],
        resume_text=cv, segments=[segment], semantic_grounded=True)
    return accepted, invalid, why


@pytest.mark.parametrize("text", [
    "Used ERP dashboards for production reporting.",
    "Used MES dashboards for production reporting.",
    "Used SAP dashboards for production reporting.",
])
def test_three_way_alternative_any_branch(text):
    checked, invalid, why = citation_result(
        "Use ERP, MES or SAP for production reporting.", text)
    assert not invalid, why
    assert checked["R001"].status == "matched"


def test_four_option_list_and_mandatory_sibling():
    group = _named_condition_groups(req("Use ERP, MES, SAP or CRM for production reporting."))
    assert group == [["ERP", "MES", "SAP", "CRM"]]
    for tool in ["ERP", "MES", "SAP", "CRM"]:
        checked, invalid, why = citation_result(
            "Use ERP, MES, SAP or CRM for production reporting.",
            f"Used {tool} for production reporting.")
        assert not invalid, (tool, why)
    checked, invalid, _ = citation_result(
        "Use (ERP, MES or SAP) and SQL for production reporting.",
        "Used SAP for production reporting.")
    assert invalid or checked["R001"].status != "matched"


@pytest.mark.parametrize("source", [
    "Managed equipment repair procedures for production reporting.",
    "Managed EQUIPMENT REPAIR PROCEDURES for production reporting.",
    "Planned ERP deployment for production reporting next year.",
    "Did not use ERP for production reporting.",
])
def test_unrelated_initials_and_non_performed_mentions_cannot_award_erp(source):
    checked, invalid, _ = citation_result("Use ERP for production reporting.", source)
    assert invalid or checked["R001"].status != "matched"


def test_erp_mes_abbreviation_works_only_with_grounded_source():
    original_jd = "Use ERP or manufacturing execution systems (MES) for weaving reports."
    checked, invalid, why = citation_result(
        original_jd, "Used manufacturing execution systems for weaving reports.")
    assert not invalid, why
    rejected, missing, _ = citation_result(
        original_jd, "Used miscellaneous equipment scheduling for weaving reports.")
    assert missing or rejected["R001"].status != "matched"


@pytest.mark.parametrize("source,expected", [
    ("Maintain financial records for at least 7 years.", ("responsibility", None)),
    ("Archive records for 5 years.", ("responsibility", None)),
    ("At least 7 years of experience maintaining financial records.", ("experience", 7.0)),
    ("5 years in Python", ("experience", 5.0)),
    ("3 yrs using SAP", ("experience", 3.0)),
])
def test_duration_scope_must_be_candidate_tenure(source, expected):
    typed = classify_requirement(req(source), source)
    assert (typed.kind, typed.minimum_years) == expected


@pytest.mark.parametrize("text", [
    "Manage customer complaints from receipt through resolution.",
    "Resolve customer complaints from receipt through resolution.",
    "Inspect finished fabric for visible defects.",
])
def test_equivalent_operational_duties_type_consistently(text):
    assert req(text).constraint.kind == "responsibility"


def test_fallback_excludes_role_description_but_preserves_explicit_criteria():
    jd = (Path(__file__).resolve().parents[1]/"sample_data/hr_jd.txt").read_text()
    rows = fallback_requirements(jd, [], max_requirements=100)
    assert len(rows) == 8
    assert sum(x.priority == "required" for x in rows) == 6
    assert sum(x.priority == "preferred" for x in rows) == 2
    assert all("The role supports day-to-day" not in row.name for row in rows)


def test_docx_header_degree_is_not_silently_lost(tmp_path):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Education: Master of Science in Accounting, completed 2024"
    doc.add_paragraph("Professional experience preparing financial reports.")
    path = tmp_path / "resume.docx"
    doc.save(path)
    text = extract_text(path)
    assert "Master of Science in Accounting" in text
    assert "Professional experience" in text


def test_mixed_pdf_image_only_qualification_page_blocks_scoring(tmp_path):
    with fitz.open() as source:
        page = source.new_page()
        page.insert_text((50, 70), "Education: Completed Bachelor degree in Accounting.")
        scanned = page.get_pixmap()
    with fitz.open() as mixed:
        p = mixed.new_page()
        p.insert_text((50, 70), "Professional financial reporting experience in accounting.")
        p = mixed.new_page()
        p.insert_image(p.rect, pixmap=scanned)
        target = tmp_path / "mixed.pdf"
        mixed.save(target)
    with pytest.raises(DocumentError, match=r"page\(s\): 2"):
        extract_text(target)


def scoring_report(*, with_assessments=True):
    requirement = req("Python")
    rows = [RequirementAssessment(requirement_id="R001", status="not_matched",
                                  unified_status="Not Found")] if with_assessments else []
    person = CandidateResult(candidate_name="Synthetic.pdf", assessments=rows)
    report = RankingReport(job_description_source="fixture",jd_validation_mode="manual",
                           yake_candidates=[],requirements=[requirement],candidates=[person])
    return report, person


def test_unavailable_score_is_not_exported_verified():
    report, person = scoring_report(with_assessments=False)
    weights = ScoreWeights(experience=0,education=0,jd=100)
    row = weighted_leaderboard(report,weights)[0]
    assert row["weighted_score"] is None and row["score_status"] == "Unavailable"
    with ZipFile(io.BytesIO(complete_results_zip(report,weights))) as archive:
        record = list(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))[0]
    assert record["Score status"] == "Unavailable"
    assert record["Rank"] == "Unavailable"
    assert record["Weighted score (%)"] == ""


def test_verified_zero_remains_verified_not_unavailable():
    report, person = scoring_report()
    weights = ScoreWeights(experience=0,education=0,jd=100)
    row = weighted_leaderboard(report,weights)[0]
    assert row["weighted_score"] == 0.0
    assert row["score_status"] == "Verified"


def test_opt_in_weighted_split_and_legacy_display_split():
    requirements = [req("Python"),req("SQL",rid="R002",priority="preferred")]
    person = CandidateResult(candidate_name="Synthetic", assessments=[
        RequirementAssessment(requirement_id="R001", status="matched", unified_status="Found"),
        RequirementAssessment(requirement_id="R002", status="not_matched", unified_status="Not Found")])
    report = RankingReport(job_description_source="fixture",jd_validation_mode="manual",
                           yake_candidates=[],requirements=requirements,candidates=[person])
    def score(**opts):
        return weighted_candidate(report,person,ScoreWeights(0,0,100,**opts))["score"]
    assert score() == 50
    assert score(split_jd=True,required_share=90) == 50  # old display-only behavior
    assert score(jd_allocation_mode="weighted_split",required_share=90) == 90
    assert score(jd_allocation_mode="weighted_split",required_share=10) == 10


def test_ingestion_logic_is_in_resume_fingerprint():
    assert "documents.py" in _ASSESSMENT_LOGIC_FILES


def test_key_publication_is_atomic_for_two_readers(tmp_path, monkeypatch):
    import cv_ranker.recovery_bundle as bundle
    wait_for_first = threading.Event()
    release_first = threading.Event()
    original = bundle.secrets.token_bytes
    def slow_first(size):
        if threading.current_thread().name == "creator":
            wait_for_first.set()
            assert release_first.wait(5)
        return original(size)
    monkeypatch.setattr(bundle.secrets,"token_bytes",slow_first)
    key_path = tmp_path/"signing.key"
    found = []
    errors = []
    def writer():
        try: found.append(local_signing_key(key_path))
        except Exception as exc: errors.append(str(exc))
    thread = threading.Thread(target=writer, name="creator")
    thread.start()
    try:
        assert wait_for_first.wait(5)
        found.append(local_signing_key(key_path))  # should never observe empty key
    finally:
        release_first.set()
        thread.join(5)
    assert not errors, errors
    assert len(found) == 2 and found[0] == found[1] and len(found[0]) == 32


def test_cloud_transport_does_not_follow_redirect_with_token(monkeypatch):
    import cv_ranker.llm as llm_module
    forwarded = []
    class Intercept(BaseHandler):
        handler_order = 100
        def https_open(self, request):
            h = email.message.Message()
            if request.host == "openrouter.ai":
                h["Location"] = "https://example.invalid/untrusted"
                reply = addinfourl(io.BytesIO(b""), h, request.full_url, 302)
            else:
                forwarded.append(request.get_header("Authorization"))
                reply = addinfourl(io.BytesIO(b"{}"), h, request.full_url, 200)
            reply.msg = "synthetic"
            return reply
    monkeypatch.setattr(llm_module,"_SAFE_CLOUD_OPENER",
                        build_opener(ProxyHandler({}),_RejectProviderRedirects(),Intercept()))
    client = OpenRouterStructuredLLM(Settings(llm_provider="openrouter",openrouter_api_key="dummy"))
    with pytest.raises(OpenRouterHTTPError) as raised:
        client._post_chat({"model":"synthetic"})
    assert raised.value.status_code == 302
    assert not forwarded
    assert client.http_attempts == 1


def test_actual_unified_supervisor_branch_has_offline_regressions():
    results = run_suite()
    assert results["correct"] == results["count"] >= 7
    assert {"erp_false_initialism","erp_three_way","mes_three_way","sap_three_way"}.issubset(
        {row["case"] for row in results["cases"]})
    assert all(row["engine"].startswith("CVRanker(unified=True)") for row in results["cases"])

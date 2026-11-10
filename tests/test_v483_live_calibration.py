"""V4.8.3 regression contracts from the Sara live evidence export.

These use synthetic, fictional extracts and never make external LLM calls.
"""
from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.jd import SYSTEM_PROMPT as JD_PROMPT
from cv_ranker.schemas import (EvidenceCitation, RankingReport, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.unified import UNIFIED_PROMPT


def _req(rid, name, kind="skill", operator="single", priority="preferred"):
    return ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority=priority,
        constraint=RequirementConstraint(kind=kind, operator=operator,
                                         source_line_numbers=[1],
                                         requires_review=operator != "single"),
    )


def _citation(rid, text, section):
    return EvidenceCitation(segment_id=rid, section=section, text=text)


def _result(rid, status, citations, final):
    return RequirementAssessment(
        requirement_id=rid, status=status, unified_status=final,
        evidence_segments=citations,
        evidence_ids=[s.segment_id for s in citations],
        evidence=citations[0].text if citations else None,
        reason="Original evidence-backed assessment of completed work.",
    )


def test_production_experience_example_list_preserves_verified_work():
    req = _req("R018", "Experience building production-oriented AI products, "
               "including deployable AI applications, APIs, containerized services, "
               "or cloud-ready solutions.", kind="experience", operator="complex")
    source = _citation("S008", "Delivered a customer-facing knowledge assistant with "
                       "hosted LLM APIs and automated retrieval.", "experience")
    assessed = _result(req.requirement_id, "matched", [source], "Found")
    updated, notices, changed = apply_compound_checks(
        requirements=[req], assessments=[assessed], resume_text=source.text)
    assert not changed and updated[0].status == "matched"
    assert updated[0].evidence_ids == ["S008"]
    assert updated[0].review_recommended
    assert updated[0].compound_check.outcome == "matched"
    assert not notices  # Accepted illustrative clauses are not pipeline failures.


def test_descriptive_experience_does_not_credit_a_bare_skill_or_denial():
    req = _req("R018", "Experience building products including APIs or services",
               kind="experience", operator="complex")
    for source in (
        _citation("S001", "APIs, services, Python", "skills"),
        _citation("S002", "Never built a deployable service", "experience"),
    ):
        assessed = _result(req.requirement_id, "matched", [source], "Found")
        updated, _, changed = apply_compound_checks(
            requirements=[req], assessments=[assessed], resume_text=source.text)
        assert changed and updated[0].status == "uncertain"
        assert updated[0].compound_check.outcome == "needs_review"


def test_true_complex_compounds_still_fail_closed():
    req = _req("R001", "Python and Django or Flask", kind="skill", operator="complex")
    source = _citation("S001", "Python, Django, Flask", "skills")
    updated, _, changed = apply_compound_checks(
        requirements=[req],
        assessments=[_result("R001", "matched", [source], "Found")],
        resume_text=source.text)
    assert changed and updated[0].status == "uncertain"


def test_mandatory_experience_and_clause_not_bypassed_by_examples():
    req = _req("R019", "Experience designing apps and managing deployments, "
               "including APIs or cloud services", kind="experience", operator="complex")
    source = _citation("S012", "Designed an app using APIs.", "experience")
    updated, _, changed = apply_compound_checks(
        requirements=[req], assessments=[_result("R019", "matched", [source], "Found")],
        resume_text=source.text)
    assert changed and updated[0].status == "uncertain"
    assert updated[0].compound_check.outcome == "needs_review"


def test_related_time_series_and_framework_work_remain_transferable():
    requirements = [
        _req("R009", "LangChain", priority="required"),
        _req("R014", "Time-series forecasting"),
        _req("R018", "Experience building production-oriented AI products, "
             "including deployable AI applications, APIs, or containerized services.",
             kind="experience", operator="complex"),
    ]
    citations = [
        _citation("S009", "Implemented tool routing and conditional workflows with "
                  "Haystack, without LangChain.", "experience"),
        _citation("S020", "Built batch demand-anomaly screening with seasonal "
                  "features and out-of-time validation.", "experience"),
        _citation("S008", "Delivered a customer-facing knowledge assistant "
                  "using hosted model APIs.", "experience"),
    ]
    assessments = [
        _result("R009", "not_matched", [citations[0]], "Transferable"),
        _result("R014", "not_matched", [citations[1]], "Transferable"),
        _result("R018", "matched", [citations[2]], "Found"),
    ]
    updated, _, changed = apply_compound_checks(
        requirements=requirements, assessments=assessments,
        resume_text="\n".join(c.text for c in citations))
    assert not changed
    candidate = score_candidate(candidate_name="fictional.txt", candidate_source="fictional.txt",
                                requirements=requirements, assessments=updated,
                                evaluation_mode="llm_assessed", errors=["Example validation notice"])
    report = RankingReport(job_description_source="fictional_jd.txt",
                           jd_validation_mode="llm_validated", yake_candidates=[],
                           requirements=requirements, candidates=[candidate],
                           warnings=["Example pipeline warning"])
    segments = [ResumeSegment(segment_id=c.segment_id, section=c.section,
                              text=c.text, source_lines=()) for c in citations]
    final = reconcile_unified_candidate(report, 0, segment_ledger(segments))
    by_id = {r["ID"]: r for r in final["Criteria"]}
    assert [by_id[rid]["Result"] for rid in ("R009", "R014", "R018")] == [
        "Transferable", "Transferable", "Found"]
    assert (final["Required matched"], final["Preferred matched"], final["Transferable"]) == (0, 1, 2)
    assert final["Notices"] == ["Example validation notice"]
    assert final["Run warnings"] == ["Example pipeline warning"]
    assert by_id["R018"]["Checkpoints"][0]["Validated against CV"]


def test_legacy_nonnumeric_uncertainty_citations_preserved_for_review():
    req = _req("R018", "Experience building services including APIs or workers",
               kind="experience", operator="complex")
    c = _citation("S007", "Exploring API deployment", "projects")
    item = _result("R018", "uncertain", [c], "Not Found")
    result, _, _ = apply_compound_checks(
        requirements=[req], assessments=[item], resume_text=c.text)
    assert result[0].status == "uncertain" and result[0].evidence_ids == ["S007"]
    assert result[0].review_recommended


def test_prompt_contract_prevents_relation_inflation_without_more_calls():
    assert "related inputs" in UNIFIED_PROMPT.casefold()
    assert "TRANSFERABLE" not in UNIFIED_PROMPT  # canonical JSON is lower-case
    assert "transferable" in UNIFIED_PROMPT
    assert "different item" in UNIFIED_PROMPT.casefold()
    assert "including/such as" in UNIFIED_PROMPT
    assert "ENTAILMENT CHECK" in UNIFIED_PROMPT
    assert "keep the\nreason consistent with status" in UNIFIED_PROMPT
    assert "including" in JD_PROMPT and '"A or B"' in JD_PROMPT

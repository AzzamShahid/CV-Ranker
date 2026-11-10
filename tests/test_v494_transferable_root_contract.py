"""Regression contracts for the distinction between exact credit and overlap.

These fixtures exercise generic evidence decisions, not job/degree acceptance
tables. The fake provider never uses a cloud API or a sample resume name.
"""
import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.pipeline import CVRanker
from cv_ranker.qualification_validation import (apply_qualification_checks,
                                              check_qualification,
                                              related_degree_transfer_supported)
from cv_ranker.documents import extract_text
from cv_ranker.segments import segment_resume
from pathlib import Path
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem,
                               _compared_work_leads, _final_unified_row,
                               _needs_independent_overlap_review)


def requirement(name, kind="skill", field=None):
    return ValidatedRequirement(
        requirement_id="R001", priority="required", name=name, jd_evidence=name,
        constraint=RequirementConstraint(kind=kind, origin="source_rules",
                                         degree_level="bachelor" if field else None,
                                         field_of_study=field),
    )


def cited(segment, *, status="not_matched", final="Transferable"):
    return RequirementAssessment(
        requirement_id="R001", status=status, unified_status=final,
        evidence=segment.text, evidence_ids=[segment.segment_id],
        evidence_segments=[EvidenceCitation(segment_id=segment.segment_id,
                                            section=segment.section, text=segment.text)],
        reason="The completed alternative has overlapping subject content, "
               "but it does not establish the exact named requirement.",
    )


@pytest.mark.parametrize("requested,actual", [
    ("Computer Science", "Software Engineering"),
    ("Environmental Science", "Ecology"),
    ("Business Administration", "Accounting"),
])
def test_same_level_different_major_preserves_model_transfer_without_point(requested, actual):
    req = requirement(f"Completed Bachelor's degree in {requested}",
                      kind="education", field=requested)
    segment = ResumeSegment("S001", "education", f"BS in {actual}, completed 2024.")
    decisions, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[cited(segment)], resume_text=segment.text)
    assert decisions[0].status == "not_matched"  # Never direct credit.
    assert decisions[0].unified_status == "Transferable"
    assert decisions[0].review_recommended
    assert decisions[0].evidence_ids == ["S001"]


@pytest.mark.parametrize("cv", [
    "Currently pursuing a BS in Ecology.",
    "No bachelor's degree in Ecology.",
    "Associate degree in Ecology, completed 2024.",
])
def test_pending_denied_or_lower_level_never_inherits_transfer(cv):
    req = requirement("Completed Bachelor's degree in Environmental Science",
                      kind="education", field="Environmental Science")
    segment = ResumeSegment("S001", "education", cv)
    decisions, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[cited(segment)], resume_text=segment.text)
    assert decisions[0].status != "matched"
    assert decisions[0].unified_status == "Not Found"
    assert not any(x.state == "claimed" and x.degree_level == "bachelor"
                   for x in decisions[0].qualification_check.claims)


@pytest.mark.parametrize("requested,actual", [
    ("Computer Science", "MSc Artificial Intelligence"),
    ("Environmental Science", "PhD Geology"),
    ("Business Administration", "Master of Science in Management"),
])
def test_completed_related_higher_degree_can_be_reviewed_not_awarded(requested, actual):
    req = requirement(f"Completed Bachelor's degree in {requested}",
                      kind="education", field=requested)
    segment = ResumeSegment("S001", "education", f"{actual} | University, 2022")
    decisions, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[cited(segment)], resume_text=segment.text)
    assert decisions[0].status != "matched"
    assert decisions[0].unified_status == "Transferable"
    assert decisions[0].review_recommended
    assert decisions[0].evidence_ids == ["S001"]


def test_higher_degree_does_not_get_transfer_without_positive_semantic_verdict():
    req = requirement("Completed Bachelor's degree in Computer Science",
                      kind="education", field="Computer Science")
    segment = ResumeSegment("S001", "education", "PhD Classical Archaeology, 2022")
    decisions, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[cited(segment, final="Not Found")],
        resume_text=segment.text)
    assert decisions[0].status != "matched"
    assert decisions[0].unified_status == "Not Found"


def test_job_title_research_associate_is_not_mistaken_for_a_degree():
    req = requirement("Completed Bachelor's degree in Computer Science",
                      kind="education", field="Computer Science")
    text = "Applied AI Research Associate with three years of experience.\nMSc Artificial Intelligence, 2022."
    check = check_qualification(req, text, segment_resume(text))
    assert check is not None
    assert [(claim.degree_level, claim.field_of_study)
            for claim in check.claims] == [("master", "Artificial Intelligence")]


def test_qualification_gate_preserves_cited_higher_degree_not_uncited_claim():
    req = requirement("Completed Bachelor's degree in Computer Science",
                      kind="education", field="Computer Science")
    text = "Education\nMSc Artificial Intelligence, 2022."
    check = check_qualification(req, text, segment_resume(text))
    assert check and len(check.claims) == 1
    assert related_degree_transfer_supported(req, check, [check.claims[0].segment_id])
    assert not related_degree_transfer_supported(req, check, ["S999"])


def test_real_pdf_extracts_master_without_fabricating_associate_degree():
    cv = Path(__file__).resolve().parents[1] / "sample_data" / "applied_ai_documents" / "pdf" / "08_taimoor_research_transfer.pdf"
    text = extract_text(cv)
    req = requirement("Completed Bachelor's degree in Computer Science",
                      kind="education", field="Computer Science")
    check = check_qualification(req, text, segment_resume(text))
    assert check is not None
    assert any(x.state == "claimed" and x.degree_level == "master" and
               x.field_of_study == "Artificial Intelligence" for x in check.claims)
    assert not any(x.degree_level == "associate" for x in check.claims)


def test_completed_function_is_not_rejected_solely_due_to_section_heading():
    req = requirement("NamedWorkflowFramework")
    segment = ResumeSegment(
        "S015", "education",
        "Never used NamedWorkflowFramework professionally; built a custom "
        "state-routing workflow with retries and reviewer approval.",
    )
    judgment = cited(segment)
    proposal = UnifiedItem(requirement_id="R001", decision="transferable",
                           evidence_ids=["S015"],
                           reason="A completed custom workflow overlaps the framework functions.")
    result = _final_unified_row(judgment, proposal, req, {"S015": segment})
    assert result.status == "not_matched"
    assert result.unified_status == "Transferable"


def test_denial_without_completed_alternative_cannot_be_transferable():
    req = requirement("NamedWorkflowFramework")
    segment = ResumeSegment("S001", "education",
                            "Has not used NamedWorkflowFramework professionally.")
    result = _final_unified_row(
        cited(segment), UnifiedItem(requirement_id="R001", decision="transferable",
                                    evidence_ids=["S001"],
                                    reason="The applicant has not used this tool."),
        req, {"S001": segment})
    assert result.unified_status == "Not Found"


@pytest.mark.parametrize("text,section,expected", [
    ("Workflow audit engine: state routing, process checks and reviewer gates.",
     "projects", "Transferable"),
    ("Workflow audit engine: planned future state routing and reviewer gates.",
     "projects", "Not Found"),
    ("Never built a custom audit workflow with state routing and reviewer gates.",
     "experience", "Not Found"),
])
def test_project_outcome_without_past_tense_verb_and_negative_controls(
        text, section, expected):
    req = requirement("NamedWorkflowFramework")
    segment = ResumeSegment("S055", section, text)
    proposal = UnifiedItem(requirement_id="R001", decision="transferable",
                           evidence_ids=["S055"], reason="Review completed overlap.")
    assert _final_unified_row(cited(segment), proposal, req,
                              {"S055": segment}).unified_status == expected


def test_project_results_are_not_skipped_when_comparison_mentions_other_tool():
    req = requirement("NamedWorkflowFramework")
    sources = [
        ResumeSegment("S001", "education", "Never used NamedWorkflowFramework; "
                      "built comparable workflow routing using another approach."),
        ResumeSegment("S002", "experience", "Built separate equipment checks."),
        ResumeSegment("S003", "projects", "Conditional workflow engine: state "
                      "routing, conditional branches and review gates."),
        ResumeSegment("S004", "experience", "Orchestrated conditional workflows "
                      "using custom routing and reviewer approvals."),
    ]
    selected = _compared_work_leads(
        req, {source.segment_id: source for source in sources},
        {source.segment_id for source in sources})
    assert "S003" in selected and "S004" in selected
    assert "S002" not in selected


class FlatEncoder:
    fingerprint = "v494-offline-stub"
    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)
    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class TwoStageProvider:
    disabled_reason = None
    def __init__(self, final_decision="transferable"):
        self.settings = Settings(llm_provider="ollama")
        self.calls = 0
        self.final_decision = final_decision

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        payload = json.loads(user_prompt)
        rid = payload["requirements"][0]["id"]
        if "second, independent" not in system_prompt:
            return schema.model_validate({rid: {
                "decision": "not_found", "evidence_ids": [],
                "reason": "The exact major is not established by the cited source.",
            }})
        source = next(s for s in payload["sources"]
                      if any(token in s["text"] for token in
                             ("BS in", "MSc ", "Master of Science", "PhD ")))
        return schema.model_validate({rid: {
            "decision": self.final_decision,
            "relation": "overlap" if self.final_decision == "transferable" else "absent",
            "evidence_ids": [source["id"]] if self.final_decision != "not_found" else [],
            "proof_excerpt": source["text"] if self.final_decision != "not_found" else None,
            "reason": "The completed field is related but does not establish the exact major."
                      if self.final_decision == "transferable" else
                      "The alternative major does not establish relevant field overlap.",
        }})


@pytest.mark.parametrize("verdict", ["transferable", "not_found"])
@pytest.mark.parametrize("cv", [
    "BS in Ecology, completed 2024.",
    "MSc Ecology, completed 2024.",
    "PhD Geology, completed 2024.",
])
def test_one_grouped_independent_check_can_correct_missed_degree_overlap(tmp_path, verdict, cv):
    req = requirement("Completed Bachelor's degree in Environmental Science",
                      kind="education", field="Environmental Science")
    segment = ResumeSegment("S001", "education", cv)
    llm = TwoStageProvider(verdict)
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "cache.sqlite", encoder=FlatEncoder())
    try:
        result, metrics = engine.assess([req], [segment], cv, candidate_id="offline-candidate")
    finally:
        engine.close()
    assert llm.calls == 2 == metrics.llm_calls
    assert metrics.final_verification_calls == 1
    assert result[0].status == "not_matched"
    assert result[0].unified_status == ("Transferable" if verdict == "transferable" else "Not Found")


def test_unrelated_negative_skill_without_alternative_does_not_trigger_extra_api_call():
    req = requirement("NamedWorkflowFramework")
    denial = ResumeSegment("S001", "skills", "Not familiar with NamedWorkflowFramework.")
    decision = RequirementAssessment(requirement_id="R001", status="not_matched",
                                     unified_status="Not Found")
    assert not _needs_independent_overlap_review(req, decision, {"S001": denial}, denial.text)


def test_batch_prompt_retains_late_independent_work_beyond_dense_top_k(tmp_path):
    req = requirement("NamedWorkflowFramework")
    sources = [
        ResumeSegment("S001", "summary", "Has not used NamedWorkflowFramework; "
                      "built comparable approval workflow using another approach."),
        ResumeSegment("S002", "skills", "No professional use of NamedWorkflowFramework."),
        ResumeSegment("S003", "other", "Studying NamedWorkflowFramework tutorials."),
    ]
    sources.extend(ResumeSegment(f"S{i:03d}", "experience",
                                 f"Completed unrelated annual audit task {i}.")
                   for i in range(4, 9))
    sources.append(ResumeSegment(
        "S009", "projects", "Approval workflow engine: state routing, retries "
        "and independent reviewer approval."))
    sources.append(ResumeSegment(
        "S010", "experience", "Orchestrated approval workflows with reviewer "
        "gates and custom decision routing."))

    class CaptureProvider(TwoStageProvider):
        def __init__(self):
            super().__init__(final_decision="not_found")
            self.first_source_ids = []

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            if "second, independent" in system_prompt:
                return schema.model_validate({"R001": {
                    "decision": "not_found", "relation": "absent",
                    "evidence_ids": [], "proof_excerpt": None,
                    "reason": "No independently verified overlap was established.",
                }})
            if "second, independent" not in system_prompt and not self.first_source_ids:
                self.first_source_ids = [s["id"] for s in json.loads(user_prompt)["sources"]]
            return super().invoke_structured(system_prompt=system_prompt,
                                             user_prompt=user_prompt, schema=schema)

    llm = CaptureProvider()
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=FlatEncoder(), top_k=8)
    try:
        engine.assess([req], sources, "\n".join(s.text for s in sources),
                      candidate_id="segment-recall-fixture")
    finally:
        engine.close()
    assert "S009" in llm.first_source_ids
    assert "S010" in llm.first_source_ids


def test_complete_pipeline_and_display_keep_related_degree_as_unscored_transfer(
        tmp_path, monkeypatch):
    req = requirement("Completed Bachelor's degree in Environmental Science",
                      kind="education", field="Environmental Science")
    monkeypatch.setattr("cv_ranker.pipeline.extract_yake_candidates", lambda *_: [])
    monkeypatch.setattr(
        "cv_ranker.pipeline.validate_jd_requirements",
        lambda **_: ([req], "llm_validated", []),
    )
    monkeypatch.setattr(
        "cv_ranker.pipeline.add_requirement_types",
        lambda requirements, *_args, **_kwargs: requirements,
    )
    jd = tmp_path / "position.txt"
    cv = tmp_path / "candidate.txt"
    jd.write_text(req.name)
    cv.write_text("Education\nBS in Ecology, completed 2024.")
    ranker = CVRanker(
        settings=Settings(llm_provider="ollama"), use_llm=True, unified=True,
        embedding_encoder=FlatEncoder(), embedding_cache_path=tmp_path / "db.sqlite",
    )
    ranker.llm = TwoStageProvider("transferable")
    report = ranker.run(jd, [cv])
    candidate = report.candidates[0]
    assert candidate.primary_score == 0
    assert candidate.assessments[0].status == "not_matched"
    assert candidate.assessments[0].unified_status == "Transferable"
    view = reconcile_unified_candidate(report, 0,
                                      segment_ledger(ranker.source_ledgers[str(cv)]))
    assert view["Required matched"] == 0
    assert view["Transferable"] == 1
    assert view["Criteria"][0]["Result"] == "Transferable"
    assert "related" in view["Criteria"][0]["Why"]


def test_full_pipeline_higher_level_degree_is_unscored_transfer(tmp_path, monkeypatch):
    req = requirement("Completed Bachelor's degree in Environmental Science",
                      kind="education", field="Environmental Science")
    monkeypatch.setattr("cv_ranker.pipeline.extract_yake_candidates", lambda *_: [])
    monkeypatch.setattr("cv_ranker.pipeline.validate_jd_requirements",
                        lambda **_: ([req], "llm_validated", []))
    monkeypatch.setattr("cv_ranker.pipeline.add_requirement_types",
                        lambda requirements, *_args, **_kwargs: requirements)
    jd, cv = tmp_path / "job.txt", tmp_path / "candidate.txt"
    jd.write_text(req.name)
    cv.write_text("Education\nMSc Ecology, completed 2024.")
    ranker = CVRanker(settings=Settings(llm_provider="ollama"), use_llm=True,
                      unified=True, embedding_encoder=FlatEncoder(),
                      embedding_cache_path=tmp_path / "db.sqlite")
    ranker.llm = TwoStageProvider("transferable")
    report = ranker.run(jd, [cv])
    candidate = report.candidates[0]
    assert candidate.primary_score == 0
    assert candidate.assessments[0].status != "matched"
    assert candidate.assessments[0].unified_status == "Transferable"
    view = reconcile_unified_candidate(
        report, 0, segment_ledger(ranker.source_ledgers[str(cv)]))
    assert view["Required matched"] == 0
    assert view["Transferable"] == 1
    assert view["Criteria"][0]["Result"] == "Transferable"

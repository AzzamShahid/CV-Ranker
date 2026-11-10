"""Regression tests for generic duration and unstated deployment thresholds."""

from pathlib import Path
from types import SimpleNamespace

from cv_ranker.config import Settings

from cv_ranker.documents import extract_text
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import segment_resume
from cv_ranker.unified import (_needs_independent_overlap_review,
                               UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse)


def _aisha():
    path = (Path(__file__).resolve().parents[1] / "sample_data" /
            "applied_ai_documents" / "pdf" / "01_aisha_direct_senior.pdf")
    text = extract_text(path)
    return text, segment_resume(text)


def test_dataset_coverage_years_do_not_conflict_with_professional_tenure():
    text, segments = _aisha()
    req = ValidatedRequirement(
        requirement_id="R001", name="Minimum 3 years of relevant professional experience",
        priority="required", jd_evidence="Minimum 3 years of relevant professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    verdict = check_experience(req, text, segments)
    assert verdict.outcome == "sufficient", verdict.model_dump()
    assert all("retail series" not in claim.quote.lower() for claim in verdict.claims)
    assert any(claim.lower_years == 5.75 for claim in verdict.claims)


def test_aisha_explicit_experience_survives_validator_and_final_reconciliation():
    text, segments = _aisha()
    req = ValidatedRequirement(
        requirement_id="R001", name="Minimum 3 years of relevant professional experience",
        priority="required", jd_evidence="Minimum 3 years of relevant professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    # Reproduce a first-model false negative: source-grounded numeric validation
    # must restore a correctly cited Found verdict, with no copied dataset years.
    initial = RequirementAssessment(requirement_id="R001", status="not_matched",
                                    unified_status="Not Found", reason="Not established.")
    checked, _, changed = apply_experience_checks(
        requirements=[req], assessments=[initial], resume_text=text)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)
    assert changed
    assert final[0].status == "matched"
    assert final[0].unified_status == "Found"
    assert final[0].experience_check.outcome == "sufficient"
    assert final[0].evidence_ids
    assert any(s.segment_id == final[0].evidence_ids[0] and "5 years 9 months" in s.text
               for s in segments)


def test_dataset_duration_inside_experience_section_is_not_job_tenure():
    text = """EXPERIENCE
Data analyst | Sample Office | Jan 2024 - Dec 2024
Worked on evaluation projects.
Historical forecast input: four years of sales data records.
"""
    req = ValidatedRequirement(
        requirement_id="X1", name="Minimum 3 years of professional experience",
        priority="required", jd_evidence="Minimum 3 years of professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    result = check_experience(req, text, segment_resume(text))
    assert result.outcome != "sufficient", result.model_dump()
    assert all("sales data records" not in c.quote for c in result.claims)


def test_working_with_four_years_of_data_is_not_four_years_of_employment():
    text = ("EXPERIENCE\nWorked with four years of archive data to test a "
            "forecasting prototype.\n")
    req = ValidatedRequirement(
        requirement_id="X2", name="Minimum 3 years of professional experience",
        priority="required", jd_evidence="Minimum 3 years of professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    verdict = check_experience(req, text, segment_resume(text))
    assert verdict.outcome != "sufficient", verdict.model_dump()


def test_explicit_four_years_of_work_still_establishes_generic_tenure():
    text = "PROFESSIONAL PROFILE\nWorked for four years delivering customer service.\n"
    req = ValidatedRequirement(
        requirement_id="X3", name="Minimum 3 years of professional experience",
        priority="required", jd_evidence="Minimum 3 years of professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    verdict = check_experience(req, text, segment_resume(text))
    assert verdict.outcome == "sufficient", verdict.model_dump()


def test_numeric_data_coverage_not_credited_even_alongside_real_tenure():
    text = ("EXPERIENCE\nWorked for five years with engineering teams "
            "using two years of collected measurements.\n")
    req = ValidatedRequirement(
        requirement_id="X4", name="Minimum 3 years of professional experience",
        priority="required", jd_evidence="Minimum 3 years of professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    verdict = check_experience(req, text, segment_resume(text))
    assert verdict.outcome == "sufficient", verdict.model_dump()
    assert [claim.lower_years for claim in verdict.claims] == [5.0]


def test_worked_on_projects_for_years_is_an_explicit_duration():
    text = "PROFILE\nWorked on professional projects for five years.\n"
    req = ValidatedRequirement(
        requirement_id="X5", name="Minimum 3 years of professional experience",
        priority="required", jd_evidence="Minimum 3 years of professional experience",
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         requires_review=False))
    verdict = check_experience(req, text, segment_resume(text))
    assert verdict.outcome == "sufficient", verdict.model_dump()


def test_completed_skill_pilot_downgraded_for_no_deployment_gets_second_opinion():
    text, segments = _aisha()
    cited = [seg for seg in segments
             if "medical-image" in seg.text.casefold() or "medical imagery" in seg.text.casefold()]
    assert len(cited) >= 2
    req = ValidatedRequirement(
        requirement_id="R012", name="Medical imaging", priority="preferred",
        jd_evidence="Medical imaging",
        constraint=RequirementConstraint(kind="skill", requires_review=False))
    row = RequirementAssessment(
        requirement_id="R012", status="not_matched", unified_status="Transferable",
        reason=("The candidate has experience with medical imaging research pilots "
                "and segmentation research, though not explicitly stated as a "
                "deployed application or commercial product."),
        evidence_ids=[s.segment_id for s in cited],
        evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                            section=s.section, text=s.text)
                           for s in cited])
    assert _needs_independent_overlap_review(
        req, row, {s.segment_id: s for s in segments}, text)


def test_generic_nonsoftware_pilot_and_unstated_deployment_also_gets_review():
    text = """PROJECTS
Designed a fabric-weaving research pilot and tested samples against weave patterns.
"""
    segments = segment_resume(text)
    source = next(s for s in segments if "fabric-weaving" in s.text)
    req = ValidatedRequirement(
        requirement_id="W5", name="Fabric weaving", priority="preferred",
        jd_evidence="Fabric weaving",
        constraint=RequirementConstraint(kind="skill", requires_review=False))
    row = RequirementAssessment(
        requirement_id="W5", status="not_matched", unified_status="Transferable",
        reason="Has experience with fabric weaving research, though no commercial deployment is stated.",
        evidence_ids=[source.segment_id],
        evidence_segments=[EvidenceCitation(segment_id=source.segment_id,
                                            section=source.section, text=source.text)])
    assert _needs_independent_overlap_review(
        req, row, {s.segment_id: s for s in segments}, text)


def test_aisha_completed_project_can_be_promoted_by_independent_source_judgment():
    text, segments = _aisha()
    source = next(s for s in segments if "Designed a lightweight medical-image" in s.text)
    req = ValidatedRequirement(
        requirement_id="R012", name="Medical imaging", priority="preferred",
        jd_evidence="Medical imaging",
        constraint=RequirementConstraint(kind="skill", requires_review=False))

    class AssessmentModel:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, schema, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 1:
                return UnifiedResponse(assessments=[UnifiedItem(
                    requirement_id="R012", decision="transferable", relation="overlap",
                    evidence_ids=[source.segment_id],
                    reason=("The candidate has experience with medical imaging research "
                            "pilots, though not deployed in a commercial product."))])
            return schema.model_validate({"R012": {
                "decision": "found", "relation": "entailed",
                "evidence_ids": [source.segment_id],
                "proof_excerpt": "Designed a lightweight medical-image triage research pilot",
                "reason": ("The completed medical-image triage pilot reports practical "
                           "work in the requested skill, with no deployment rule in the JD."),
            }})

    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama")
    engine.llm = AssessmentModel()
    engine.top_k = 8
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        "R012": [SimpleNamespace(source=SimpleNamespace(segment_id=source.segment_id))]})

    rows, metrics = engine.assess([req], segments, text, candidate_id="aisha")
    assert engine.llm.calls == 2
    assert metrics.final_verification_calls == 1
    assert rows[0].unified_status == "Found"
    assert rows[0].status == "matched"
    assert rows[0].evidence_ids == [source.segment_id]

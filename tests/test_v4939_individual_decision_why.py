"""Keep requirement-level Why distinct from comparative rank reasoning."""

from pathlib import Path

from cv_ranker.documents import extract_text
from cv_ranker.experience_validation import apply_experience_checks
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import (CandidateResult, RankingReport,
                               RequirementAssessment, RequirementConstraint,
                               ValidatedRequirement)
from cv_ranker.segments import segment_resume
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate


ROOT = Path(__file__).resolve().parents[1]
JD = ("Minimum 3 years of relevant professional experience developing or "
      "delivering AI, machine-learning, deep-learning, or LLM-powered software.")


def _report_and_ledger():
    text = extract_text(ROOT / "sample_data/applied_ai_documents/pdf/02_bilal_direct_fullstack.pdf")
    segments = segment_resume(text)
    requirement = ValidatedRequirement(
        requirement_id="R001", name=JD, priority="required", jd_evidence=JD,
        constraint=RequirementConstraint(kind="experience", minimum_years=3,
                                         operator="complex", requires_review=True),
    )
    # Model initially judged the criterion negatively. The exact PDF's
    # explicit professional-duration claim must rescue and EXPLAIN the result.
    stale = RequirementAssessment(
        requirement_id="R001", status="not_matched", unified_status="Not Found",
        reason="Experience minimum is not established.",
    )
    checked, _, changed = apply_experience_checks(
        requirements=[requirement], assessments=[stale], resume_text=text)
    assert changed
    checked = reconcile_final_assessments(requirements=[requirement], assessments=checked)
    assert checked[0].status == "matched"
    assert checked[0].unified_status == "Found"
    report = RankingReport(
        job_description_source="JD", jd_validation_mode="llm_validated",
        requirements=[requirement], yake_candidates=[],
        candidates=[CandidateResult(
            candidate_name="Candidate A", primary_score=100,
            matched_required=1, total_required=1, matched_preferred=0,
            total_preferred=0, evaluation_mode="llm_assessed",
            assessments=checked,
        )],
    )
    return report, segment_ledger(segments)


def test_experience_rescue_restores_a_human_why_not_a_stale_negative():
    report, ledger = _report_and_ledger()
    row = report.candidates[0].assessments[0]
    assert "4 years 5 months" in row.reason
    assert "professional AI/ML delivery" in row.reason
    assert "minimum of 3 years" in row.reason
    assert "professional summary" in row.reason
    assert "not established" not in row.reason.casefold()
    assert "S005" not in row.reason
    individual = reconcile_unified_candidate(report, 0, ledger)
    assert individual["Criteria"][0]["Why"] == row.reason
    assert individual["Criteria"][0]["Result"] == "Found"


def test_streamlit_individual_requirements_show_why_in_table_and_expander():
    from streamlit.testing.v1 import AppTest

    report, ledger = _report_and_ledger()

    def page(report_data, ledger):
        import streamlit as st
        from cv_ranker.schemas import RankingReport
        from cv_ranker.ui.dashboard import _candidate_evidence
        from cv_ranker.ui.unified_decisions import reconcile_unified_candidate

        report = RankingReport.model_validate(report_data)
        st.session_state["cv_source_ledgers"] = {"0": ledger}
        st.session_state["cv_final_results"] = {
            "0": reconcile_unified_candidate(report, 0, ledger)
        }
        _candidate_evidence(report)

    app = AppTest.from_function(page, args=(report.model_dump(), ledger)).run(timeout=20)
    assert not app.exception
    table = app.dataframe[0].value
    assert "Why this decision" in table.columns
    reason = table.iloc[0]["Why this decision"]
    assert "4 years 5 months of professional AI/ML delivery" in reason
    assert "minimum of 3 years" in reason
    assert "S005" not in reason
    labels = " ".join(str(item.value) for item in app.markdown)
    assert "Why this CV received its ranking" in labels
    assert "Why this decision" in labels


"""Keep the supervisor's primary view simple while retaining technical audits."""

from streamlit.testing.v1 import AppTest

from cv_ranker.schemas import (CandidateResult, RankingReport,
                               RequirementAssessment, ValidatedRequirement)


def _sample_report_and_source():
    text = "Developed Python tools for data processing."
    report = RankingReport(
        job_description_source="Python", jd_validation_mode="llm_validated",
        requirements=[ValidatedRequirement(requirement_id="R001", name="Python",
                                           priority="required", jd_evidence="Python")],
        yake_candidates=[],
        candidates=[CandidateResult(
            candidate_name="Candidate A", primary_score=100,
            matched_required=1, total_required=1,
            matched_preferred=0, total_preferred=0,
            evaluation_mode="llm_assessed",
            assessments=[RequirementAssessment(
                requirement_id="R001", status="matched", unified_status="Found",
                reason="Developed Python tools for data processing.",
                assessment_state="verified",
            )],
        )],
    )
    ledger = [{"segment_id": "S001", "text": text, "section": "experience"}]
    final = {"0": {
        "Required matched": 1, "Required total": 1, "Preferred matched": 0,
        "Preferred total": 0, "Transferable": 0, "Unverified": 0,
        "Provisional": False, "Notices": [],
        "Criteria": [{
            "ID": "R001", "Requirement": "Python", "Priority": "Required",
            "Result": "Found", "Why": "Developed Python tools for data processing.",
            "Checkpoints": [{
                "Segment": "S001", "Text": text, "Section": "experience",
                "Sources": ["Original CV"], "Validated against CV": True,
                "Why": ["Developed Python tools for data processing."],
            }],
            "Review recommended": False, "Evidence level": "Direct evidence",
            "JD source": "Python", "Kind": "skill",
        }],
    }}
    return report, ledger, final


def test_ranked_explanation_is_one_full_width_row_not_repeated_panels():
    report, ledger, final = _sample_report_and_source()

    def page(data, retained, decisions):
        import streamlit as st
        from cv_ranker.schemas import RankingReport
        from cv_ranker.ui.dashboard import _ranking

        st.session_state["cv_final_results"] = decisions
        st.session_state["cv_source_ledgers"] = {"0": retained}
        _ranking(RankingReport.model_validate(data))

    app = AppTest.from_function(
        page, args=(report.model_dump(), ledger, final)).run(timeout=20)
    assert not app.exception
    markup = "\n".join(str(item.value) for item in app.markdown)
    assert "Why candidates ranked this way" in markup
    assert markup.count('class="cv-rank-row') == 1
    assert "Candidate A" in markup
    assert "Optional · Compare the leading candidate with others" in (
        " ".join(item.label for item in app.expander))
    assert "Why every candidate received their position" not in markup


def test_reliability_status_is_only_in_technical_audit_not_main_results():
    report, ledger, final = _sample_report_and_source()

    def page(data, retained, decisions, show_technical):
        import streamlit as st
        from cv_ranker.schemas import RankingReport
        from cv_ranker.ui.dashboard import _candidate_evidence, _reasoning_audit_panel

        st.session_state["cv_final_results"] = decisions
        st.session_state["cv_source_ledgers"] = {"0": retained}
        parsed = RankingReport.model_validate(data)
        if show_technical:
            _reasoning_audit_panel(parsed)
        else:
            _candidate_evidence(parsed)

    for technical in (False, True):
        app = AppTest.from_function(
            page, args=(report.model_dump(), ledger, final, technical)).run(timeout=20)
        assert not app.exception
        text = "\n".join(str(item.value) for item in app.markdown)
        all_copy = text + "\n" + "\n".join(str(item.value) for item in app.caption)
        expanders = " ".join(item.label for item in app.expander)
        if technical:
            assert "Reasoning verification · internal audit" in expanders
            assert "structurally_valid" in all_copy
        else:
            assert "Reasoning verification" not in expanders
            assert "Reasoning reliability check" not in expanders
            assert "structurally_valid" not in all_copy
            assert "Why this CV received its ranking" in text
            assert "What helped this CV" in text
            assert "Why this decision" in text


def test_rank_explanation_escapes_uploaded_names_and_model_output(monkeypatch):
    from cv_ranker.ui import dashboard

    output = []
    monkeypatch.setattr(dashboard.st, "markdown", lambda value, **kwargs: output.append(value))
    dashboard._rank_explanation_row({
        "rank": 1, "weighted_score": 87.5,
        "candidate": "<script>alert('candidate')</script>",
        "placement_reason": "<img src=x onerror=alert(1)>",
    })
    markup = "\n".join(output)
    assert "&lt;script&gt;" in markup
    assert "&lt;img src=x onerror=alert(1)&gt;" in markup
    assert "<script>" not in markup
    assert "87.50%" in markup


def test_complete_cv_review_flag_does_not_display_provisional_warning():
    from cv_ranker.ui_support import final_leaderboard_rows

    report, ledger, finals = _sample_report_and_source()
    finals["0"]["Provisional"] = True  # legacy broad flag, even though score is complete
    finals["0"]["Criteria"][0]["Review recommended"] = True
    assert final_leaderboard_rows(report, finals)[0]["Review"] == "Review suggested (1)"

    def page(data, retained, decisions):
        import streamlit as st
        from cv_ranker.schemas import RankingReport
        from cv_ranker.ui.dashboard import _candidate_evidence

        st.session_state["cv_final_results"] = decisions
        st.session_state["cv_source_ledgers"] = {"0": retained}
        _candidate_evidence(RankingReport.model_validate(data))

    app = AppTest.from_function(
        page, args=(report.model_dump(), ledger, finals)).run(timeout=20)
    assert not app.exception
    warnings = " ".join(str(item.message) for item in app.warning)
    text = " ".join(str(item.value) for item in app.caption)
    assert "Provisional assessment" not in warnings
    assert "Human review suggested for this requirement" in text


def test_legacy_provisional_flag_does_not_downgrade_a_complete_unflagged_cv():
    from cv_ranker.ui_support import final_leaderboard_rows

    report, _, finals = _sample_report_and_source()
    finals["0"]["Provisional"] = True  # an earlier nonblocking pipeline notice
    finals["0"]["Criteria"][0]["Review recommended"] = False
    assert final_leaderboard_rows(report, finals)[0]["Review"] == "Complete"


def test_review_export_is_consistent_with_completed_candidate_status():
    import csv
    import io
    import json
    from zipfile import ZipFile

    from cv_ranker.report_bundle import complete_results_zip
    from cv_ranker.weighted_scoring import ScoreWeights

    report, ledger, finals = _sample_report_and_source()
    finals["0"]["Provisional"] = True
    finals["0"]["Criteria"][0]["Review recommended"] = True
    with ZipFile(io.BytesIO(complete_results_zip(
        report, ScoreWeights(), final_results=finals,
        source_ledgers={"0": ledger}))) as archive:
        summary = list(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
        detail = json.loads(archive.read("candidates/candidate_001_results.json"))
        assert summary[0]["Review"] == "Review suggested (1)"
        assert detail["weighted_result"]["review"] == "Review suggested (1)"
        # The original legacy flag is retained to avoid breaking older readers.
        assert detail["final_decisions"]["Provisional"] is True

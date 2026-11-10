"""JD review is an actual scoring gate, not a decorative preview."""
from pathlib import Path

import pytest

from cv_ranker.config import Settings
from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
from cv_ranker.pipeline import CVRanker
from cv_ranker.schemas import JDReviewDraft, RequirementConstraint, ValidatedRequirement
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.schemas import CandidateResult, RankingReport, RequirementAssessment
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import _retain_negative_review_checkpoints


JD_TEXT = ("Required skills:\nPython\nSQL\n"
           "Preferred skills:\nDocker\n")


def _draft():
    return JDReviewDraft(
        jd_sha256="placeholder", yake_candidates=[], jd_validation_mode="llm_validated",
        requirements=[
            ValidatedRequirement(requirement_id="R001", name="Python", priority="required",
                                 jd_evidence="Python", constraint=RequirementConstraint(
                                     kind="skill", origin="source_rules", requires_review=False)),
            ValidatedRequirement(requirement_id="R002", name="Docker", priority="preferred",
                                 jd_evidence="Docker", constraint=RequirementConstraint(
                                     kind="skill", origin="source_rules", requires_review=False)),
        ],
    )


def test_review_requires_explicit_approval_and_source_grounding():
    draft = _draft()
    rows = editable_jd_rows(draft)
    rows[0]["Priority"] = "preferred"
    reviewed = approve_jd_rows(draft=draft, rows=rows,
                               jd_text=JD_TEXT, max_requirements=10)
    assert reviewed.approved and reviewed.edited
    assert reviewed.requirements[0].priority == "preferred"
    assert not draft.approved
    rows[0]["JD source"] = "Invented credential requirement"
    with pytest.raises(ValueError, match="actual uploaded JD"):
        approve_jd_rows(draft=draft, rows=rows,
                        jd_text=JD_TEXT, max_requirements=10)


def test_reviewer_can_add_and_remove_frozen_jd_rows():
    draft = _draft()
    rows = editable_jd_rows(draft)
    rows.pop(1)
    rows.append({"ID": "", "Priority": "required", "Requirement": "SQL",
                 "Type": "skill", "JD source": "SQL"})
    reviewed = approve_jd_rows(draft=draft, rows=rows,
                               jd_text=JD_TEXT, max_requirements=10)
    assert [r.requirement_id for r in reviewed.requirements] == ["R001", "R003"]
    assert [r.name for r in reviewed.requirements] == ["Python", "SQL"]
    assert reviewed.requirements[1].constraint.kind == "skill"


def test_approved_jd_is_consumed_without_second_extraction(tmp_path: Path, monkeypatch):
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text(JD_TEXT, encoding="utf-8")
    cv_path = tmp_path / "candidate.txt"
    cv_path.write_text("Skills: Python, SQL", encoding="utf-8")
    ranker = CVRanker(settings=Settings(), use_llm=False)
    prepared = ranker.prepare_jd_review(jd_path)
    assert prepared.requirements
    approved = approve_jd_rows(draft=prepared,
                               rows=editable_jd_rows(prepared),
                               jd_text=JD_TEXT, max_requirements=100)

    def should_not_reextract(*args, **kwargs):
        raise AssertionError("JD was re-extracted after human approval")
    monkeypatch.setattr(ranker, "prepare_jd_review", should_not_reextract)
    report = ranker.run(jd_path, [cv_path], approved_jd=approved)
    assert report.jd_review_approved
    assert [r.model_dump() for r in report.requirements] == [
        r.model_dump() for r in approved.requirements]
    with pytest.raises(ValueError, match="require reviewer approval"):
        ranker.run(jd_path, [cv_path], approved_jd=prepared)


def test_review_invalidation_when_source_changes(tmp_path: Path):
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text(JD_TEXT, encoding="utf-8")
    ranker = CVRanker(settings=Settings(), use_llm=False)
    draft = ranker.prepare_jd_review(jd_path)
    approved = approve_jd_rows(draft=draft, rows=editable_jd_rows(draft),
                               jd_text=JD_TEXT, max_requirements=100)
    jd_path.write_text(JD_TEXT + "\nKubernetes", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after approval"):
        ranker.run(jd_path, [], approved_jd=approved)


def test_negative_review_context_is_visible_without_internal_omission_text():
    req = _draft().requirements[0]
    source = ResumeSegment("S007", "skills", "Not familiar with Python")
    row = _retain_negative_review_checkpoints(
        req, RequirementAssessment(requirement_id="R001", status="not_matched",
                                   unified_status="Not Found", reason="The candidate explicitly denies Python."),
        {"S007": source}, ["S007"])
    candidate = CandidateResult(candidate_name="CV", primary_score=0,
                                assessments=[row])
    report = RankingReport(job_description_source="jd.txt", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[req], candidates=[candidate])
    final = reconcile_unified_candidate(report, 0, [{"segment_id": "S007",
        "section": "skills", "text": source.text}])
    assert final["Criteria"][0]["Why"] == "The candidate explicitly denies Python."
    assert final["Criteria"][0]["Checkpoints"][0]["Segment"] == "S007"
    assert "omitted" not in str(final["Criteria"][0])


def test_streamlit_jd_editor_renders_and_freezes_approved_rows():
    from streamlit.testing.v1 import AppTest

    def page(draft_data, jd_text):
        import streamlit as st
        from cv_ranker.ui import dashboard
        from cv_ranker.config import Settings
        if "test_jd_pending" not in st.session_state:
            st.session_state["test_jd_pending"] = {
                "draft": draft_data, "source_text": jd_text,
                "approved": None, "revision": 1,
            }
        dashboard._review_jd_panel(Settings(), st.session_state["test_jd_pending"])

    # Full-suite Streamlit initialization can exceed the runner's default 3 s.
    app = AppTest.from_function(page, args=(_draft().model_dump(), JD_TEXT)).run(timeout=12)
    assert not app.exception
    app.button(key="cv_jd_freeze_approval").click().run(timeout=12)
    assert not app.exception
    assert app.session_state["test_jd_pending"]["approved"]["approved"] is True

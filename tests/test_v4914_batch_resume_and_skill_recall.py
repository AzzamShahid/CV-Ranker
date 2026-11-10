"""Bounded-recovery checkpoint identity and misread performed-skill evidence."""

from cv_ranker.config import Settings
from cv_ranker.resume import assessment_context_key
from cv_ranker.schemas import (RequirementAssessment, RequirementConstraint,
                               ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.ui import dashboard
from cv_ranker.unified import (FINAL_ADJUDICATION_PROMPT, UNIFIED_PROMPT,
                               _needs_independent_overlap_review)


def _medical_requirement():
    return ValidatedRequirement(
        requirement_id="R013", name="Medical imaging", priority="preferred",
        jd_evidence="Medical imaging",
        constraint=RequirementConstraint(kind="skill", operator="single",
                                         origin="source_rules"))


def test_completed_research_pilot_quoted_by_model_triggers_semantic_recheck():
    segment = ResumeSegment("S031", "projects", (
        "Designed a lightweight medical-image triage research pilot, "
        "evaluated on public data rather than in clinical use."))
    row = RequirementAssessment(
        requirement_id="R013", status="not_matched", unified_status="Not Found",
        reason=("The CV mentions 'medical-image triage research pilot' "
                "but does not show core production experience."))
    assert _needs_independent_overlap_review(
        _medical_requirement(), row, {segment.segment_id: segment}, segment.text)


def test_future_learning_quote_cannot_trigger_recall_as_completed_work():
    segment = ResumeSegment("S031", "projects", (
        "Plans to learn medical-image triage research pilot methods next year."))
    row = RequirementAssessment(
        requirement_id="R013", status="not_matched", unified_status="Not Found",
        reason="The candidate mentions 'medical-image triage research pilot' only as a future plan.")
    assert not _needs_independent_overlap_review(
        _medical_requirement(), row, {segment.segment_id: segment}, segment.text)


def test_pasted_jd_identity_matches_exact_disk_bytes_even_on_windows(monkeypatch):
    class Uploaded:
        name = "candidate.txt"

        def getvalue(self):
            return b"Completed a relevant applied research pilot."

    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test")
    jd = "Required:\nMedical imaging\nPreferred:\nPython\n"
    upload = Uploaded()
    input_identity = dashboard._uploaded_identity(
        settings, True, method="Paste job description", jd_text=jd,
        jd_upload=None, resumes=[upload], alias=None, gate=None)
    captured = {}

    def fake_rank(jd_path, resumes, effective, use_llm, label, **kwargs):
        captured["bytes"] = jd_path.read_bytes()
        captured["key"] = assessment_context_key(effective, jd_bytes=captured["bytes"],
                                                  use_llm=use_llm)
        return "report"

    monkeypatch.setattr(dashboard, "_rank", fake_rank)
    assert dashboard._run_uploaded_inputs(
        settings, True, True, method="Paste job description", jd_text=jd,
        jd_upload=None, resumes=[upload], alias=None, gate=None,
        resume=False) == "report"
    assert captured["bytes"] == jd.encode("utf-8")
    assert captured["key"] == input_identity[0]


def test_skill_only_prompt_does_not_invent_production_requirement():
    assert "SKILL-ONLY SCOPE" in UNIFIED_PROMPT
    assert "completed relevant" in FINAL_ADJUDICATION_PROMPT

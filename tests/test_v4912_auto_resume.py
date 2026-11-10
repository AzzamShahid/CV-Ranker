"""Automatic recovery must never silently change inputs or run forever."""

from concurrent.futures import Future
from contextlib import nullcontext

import pytest

from cv_ranker.config import Settings
from cv_ranker.resume import candidate_resume_key
from cv_ranker.schemas import (CandidateResult, JDReviewDraft, RankingReport,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.ui import dashboard


class Upload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data

    def getvalue(self):
        return self.data


def _fixture(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test")
    upload = Upload("candidate.txt", b"Professional Python implementation and API delivery work.")
    jd_text = "Required: Python programming and integration experience."
    req = ValidatedRequirement(requirement_id="R001", name="Python", priority="required",
                               jd_evidence="Python")
    partial = CandidateResult(candidate_name=upload.name, primary_score=None,
                              evaluation_mode="failed", assessments=[
                                  RequirementAssessment(requirement_id="R001",
                                                        status="uncertain",
                                                        assessment_state="unverified",
                                                        unified_status="Unverified")])
    report = RankingReport(job_description_source="uploaded://jd", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[req], candidates=[partial])
    approved = JDReviewDraft(jd_sha256=jd_source_sha256(jd_text),
                             yake_candidates=[], requirements=[req],
                             jd_validation_mode="llm_validated", approved=True)
    identity = dashboard._uploaded_identity(
        settings, True, method="Paste job description", jd_text=jd_text,
        jd_upload=None, resumes=[upload], alias=None, gate=None,
        approved_jd=approved)
    session = {
        "cv_auto_resume_enabled": True,
        "cv_jd_source_mode": "Paste job description",
        "cv_jd_text": jd_text,
        "cv_jd_review_pending": {"kind": "upload", "approved": approved.model_dump()},
        "resume_files": [upload],
        "cv_ranking_report": report.model_dump(),
        "cv_resume_cache": {"context_key": identity[0], "report": report.model_dump(),
                            "candidates": {candidate_resume_key(upload.name, upload.data):
                                           partial.model_dump()}},
    }
    calls = {"rerun": 0, "warning": []}
    monkeypatch.setattr(dashboard.st, "session_state", session)
    monkeypatch.setattr(dashboard.st, "spinner", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(dashboard.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard.st, "warning", lambda message, **kwargs:
                        calls["warning"].append(message))
    monkeypatch.setattr(dashboard.st, "rerun", lambda *args, **kwargs:
                        calls.__setitem__("rerun", calls["rerun"] + 1))
    class ImmediatePool:
        def submit(self, fn, *args):
            future = Future()
            try:
                future.set_result(fn(*args))
            except Exception as exc:
                future.set_exception(exc)
            return future

    monkeypatch.setattr(dashboard, "_RECOVERY_POOL", ImmediatePool())
    def publish(artifacts, *_args):
        session["cv_ranking_report"] = artifacts["report"].model_dump()
    monkeypatch.setattr(dashboard, "_publish_rank_artifacts", publish)
    return settings, upload, report, identity, session, calls


def _arm(session, identity):
    session["cv_auto_resume_state"] = {
        "context_key": identity[0], "candidate_keys": identity[1],
        "attempts": 0, "rate_limit_streak": 0,
        "no_progress_streak": 0, "next_due": 0.0, "running": False,
    }


def _artifacts(report, *, rate_limited=False, retry_after=None):
    return {"report": report,
            "request_metrics": {"http_429_count": 1 if rate_limited else 0,
                                "provider_retry_after_seconds": retry_after},
            "provider_hard_stop": False, "cooldown_seconds": 60.0 if rate_limited else 0.0}


def test_auto_resume_completes_unchanged_batch_without_user_click(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    recorded = []

    def recovered(*args):
        recorded.append(args)
        assert args[0].openrouter_max_requests_per_run == settings.openrouter_max_requests_per_run
        return _artifacts(report.model_copy(update={"candidates": [report.candidates[0].model_copy(update={
            "primary_score": 100.0,
        })]}))

    monkeypatch.setattr(dashboard, "_background_resume", recovered)
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert isinstance(session["cv_auto_resume_future"], Future)
    assert calls["rerun"] == 0
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert len(recorded) == 1
    assert "cv_auto_resume_state" not in session
    assert calls["rerun"] == 1
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert len(recorded) == 1  # Recovered candidates do not trigger another call.


def test_auto_resume_cancels_if_original_cv_changes(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    upload.data = b"Replaced resume text, which MUST not inherit previous assessments."
    monkeypatch.setattr(dashboard, "_background_resume", lambda *a, **k:
                        pytest.fail("Automatic resume called the model for changed files"))
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert "cv_auto_resume_state" not in session
    assert any("changed" in message for message in calls["warning"])


def test_auto_resume_stops_after_two_paid_no_progress_attempts_without_429(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    attempted = []
    monkeypatch.setattr(dashboard, "_background_resume",
                        lambda *a: (attempted.append(a) or _artifacts(report)))
    for _ in range(2):
        session["cv_auto_resume_state"]["next_due"] = 0.0
        dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
        dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert session["cv_auto_resume_state"]["attempts"] == 2
    assert session["cv_auto_resume_state"]["paused"] is True
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert len(attempted) == 2


def test_auto_resume_pauses_after_repeated_http_429_without_progress(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    attempts = []

    def retry(*args):
        attempts.append(args)
        return _artifacts(report, rate_limited=True, retry_after=500.0)

    monkeypatch.setattr(dashboard, "_background_resume", retry)
    for idx in range(3):
        session["cv_auto_resume_state"]["next_due"] = 0.0
        dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
        dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
        assert session["cv_auto_resume_state"]["rate_limit_streak"] == idx + 1
        if idx < 2:
            assert session["cv_auto_resume_state"].get("paused") is not True
            assert session["cv_auto_resume_state"]["next_due"] > 0.0
    assert session["cv_auto_resume_state"]["paused"] is True
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert len(attempts) == 3
    assert any("429" in message for message in calls["warning"])


def test_auto_resume_refuses_structural_fallback_frozen_jd(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    fallback = report.model_copy(update={"jd_validation_mode": "fallback_structural_after_llm"})
    notice = dashboard._arm_auto_resume(fallback, settings, True, identity, True)
    assert "structural fallback" in notice
    assert "cv_auto_resume_state" not in session


def test_manual_analyze_may_reuse_only_the_exact_prior_candidate_set(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    assert dashboard._checkpoint_matches(identity, session["cv_resume_cache"])
    changed_cv = (identity[0], (candidate_resume_key("candidate.txt", b"changed"),))
    assert not dashboard._checkpoint_matches(changed_cv, session["cv_resume_cache"])
    extra_cv = (identity[0], identity[1] + (candidate_resume_key("new.pdf", b"other"),))
    assert not dashboard._checkpoint_matches(extra_cv, session["cv_resume_cache"])
    changed_jd = ("different-context", identity[1])
    assert not dashboard._checkpoint_matches(changed_jd, session["cv_resume_cache"])

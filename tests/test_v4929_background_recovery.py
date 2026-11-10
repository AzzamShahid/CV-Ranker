"""V4.9.29: worker isolation, bounded retries and no stale-result publication."""

from concurrent.futures import Future
from pathlib import Path

from cv_ranker.config import Settings
from cv_ranker.ui import dashboard

from test_v4912_auto_resume import _artifacts, _arm, _fixture


def test_background_worker_uses_snapshotted_bytes_and_no_streamlit(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test")
    snapshot = {
        "method": "Paste job description", "jd_text": "Original job description text",
        "jd_upload": None,
        "resumes": [{"name": "candidate.txt", "data": b"Original candidate"}],
        "alias": None, "gate": None,
    }

    def isolated_core(jd, paths, actual_settings, use_llm, **kwargs):
        assert Path(jd).read_bytes() == b"Original job description text"
        assert paths[0].read_bytes() == b"Original candidate"
        assert actual_settings.llm_provider == "openrouter"
        assert use_llm is True and kwargs["resume"] is True
        assert kwargs["previous"] == {"saved": "checkpoint"}
        return {"isolated": True}

    monkeypatch.setattr(dashboard, "_rank_core", isolated_core)
    assert dashboard._background_resume(
        settings, None, snapshot, {"saved": "checkpoint"}) == {"isolated": True}


def test_pending_future_does_not_launch_duplicate_requests(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    pending = Future()
    session["cv_auto_resume_future"] = pending
    session["cv_auto_resume_state"]["running"] = True
    monkeypatch.setattr(dashboard, "_background_resume", lambda *a: 1 / 0)
    for _ in range(3):
        dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert session["cv_auto_resume_future"] is pending
    assert calls["rerun"] == 0


def test_worker_result_discarded_when_a_cv_changes_during_execution(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    pending = Future()
    pending.set_result(_artifacts(report))
    session["cv_auto_resume_future"] = pending
    upload.data = b"Replaced after the background worker began."

    def forbidden(*args):
        raise AssertionError("A stale worker must not publish the prior assessment")

    monkeypatch.setattr(dashboard, "_publish_rank_artifacts", forbidden)
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert "cv_auto_resume_state" not in session
    assert any("changed" in message for message in calls["warning"])


def test_worker_result_discarded_if_partial_report_was_replaced(monkeypatch):
    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    _arm(session, identity)
    state = session["cv_auto_resume_state"]
    state["checkpoint_digest"] = dashboard._checkpoint_digest(session["cv_resume_cache"])
    done = Future()
    done.set_result(_artifacts(report))
    session["cv_auto_resume_future"] = done
    # Same uploaded files and JD, but different checkpoint content.
    session["cv_resume_cache"]["report"]["warnings"] = ["different restored report"]
    monkeypatch.setattr(dashboard, "_publish_rank_artifacts", lambda *a:
                        (_ for _ in ()).throw(AssertionError("stale report published")))
    dashboard._automatic_resume_fragment.__wrapped__(settings, True, True)
    assert "cv_auto_resume_state" not in session
    assert any("replaced" in text for text in calls["warning"])


def test_retry_after_over_one_hour_pauses_without_busy_polling():
    from cv_ranker.schemas import CandidateResult, RankingReport

    partial = RankingReport(
        job_description_source="jd", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[],
        candidates=[CandidateResult(candidate_name="a")])
    state = {"attempts": 0, "rate_limit_streak": 0, "no_progress_streak": 0}
    updated = dashboard._advance_recovery_state(
        state, partial, previous_complete=0,
        metrics={"http_429_count": 1, "provider_retry_after_seconds": 9000},
        provider_hard_stop=False, cooldown_seconds=9000)
    assert updated["paused"] is True
    assert "one hour" in updated["pause_reason"]
    assert state["attempts"] == 0  # No mutation of the original checkpoint.


def test_mixed_rate_limit_and_invalid_results_eventually_pause():
    from cv_ranker.schemas import CandidateResult, RankingReport

    partial = RankingReport(
        job_description_source="jd", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[],
        candidates=[CandidateResult(candidate_name="a")])
    state = {"attempts": 0, "rate_limit_streak": 0, "no_progress_streak": 0}
    for limited in (True, False, True):
        state = dashboard._advance_recovery_state(
            state, partial, previous_complete=0,
            metrics={"http_429_count": int(limited)},
            provider_hard_stop=False, cooldown_seconds=0)
    assert state["paused"] is True
    assert state["no_progress_streak"] == 3

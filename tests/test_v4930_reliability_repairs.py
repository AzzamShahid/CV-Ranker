"""Offline regressions for two-CV recovery and bounded cloud requests."""

import json
from concurrent.futures import Future
from dataclasses import replace

import pytest
from pydantic import BaseModel

from cv_ranker.config import Settings
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.llm import (LLMError, ModelOutputTruncatedError,
                           OpenRouterHTTPError, OpenRouterStructuredLLM)
from cv_ranker.pipeline import CVRanker
from cv_ranker.resume import (assessment_context_key, candidate_resume_key,
                              candidate_resume_keys)
from cv_ranker.schemas import (CandidateResult, RankingReport,
                                RequirementAssessment, ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.ui.dashboard import _advance_recovery_state, _rank_core


def _req(rid, name):
    return ValidatedRequirement(requirement_id=rid, name=name,
                                priority="required", jd_evidence=name)


def _row(rid, *, verified=True):
    return RequirementAssessment(
        requirement_id=rid,
        status="matched" if verified else "uncertain",
        unified_status="Found" if verified else "Unverified",
        assessment_state="verified" if verified else "unverified",
    )


@pytest.mark.parametrize("candidate_count", [2, 3])
def test_multi_cv_resume_only_requests_the_single_unverified_requirement(
        monkeypatch, tmp_path, candidate_count):
    jd = tmp_path / "jd.txt"
    jd.write_text("Required: Python and PostgreSQL", encoding="utf-8")
    files = [tmp_path / f"candidate_{index}.txt"
             for index in range(candidate_count)]
    for file in files:
        file.write_text("Built Python and PostgreSQL services.", encoding="utf-8")
    reqs = [_req("R001", "Python"), _req("R002", "PostgreSQL")]
    completed = score_candidate(
        candidate_name=files[0].name, requirements=reqs,
        assessments=[_row("R001"), _row("R002")],
        evaluation_mode="llm_assessed", errors=[])
    partial = score_candidate(
        candidate_name=files[-1].name, requirements=reqs,
        assessments=[_row("R001"), _row("R002", verified=False)],
        evaluation_mode="failed", errors=[])
    report = RankingReport(
        job_description_source="jd.txt", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=reqs,
        candidates=[completed] * (candidate_count - 1) + [partial],
        jd_sha256=jd_source_sha256(jd.read_text(encoding="utf-8")))

    class FakeLLM:
        disabled_reason = None
        logical_calls = 0
        http_attempts = 0
        token_usage = {}

        def __init__(self, settings):
            pass

    class FakeMetrics:
        warnings = []

        def public(self):
            return {"llm_calls": 1, "correction_calls": 0,
                    "final_verification_calls": 0}

    class FakeEngine:
        calls = []

        def __init__(self, *args, **kwargs):
            pass

        def assess(self, requirements, segments, resume_text, *, candidate_id,
                   context_requirements=None, known_assessments=None):
            self.calls.append((tuple(req.requirement_id for req in requirements),
                               tuple(sorted((known_assessments or {}).keys())),
                               len(context_requirements or requirements)))
            return [_row("R002")], FakeMetrics()

        def close(self):
            pass

    monkeypatch.setattr("cv_ranker.pipeline.StructuredLLM", FakeLLM)
    monkeypatch.setattr("cv_ranker.unified.UnifiedEvidenceEngine", FakeEngine)
    ranker = CVRanker(settings=Settings(llm_provider="ollama"),
                      use_llm=True, unified=True)
    keys = [candidate_resume_key(file.name, file.read_bytes()) for file in files]
    result = ranker.run(jd, files, resume_report=report,
                        resume_candidates=dict(zip(
                            keys, [completed] * (candidate_count - 1) + [partial])))
    assert FakeEngine.calls == [(('R002',), ('R001',), 2)]
    assert len(result.candidates) == candidate_count
    assert all(candidate.primary_score == 100.0 for candidate in result.candidates)
    assert ranker.request_metrics["reused_completed_candidates"] == candidate_count - 1
    assert ranker.request_metrics["reassessed_candidates"] == 1


def test_identical_uploads_have_independent_checkpoint_keys():
    pair = [("same.pdf", b"same CV"), ("same.pdf", b"same CV")]
    keys = candidate_resume_keys(pair)
    assert len(keys) == len(set(keys)) == 2
    assert keys == candidate_resume_keys(pair)
    assert keys[0] == candidate_resume_key(*pair[0])


def test_request_budget_is_transport_only_for_checkpoint_identity():
    settings = Settings(llm_provider="ollama")
    assert assessment_context_key(settings, jd_bytes=b"JD") == assessment_context_key(
        replace(settings, openrouter_max_requests_per_assessment=250), jd_bytes=b"JD")


def test_exhausted_checkpoint_budget_prevents_new_assessment(tmp_path):
    jd = tmp_path / "jd.txt"
    jd.write_text("Required: Python", encoding="utf-8")
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_assessment=2)
    prior = RankingReport(job_description_source="jd.txt",
                          jd_validation_mode="llm_validated", yake_candidates=[],
                          requirements=[_req("R001", "Python")],
                          candidates=[CandidateResult(candidate_name="a")])
    saved = {"context_key": assessment_context_key(settings, jd_bytes=jd.read_bytes()),
             "report": prior.model_dump(), "candidates": {},
             "assessment_http_attempts_total": 2}
    with pytest.raises(ValueError, match="request budget exhausted"):
        _rank_core(jd, [], settings, True, uploaded=False, resume=True,
                   approved_jd=None, previous=saved)


def test_resumed_run_enforces_remaining_budget_and_accumulates_requests(
        monkeypatch, tmp_path):
    jd = tmp_path / "jd.txt"
    jd.write_text("Required: Python", encoding="utf-8")
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_requests_per_assessment=10)
    original = RankingReport(
        job_description_source="jd", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[_req("R001", "Python")],
        candidates=[])
    saved = {"context_key": assessment_context_key(settings, jd_bytes=jd.read_bytes()),
             "report": original.model_dump(), "candidates": {},
             "assessment_http_attempts_total": 3}

    class FakeRanker:
        def __init__(self, **kwargs):
            assert kwargs["settings"].openrouter_max_requests_per_run == 7
            self.source_ledgers = {}
            self.unified_metrics = {}
            self.request_metrics = {"actual_model_request_attempts": 2}
            self.llm = None

        def run(self, *_args, **_kwargs):
            return original

    monkeypatch.setattr("cv_ranker.ui.dashboard.CVRanker", FakeRanker)
    artifacts = _rank_core(jd, [], settings, True, uploaded=False, resume=True,
                           approved_jd=None, previous=saved)
    assert artifacts["request_metrics"]["assessment_http_attempts_cumulative"] == 5
    assert artifacts["request_metrics"]["assessment_http_attempts_remaining"] == 5
    assert artifacts["resume_cache"]["assessment_http_attempts_total"] == 5


class _Answer(BaseModel):
    answer: str


def test_429_with_retry_after_above_wait_cap_is_not_retried_early(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        openrouter_max_retry_after_seconds=45, llm_retries=2)
    client = OpenRouterStructuredLLM(settings)
    calls = []
    monkeypatch.setattr(client, "_post_chat", lambda *_: (
        calls.append(1) or (_ for _ in ()).throw(OpenRouterHTTPError(429, 50))))
    monkeypatch.setattr("cv_ranker.llm.time.sleep", lambda *_:
                        pytest.fail("Never shorten a provider Retry-After"))
    with pytest.raises(LLMError, match="429"):
        client.invoke_structured(system_prompt="Brief", user_prompt="Reply",
                                 schema=_Answer)
    assert len(calls) == 1
    assert "429" in client.disabled_reason


def test_503_opens_circuit_and_skips_subsequent_cv_requests(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test",
                        llm_retries=0)
    client = OpenRouterStructuredLLM(settings)
    calls = []
    monkeypatch.setattr(client, "_post_chat", lambda *_: (
        calls.append(1) or (_ for _ in ()).throw(OpenRouterHTTPError(503))))
    for _ in range(2):
        with pytest.raises(LLMError):
            client.invoke_structured(system_prompt="Brief", user_prompt="Reply",
                                     schema=_Answer)
    assert len(calls) == 1
    assert "503" in client.disabled_reason


def test_truncated_response_is_not_repeated_with_same_token_budget(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-test")
    client = OpenRouterStructuredLLM(settings)
    calls = []

    def truncated(*_):
        calls.append(1)
        return {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}

    monkeypatch.setattr(client, "_post_chat", truncated)
    with pytest.raises(ModelOutputTruncatedError):
        client.invoke_structured(system_prompt="Brief", user_prompt="Reply", schema=_Answer)
    assert len(calls) == 1


def test_partial_requirement_verification_resets_no_progress_streak():
    report = RankingReport(
        job_description_source="jd", jd_validation_mode="llm_validated",
        yake_candidates=[], requirements=[_req("R001", "Python"),
                                           _req("R002", "PostgreSQL")],
        candidates=[CandidateResult(
            candidate_name="a", primary_score=None,
            assessments=[_row("R001"), _row("R002", verified=False)])])
    state = _advance_recovery_state(
        {"attempts": 1, "no_progress_streak": 1, "rate_limit_streak": 0},
        report, previous_complete=0, previous_verified=0,
        metrics={"http_429_count": 0}, provider_hard_stop=False,
        cooldown_seconds=0)
    assert not state.get("paused", False)
    assert state["no_progress_streak"] == 0


def test_truncated_group_is_split_before_another_model_attempt(tmp_path):
    from cv_ranker.unified import UnifiedEvidenceEngine
    from test_v48_unified import FakeEncoder, FakeLLM, _fixtures

    class TruncateLargeGroup(FakeLLM):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            payload = json.loads(user_prompt)
            if len(payload.get("requirements", [])) > 1:
                self.calls += 1
                self.payloads.append(payload)
                raise ModelOutputTruncatedError("provider output truncated")
            return super().invoke_structured(system_prompt=system_prompt,
                                             user_prompt=user_prompt, schema=schema)

    reqs, segments = _fixtures()
    provider = TruncateLargeGroup()
    with UnifiedEvidenceEngine(
            Settings(llm_provider="ollama"), provider,
            cache_path=tmp_path / "vectors.db", encoder=FakeEncoder()) as engine:
        assessments, metrics = engine.assess(
            reqs, segments, "\n".join(s.text for s in segments),
            candidate_id="truncation_recovery")
    assert [len(payload["requirements"]) for payload in provider.payloads] == [2, 1, 1]
    assert [row.assessment_state for row in assessments] == ["verified", "verified"]
    assert metrics.llm_calls == 3


def test_initial_worker_uses_approved_jd_without_resume_checkpoint(monkeypatch):
    from cv_ranker.ui import dashboard

    snapshot = {
        "method": "Paste job description", "jd_text": "Required Python developer",
        "jd_upload": None, "resumes": [{"name": "candidate.txt", "data": b"Python"}],
        "alias": None, "gate": None,
    }

    def fake_core(jd, cv_paths, settings, use_llm, **kwargs):
        assert jd.read_text(encoding="utf-8") == snapshot["jd_text"]
        assert cv_paths[0].read_bytes() == b"Python"
        assert kwargs["resume"] is False and kwargs["previous"] is None
        return {"completed": True}

    monkeypatch.setattr(dashboard, "_rank_core", fake_core)
    assert dashboard._background_resume(
        Settings(llm_provider="ollama"), None, snapshot, None) == {"completed": True}


def test_manual_background_future_is_published_once_on_ui_thread(monkeypatch):
    from cv_ranker.ui import dashboard
    from test_v4912_auto_resume import _artifacts, _fixture

    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    future = Future()
    session["cv_manual_assessment_state"] = {
        "context_key": identity[0], "candidate_keys": identity[1],
        "checkpoint_digest": None,
    }
    session["cv_manual_assessment_future"] = future
    dashboard._manual_assessment_fragment.__wrapped__(settings, True)
    assert calls["rerun"] == 0
    assert session["cv_manual_assessment_future"] is future

    future.set_result(_artifacts(report))
    dashboard._manual_assessment_fragment.__wrapped__(settings, True)
    assert "cv_manual_assessment_state" not in session
    assert "cv_manual_assessment_future" not in session
    assert calls["rerun"] == 1
    dashboard._manual_assessment_fragment.__wrapped__(settings, True)
    assert calls["rerun"] == 1


def test_manual_background_result_is_discarded_after_cv_edit(monkeypatch):
    from cv_ranker.ui import dashboard
    from test_v4912_auto_resume import _artifacts, _fixture

    settings, upload, report, identity, session, calls = _fixture(monkeypatch)
    future = Future()
    future.set_result(_artifacts(report))
    session["cv_manual_assessment_state"] = {
        "context_key": identity[0], "candidate_keys": identity[1],
        "checkpoint_digest": None,
    }
    session["cv_manual_assessment_future"] = future
    upload.data = b"CV changed while the model was running"
    dashboard._manual_assessment_fragment.__wrapped__(settings, True)
    assert "cv_manual_assessment_future" not in session
    assert calls["rerun"] == 0
    assert any("changed" in warning for warning in calls["warning"])

"""Regression cases for late failures on the second of multiple CVs.

No network requests or real applicant data are used.
"""

import json

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.llm import (LLMError, ModelStructuredResponseError,
                           OpenRouterHTTPError, OpenRouterStructuredLLM)
from cv_ranker.schemas import ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse


class LocalFakeEncoder:
    fingerprint = "v4933-no-network"

    def embed_documents(self, texts):
        return np.asarray([[1.0, 0.0, 0.0] for _ in texts], dtype=np.float32)

    def embed_queries(self, texts):
        return np.asarray([[1.0, 0.0, 0.0] for _ in texts], dtype=np.float32)


def fixture_requirements():
    return [ValidatedRequirement(
        requirement_id=f"R{n:03d}", name=name,
        priority="required", jd_evidence=name)
        for n, name in enumerate(("Python", "LangGraph", "Firebase"), 1)]


def fixture_segments():
    return [ResumeSegment(segment_id="S001", section="skills",
                          text="Python, FastAPI", source_lines=(1,)),
            ResumeSegment(segment_id="S002", section="projects",
                          text="Built a web service using documented REST endpoints.",
                          source_lines=(2,))]


class LateFailureLLM:
    disabled_reason = None

    def __init__(self):
        self.fail_second = False
        self.calls = []

    def prompt_fits(self, *args):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        ids = tuple(req["id"] for req in json.loads(user_prompt)["requirements"])
        self.calls.append(ids)
        if self.fail_second and "R002" in ids:
            raise LLMError("OpenRouter HTTP 503: provider temporarily unavailable")
        return UnifiedResponse(assessments=[
            UnifiedItem(requirement_id=rid,
                        decision="found" if rid == "R001" else "not_found",
                        evidence_ids=["S001"] if rid == "R001" else ["S002"],
                        relation="direct" if rid == "R001" else "absent",
                        matched_term="Python" if rid == "R001" else None,
                        reason=("The candidate directly lists Python in their skills."
                                if rid == "R001" else
                                "The cited service does not establish this particular requirement."))
            for rid in ids])


def test_second_cv_failure_preserves_earlier_batch_and_resumes_only_pending(tmp_path):
    requirements = fixture_requirements()
    segments = fixture_segments()
    llm = LateFailureLLM()
    engine = UnifiedEvidenceEngine(
        Settings(llm_provider="ollama", assessment_batch_size=1), llm,
        cache_path=tmp_path / "vectors.db", encoder=LocalFakeEncoder())
    try:
        first, first_metrics = engine.assess(requirements, segments,
                                             "Python, FastAPI", candidate_id="cv_1")
        assert all(row.assessment_state == "verified" for row in first)
        assert first_metrics.unresolved_criteria == 0

        llm.fail_second = True
        second, metrics = engine.assess(requirements, segments,
                                         "Python, FastAPI", candidate_id="cv_2")
        assert len(second) == 3
        assert second[0].assessment_state == "verified"
        assert second[0].unified_status == "Found"
        assert [row.assessment_state for row in second[1:]] == ["unverified", "unverified"]
        assert metrics.interrupted_requirement_ids == ["R002", "R003"]
        assert "503" in metrics.interrupted_cause
        assert llm.calls[-2:] == [("R001",), ("R002",)]

        # Recovery reuses the finished R001 result, never pays for R001 again.
        llm.fail_second = False
        previous_calls = len(llm.calls)
        recovered, resumed_metrics = engine.assess(
            requirements[1:], segments, "Python, FastAPI", candidate_id="cv_2",
            context_requirements=requirements,
            known_assessments={"R001": second[0]})
        assert llm.calls[previous_calls:] == [("R002",), ("R003",)]
        assert all(row.assessment_state == "verified" for row in recovered)
        assert resumed_metrics.unresolved_criteria == 0
    finally:
        engine.close()


def test_repeated_structured_output_failure_splits_once_and_finishes(tmp_path):
    class MalformedGroupedLLM(LateFailureLLM):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            ids = tuple(req["id"] for req in json.loads(user_prompt)["requirements"])
            if len(ids) > 1:
                self.calls.append(ids)
                raise ModelStructuredResponseError("structured JSON did not validate")
            return super().invoke_structured(system_prompt=system_prompt,
                                             user_prompt=user_prompt, schema=schema)

    llm = MalformedGroupedLLM()
    engine = UnifiedEvidenceEngine(
        Settings(llm_provider="ollama", assessment_batch_size=3), llm,
        cache_path=tmp_path / "vectors.db", encoder=LocalFakeEncoder())
    try:
        rows, metrics = engine.assess(fixture_requirements(), fixture_segments(),
                                       "Python, FastAPI", candidate_id="cv_2")
        assert len(rows) == 3
        assert all(row.assessment_state == "verified" for row in rows)
        assert metrics.interrupted_cause is None
        assert any(len(ids) > 1 for ids in llm.calls)
        assert any(len(ids) == 1 for ids in llm.calls)
        assert len(llm.calls) <= 6
    finally:
        engine.close()


def test_unsupported_strict_schema_is_not_retried_for_every_cv():
    from pydantic import BaseModel

    class Decision(BaseModel):
        status: str

    settings = Settings(llm_provider="openrouter", openrouter_api_key="test-not-real",
                        llm_retries=1)
    llm = OpenRouterStructuredLLM(settings)
    modes = []

    def fake_post(payload):
        mode = payload["response_format"]["type"]
        modes.append(mode)
        if mode == "json_schema":
            raise OpenRouterHTTPError(400)
        return {"choices": [{"message": {"content": '{"status":"ok"}'}}]}

    llm._post_chat = fake_post
    llm.invoke_structured(system_prompt="judge", user_prompt="first", schema=Decision)
    llm.invoke_structured(system_prompt="judge", user_prompt="second", schema=Decision)
    assert modes == ["json_schema", "json_object", "json_object"]


def test_background_progress_caption_updates_without_streamlit_calls_from_worker(monkeypatch):
    import time
    from queue import SimpleQueue
    from cv_ranker.ui import dashboard

    mailbox = SimpleQueue()
    mailbox.put("CV 2/2: reading resume and preparing evidence")
    monkeypatch.setattr(dashboard.st, "session_state", {
        "cv_manual_progress_queue": mailbox,
        "cv_manual_progress_started": time.monotonic() - 5,
    })
    caption = dashboard._progress_caption(
        "cv_manual_progress_queue", "cv_manual_progress_started")
    assert "CV 2/2" in caption and "elapsed" in caption


def test_identical_invalid_model_rows_pause_without_another_cloud_retry():
    from cv_ranker.schemas import CandidateResult, RankingReport, RequirementAssessment
    from cv_ranker.ui import dashboard

    unverified = RequirementAssessment(
        requirement_id="R002", status="uncertain", unified_status="Unverified",
        assessment_state="unverified")
    report = RankingReport(job_description_source="jd", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[],
                           candidates=[CandidateResult(candidate_name="candidate-one"),
                                       CandidateResult(candidate_name="candidate-two",
                                                       assessments=[unverified])])
    state = {"attempts": 0, "no_progress_streak": 0, "rate_limit_streak": 0}
    updated = dashboard._advance_recovery_state(
        state, report, previous_complete=0, previous_verified=0,
        metrics={"http_429_count": 0}, provider_hard_stop=False,
        cooldown_seconds=0,
        candidate_diagnostics={"1": {"unresolved_ids": ["R002"],
                                     "interrupted_cause": None}})
    assert updated["paused"] is True
    assert "CV 2: R002" in updated["pause_reason"]
    assert "identical requests stopped" in updated["pause_reason"]


def test_provider_rate_limit_keeps_cooldown_instead_of_blind_validation_pause():
    from cv_ranker.schemas import CandidateResult, RankingReport
    from cv_ranker.ui import dashboard

    report = RankingReport(job_description_source="jd", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[],
                           candidates=[CandidateResult(candidate_name="candidate-two")])
    updated = dashboard._advance_recovery_state(
        {"attempts": 0, "no_progress_streak": 0, "rate_limit_streak": 0},
        report, previous_complete=0, previous_verified=0,
        metrics={"http_429_count": 1, "provider_retry_after_seconds": 90},
        provider_hard_stop=False, cooldown_seconds=90,
        candidate_diagnostics={"0": {"unresolved_ids": ["R002"],
                                     "interrupted_cause": None}})
    assert updated.get("paused") is not True
    assert updated["next_due"] > 0

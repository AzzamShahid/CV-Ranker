"""Regression contracts for interrupted, privacy-preserving assessments."""

from dataclasses import replace
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

from cv_ranker.config import Settings
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.llm import OpenRouterHTTPError, OpenRouterStructuredLLM
from cv_ranker.pipeline import CVRanker
from cv_ranker.resume import assessment_context_key, candidate_resume_key
from cv_ranker.schemas import RankingReport, RequirementAssessment, ValidatedRequirement
from cv_ranker.scoring import score_candidate


def _settings():
    return Settings(llm_provider="ollama")


def _data(tmp_path: Path):
    jd = tmp_path / "jd.txt"
    jd.write_text("Required: Python application development.", encoding="utf-8")
    resume = tmp_path / "resume.txt"
    resume.write_text("Python application development experience.", encoding="utf-8")
    req = ValidatedRequirement(requirement_id="R001", name="Python",
                               priority="required", jd_evidence="Python")
    completed = score_candidate(
        candidate_name=resume.name, candidate_source="uploaded://0001/resume.txt",
        requirements=[req],
        assessments=[RequirementAssessment(requirement_id="R001", status="matched",
                                           unified_status="Found")],
        evaluation_mode="llm_assessed", errors=[],
    )
    report = RankingReport(job_description_source="uploaded://jd", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[req], candidates=[completed],
                           jd_sha256=jd_source_sha256(jd.read_text(encoding="utf-8")))
    key = candidate_resume_key(resume.name, resume.read_bytes())
    return jd, resume, report, key


def test_resume_keys_are_content_bound_and_pacing_does_not_invalidate_judgments():
    settings = _settings()
    first = assessment_context_key(settings, jd_bytes=b"Required: Python")
    assert first == assessment_context_key(replace(settings, openrouter_request_interval_seconds=10),
                                           jd_bytes=b"Required: Python")
    assert first != assessment_context_key(settings, jd_bytes=b"Required: Java")
    assert first != assessment_context_key(settings, jd_bytes=b"Required: Python",
                                           approved_aliases_bytes=b"reviewed alias")
    assert first != assessment_context_key(replace(settings, ollama_model="other:3b"),
                                           jd_bytes=b"Required: Python")
    assert candidate_resume_key("a.pdf", b"CV") != candidate_resume_key("a.pdf", b"edited CV")
    assert candidate_resume_key("a.pdf", b"CV") != candidate_resume_key("b.pdf", b"CV")


def test_completed_cv_and_frozen_jd_resume_without_any_llm_or_assessor(monkeypatch, tmp_path):
    jd, resume, report, key = _data(tmp_path)

    def no_extraction(**kwargs):
        raise AssertionError("The frozen JD was unexpectedly sent to the extractor")

    def no_assessment(**kwargs):
        raise AssertionError("A completed CV was assessed a second time")

    monkeypatch.setattr("cv_ranker.pipeline.validate_jd_requirements", no_extraction)
    monkeypatch.setattr("cv_ranker.pipeline.assess_resume", no_assessment)
    ranker = CVRanker(settings=_settings(), use_llm=False)
    result = ranker.run(jd, [resume], resume_report=report,
                        resume_candidates={key: report.candidates[0]})
    assert result.candidates[0].primary_score == 100
    assert result.candidates[0].candidate_source == str(resume)
    assert result.requirements == report.requirements
    assert result.jd_validation_mode == "llm_validated"
    assert result.candidates[0].rank == 1


def test_resume_refuses_changed_jd_before_reusing_a_single_cv(tmp_path):
    jd, resume, report, key = _data(tmp_path)
    jd.write_text("Required: Java application development.", encoding="utf-8")
    ranker = CVRanker(settings=_settings(), use_llm=False)
    with pytest.raises(ValueError, match="JD changed"):
        ranker.run(jd, [resume], resume_report=report,
                   resume_candidates={key: report.candidates[0]})


def test_failed_resume_retains_stronger_previous_partial_evidence(monkeypatch, tmp_path):
    jd, resume, report, key = _data(tmp_path)
    partial = report.candidates[0].model_copy(update={
        "primary_score": None, "required_score": None, "evaluation_mode": "failed",
        "assessments": [RequirementAssessment(requirement_id="R001", status="uncertain",
                                              unified_status="Unverified", assessment_state="unverified")],
    })
    # Even an old technically incomplete candidate should not disappear when
    # a fresh request fails before returning any requirement-level rows.
    older = partial.model_copy(update={
        "assessments": [RequirementAssessment(requirement_id="R001", status="matched",
                                              unified_status="Found", assessment_state="verified")],
    })
    monkeypatch.setattr("cv_ranker.pipeline.assess_resume",
                        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    ranker = CVRanker(settings=_settings(), use_llm=False)
    result = ranker.run(jd, [resume], resume_report=report, resume_candidates={key: older})
    assert result.candidates[0].primary_score is None
    assert result.candidates[0].assessments[0].status == "matched"
    assert any("previous partial evidence was retained" in e for e in result.candidates[0].errors)


def test_429_telemetry_records_retry_header_without_body(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="TEST_KEY")
    llm = OpenRouterStructuredLLM(settings)
    headers = Message()
    headers["Retry-After"] = "17"

    def unavailable(*args, **kwargs):
        raise HTTPError("https://openrouter.ai", 429, "confidential body", headers, None)

    monkeypatch.setattr("cv_ranker.llm.urlopen", unavailable)
    with pytest.raises(OpenRouterHTTPError, match="429"):
        llm._post_chat({"model": "test"})
    assert llm.http_attempts == 1
    assert llm.http_429_count == 1
    assert llm.last_retry_after_seconds == 17


def test_unified_resume_assesses_only_incomplete_candidate(monkeypatch, tmp_path):
    jd, first, report, first_key = _data(tmp_path)
    second = tmp_path / "second.txt"
    second.write_text("Delivered Python applications.", encoding="utf-8")
    second_key = candidate_resume_key(second.name, second.read_bytes())
    prior_partial = report.candidates[0].model_copy(update={
        "candidate_name": second.name, "primary_score": None,
        "required_score": None, "evaluation_mode": "failed",
        "assessments": [RequirementAssessment(requirement_id="R001", status="uncertain",
                                               assessment_state="unverified",
                                               unified_status="Unverified")],
    })

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
            return {"llm_calls": 1, "correction_calls": 0, "final_verification_calls": 0}

    class FakeEngine:
        names = []

        def __init__(self, *args, **kwargs):
            pass

        def assess(self, requirements, segments, resume_text, candidate_id):
            self.names.append(resume_text)
            return [RequirementAssessment(requirement_id="R001", status="matched",
                                          unified_status="Found")], FakeMetrics()

        def close(self):
            pass

    monkeypatch.setattr("cv_ranker.pipeline.StructuredLLM", FakeLLM)
    monkeypatch.setattr("cv_ranker.unified.UnifiedEvidenceEngine", FakeEngine)
    monkeypatch.setattr("cv_ranker.pipeline.validate_jd_requirements", lambda **kwargs:
                        (_ for _ in ()).throw(AssertionError("JD extraction repeated")))
    ranker = CVRanker(settings=_settings(), use_llm=True, unified=True)
    result = ranker.run(jd, [first, second], resume_report=report,
                        resume_candidates={first_key: report.candidates[0], second_key: prior_partial})
    assert len(FakeEngine.names) == 1
    assert "Delivered Python" in FakeEngine.names[0]
    assert [c.primary_score for c in result.candidates] == [100.0, 100.0]
    assert ranker.request_metrics["resumed_frozen_jd"] is True
    assert ranker.request_metrics["reused_completed_candidates"] == 1
    assert ranker.request_metrics["reassessed_candidates"] == 1
    assert ranker.request_metrics["unified_candidate_calls"] == 1


def test_all_complete_resume_skips_embedding_provider_initialization(monkeypatch, tmp_path):
    jd, resume, report, key = _data(tmp_path)

    class FakeLLM:
        disabled_reason = None
        logical_calls = 0
        http_attempts = 0
        token_usage = {}

        def __init__(self, settings):
            pass

    def no_embedding_engine(*args, **kwargs):
        raise AssertionError("Embedding provider must not be contacted for a cached CV")

    monkeypatch.setattr("cv_ranker.pipeline.StructuredLLM", FakeLLM)
    monkeypatch.setattr("cv_ranker.unified.UnifiedEvidenceEngine", no_embedding_engine)
    ranker = CVRanker(settings=_settings(), use_llm=True, unified=True)
    result = ranker.run(jd, [resume], resume_report=report,
                        resume_candidates={key: report.candidates[0]})
    assert result.candidates[0].primary_score == 100
    assert ranker.request_metrics["reused_completed_candidates"] == 1
    assert ranker.request_metrics["actual_model_request_attempts"] == 0


def test_unified_circuit_breaker_skips_remaining_cv_without_new_calls(monkeypatch, tmp_path):
    jd, first, report, _ = _data(tmp_path)
    second = tmp_path / "second.txt"
    second.write_text("Performed professional Python operations and supported teams "
                      "with documented software integrations and service workflows.",
                      encoding="utf-8")

    class FakeLLM:
        logical_calls = 1
        http_attempts = 3
        token_usage = {}
        disabled_reason = None

        def __init__(self, settings):
            pass

    class FakeEngine:
        attempts = 0

        def __init__(self, settings, llm, **kwargs):
            self.llm = llm

        def assess(self, *args, **kwargs):
            type(self).attempts += 1
            self.llm.disabled_reason = "OpenRouter HTTP 429: request budget exhausted"
            raise RuntimeError("OpenRouter HTTP 429")

        def close(self):
            pass

    monkeypatch.setattr("cv_ranker.pipeline.StructuredLLM", FakeLLM)
    monkeypatch.setattr("cv_ranker.unified.UnifiedEvidenceEngine", FakeEngine)
    ranker = CVRanker(settings=_settings(), use_llm=True, unified=True)
    result = ranker.run(jd, [first, second], resume_report=report)
    assert FakeEngine.attempts == 1
    assert all(c.primary_score is None for c in result.candidates)
    assert any("Assessment paused" in err
               for candidate in result.candidates for err in candidate.errors), [
                   (candidate.candidate_name, candidate.errors) for candidate in result.candidates]
    assert ranker.request_metrics["reassessed_candidates"] == 1


def test_dashboard_resume_checkpoint_tracks_source_hash_not_leaderboard_order(
        monkeypatch, tmp_path):
    from cv_ranker.ui import dashboard

    jd, first, base_report, _ = _data(tmp_path)
    second = tmp_path / "second.txt"
    second.write_text("Professional Python integration and application delivery; "
                      "automated internal workflows using documented Python scripts.",
                      encoding="utf-8")
    requirement = base_report.requirements[0]
    first_completed = base_report.candidates[0]
    second_partial = score_candidate(
        candidate_name=second.name, candidate_source=str(second),
        requirements=[requirement],
        assessments=[RequirementAssessment(requirement_id="R001", status="uncertain",
                                           assessment_state="unverified",
                                           unified_status="Unverified")],
        evaluation_mode="failed", errors=["Initial provider failure"],
    )

    class FakeRanker:
        resume_seen = False

        def __init__(self, **kwargs):
            self.source_ledgers = {}
            self.unified_metrics = {}
            self.request_metrics = {}
            self.llm = None

        def run(self, jd_path, paths, *, resume_report=None, resume_candidates=None):
            if resume_report is None:
                results = [first_completed.model_copy(update={"candidate_source": str(paths[0])}),
                           second_partial.model_copy(update={"candidate_source": str(paths[1])})]
            else:
                FakeRanker.resume_seen = True
                assert len(resume_candidates) == 2
                first_key = candidate_resume_key(first.name, first.read_bytes())
                assert resume_candidates[first_key].primary_score == 100
                assert resume_report.jd_sha256 == base_report.jd_sha256
                recovered = first_completed.model_copy(update={
                    "candidate_name": second.name, "candidate_source": str(paths[1]),
                })
                results = [first_completed.model_copy(update={"candidate_source": str(paths[0])}),
                           recovered]
            # Deliberately reverse input order: the cache must follow the
            # original source path rather than a visible leaderboard index.
            return base_report.model_copy(update={"candidates": list(reversed(results))})

    monkeypatch.setattr(dashboard, "CVRanker", FakeRanker)
    monkeypatch.setattr(dashboard.st, "session_state", {})
    monkeypatch.setattr(dashboard, "reconcile_unified_candidate", lambda report, index, ledger: {
        "Required matched": report.candidates[index].matched_required,
        "Required total": report.candidates[index].total_required,
        "Preferred matched": report.candidates[index].matched_preferred,
        "Preferred total": report.candidates[index].total_preferred,
    })

    first_run = dashboard._rank(jd, [first, second], _settings(), True,
                                "Uploaded CVs", uploaded=True)
    assert sum(c.primary_score is not None for c in first_run.candidates) == 1
    assert len(dashboard.st.session_state["cv_resume_cache"]["candidates"]) == 2
    second_run = dashboard._rank(jd, [first, second], _settings(), True,
                                 "Uploaded CVs", uploaded=True, resume=True)
    assert FakeRanker.resume_seen
    assert sum(c.primary_score is not None for c in second_run.candidates) == 2
    assert len(dashboard.st.session_state["cv_run_history"]) == 1

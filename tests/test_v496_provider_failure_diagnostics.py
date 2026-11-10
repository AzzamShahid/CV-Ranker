"""A failed cloud run must expose its safe cause without fabricating scores."""

import json

import numpy as np
import pytest

from cv_ranker.config import Settings
from cv_ranker.llm import LLMError
from cv_ranker.pipeline import CVRanker
from cv_ranker.schemas import RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import UnifiedEvidenceEngine


class DummyEncoder:
    fingerprint = "diagnostics-offline-stub"

    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class ProviderThatFailsAfterFirstCandidate:
    disabled_reason = None

    def __init__(self, settings):
        self.settings = settings
        self.calls = 0

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        if self.calls > 1:
            self.disabled_reason = "OpenRouter HTTP 429: request budget exhausted for this run"
            raise LLMError(
                "OpenRouter structured call failed after at most 3 attempt(s): "
                "OpenRouter HTTP 429: rate limit reached; retry later")
        payload = json.loads(user_prompt)
        name = payload["requirements"][0]["id"]
        cited = next(s["id"] for s in payload["sources"] if "Python" in s["text"])
        return schema.model_validate({name: {
            "decision": "found", "evidence_ids": [cited],
            "matched_term": "Python", "reason": "The CV lists Python explicitly.",
        }})


def test_provider_failure_marks_later_candidates_unassessed_with_safe_cause(tmp_path, monkeypatch):
    req = ValidatedRequirement(
        requirement_id="R001", priority="required", name="Python",
        jd_evidence="Python", constraint=RequirementConstraint(
            kind="skill", origin="source_rules"))
    monkeypatch.setattr("cv_ranker.pipeline.extract_yake_candidates", lambda *_: [])
    monkeypatch.setattr("cv_ranker.pipeline.validate_jd_requirements",
                        lambda **_: ([req], "llm_validated", []))
    monkeypatch.setattr("cv_ranker.pipeline.add_requirement_types",
                        lambda requirements, *_args, **_kwargs: requirements)
    jd = tmp_path / "job.txt"
    jd.write_text("The position requires documented Python programming experience.")
    resumes = [tmp_path / name for name in ("one.txt", "two.txt", "three.txt")]
    for item in resumes:
        item.write_text("Skills\nPython for developing internal software tools.")
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-mock-value")
    ranker = CVRanker(settings=settings, use_llm=True, unified=True,
                      embedding_encoder=DummyEncoder(),
                      embedding_cache_path=tmp_path / "cache.sqlite")
    ranker.llm = ProviderThatFailsAfterFirstCandidate(settings)
    report = ranker.run(jd, resumes)
    assessed = [item for item in report.candidates if item.primary_score is not None]
    failed = [item for item in report.candidates if item.primary_score is None]
    assert len(assessed) == 1 and assessed[0].primary_score == 100
    assert len(failed) == 2
    assert all(item.evaluation_mode == "failed" and item.assessments == [] for item in failed)
    assert all("OpenRouter HTTP 429" in item.errors[-1] for item in failed)
    assert any("no fallback score was assigned" in msg for msg in report.warnings)
    assert not any("remaining LLM calls used deterministic fallback" in msg
                   for msg in report.warnings)


def test_unexpected_exception_does_not_expose_provider_or_cv_content(tmp_path):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="offline-mock-value")
    class MalformedProvider:
        def __init__(self):
            self.settings = settings
        def prompt_fits(self, *_):
            return True
        def invoke_structured(self, **_):
            raise ValueError("SENSITIVE-CV-CONTENT-SHOULD-NOT-LEAK")

    req = ValidatedRequirement(
        requirement_id="R001", priority="required", name="Python",
        jd_evidence="Python", constraint=RequirementConstraint(kind="skill", origin="source_rules"))
    source = ResumeSegment("S001", "skills", "Python for software tools.")
    engine = UnifiedEvidenceEngine(settings, MalformedProvider(),
                                   cache_path=tmp_path / "cache.sqlite",
                                   encoder=DummyEncoder())
    try:
        with pytest.raises(LLMError) as failure:
            engine.assess([req], [source], source.text, candidate_id="synthetic-private")
    finally:
        engine.close()
    assert "ValueError" in str(failure.value)
    assert "SENSITIVE-CV-CONTENT-SHOULD-NOT-LEAK" not in str(failure.value)

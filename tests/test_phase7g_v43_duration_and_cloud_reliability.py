"""JD coverage and cloud-failure regressions; all provider calls are mocked."""

import json
from urllib.error import HTTPError

import pytest

from cv_ranker.config import Settings
from cv_ranker.experience_validation import check_experience
from cv_ranker.fallback import fallback_requirements
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.llm import LLMError, StructuredLLM
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (
    CandidateResult, JDRequirement, JDValidationResponse, RankingReport,
    RequirementAssessment, ValidatedRequirement,
)
from cv_ranker.segments import segment_resume
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.final_decisions import reconcile_candidate


def test_source_keeps_nonbullet_duration_and_degree_from_explicit_sections():
    jd = ("REQUIRED EXPERIENCE:\nMinimum 3 years of professional work experience.\n\n"
          "REQUIRED EDUCATION:\nBachelor's degree in Accounting required.\n\n"
          "REQUIRED SKILLS:\n- Ledger reconciliation\n\n"
          "PREFERRED SKILLS:\n- Auditing\n")
    requirements = fallback_requirements(jd, [], 30)
    assert [r.priority for r in requirements] == ["required"] * 3 + ["preferred"]
    assert [r.name for r in requirements] == [
        "Minimum 3 years of professional work experience.",
        "Bachelor's degree in Accounting required.",
        "Ledger reconciliation", "Auditing",
    ]
    assert classify_requirement(requirements[0], jd).kind == "experience"
    assert classify_requirement(requirements[1], jd).kind == "education"


def test_unsectioned_explicit_mandatory_requirements_not_hardcoded_to_ai():
    jd = ("Applicants must have at least 5 years of professional logistics experience.\n"
          "A bachelor's degree in Supply Chain Management is required.\n"
          "BENEFITS:\nAt least 25 days of annual leave is provided.\n")
    rows = fallback_requirements(jd, [], 30)
    assert len(rows) == 2
    assert all(row.priority == "required" for row in rows)
    assert any("logistics" in row.name for row in rows)
    assert any("Supply Chain" in row.name for row in rows)


def test_minimum_years_in_sample_jd_is_not_lost_to_explanatory_conjunctions():
    from pathlib import Path
    jd = Path("sample_data/applied_ai_jd.txt").read_text(encoding="utf-8")
    requirements = fallback_requirements(jd, [], 30)
    assert len(requirements) == 17
    experience = requirements[0].model_copy(update={
        "constraint": classify_requirement(requirements[0], jd)
    })
    assert experience.constraint.kind == "experience"
    assert experience.constraint.operator == "complex"  # professional work scope still reviewable
    assert experience.constraint.minimum_years == 3
    cv = ("PROFESSIONAL PROFILE\n"
          "Applied AI developer with 2 years 4 months of full-time professional experience.\n"
          "TECHNICAL SKILLS\nPython, PyTorch, NLP\n"
          "EDUCATION\nBS Computer Science, 2024\n")
    outcome = check_experience(experience, cv, segment_resume(cv))
    assert outcome.outcome == "insufficient"
    assert any(c.lower_years == pytest.approx(2 + 4 / 12) for c in outcome.claims)


def test_source_restores_missing_experience_without_inventing_education():
    from pathlib import Path
    jd = Path("sample_data/applied_ai_jd.txt").read_text(encoding="utf-8")

    class ModelOmittedDuration:
        def invoke_structured(self, **kwargs):
            return JDValidationResponse(requirements=[
                JDRequirement(name="Python", priority="required", evidence="Python"),
            ])

    frozen, _, warnings = validate_jd_requirements(
        jd_text=jd, candidates=[], settings=Settings(), llm=ModelOmittedDuration()
    )
    assert len(frozen) == 17
    assert sum(r.priority == "required" for r in frozen) == 10
    assert frozen[0].name.startswith("Minimum 3 years")
    assert not any(r.constraint.kind == "education" for r in frozen)
    assert any("source completeness" in item for item in warnings)


def test_final_reconciler_cannot_overrule_failed_numeric_duration():
    jd = "REQUIRED EXPERIENCE:\n- Minimum 3 years of professional experience\n"
    req = fallback_requirements(jd, [], 30)[0]
    req = req.model_copy(update={"constraint": classify_requirement(req, jd)})
    cv = "PROFESSIONAL PROFILE\n2 years 4 months of full-time professional experience.\n"
    segs = segment_resume(cv)
    check = check_experience(req, cv, segs)
    assert check.outcome == "insufficient"
    report = RankingReport(job_description_source="fixture", jd_validation_mode="test",
                           yake_candidates=[], requirements=[req], candidates=[
                               CandidateResult(candidate_name="Under minimum", assessments=[
                                   RequirementAssessment(requirement_id=req.requirement_id,
                                                         status="matched", experience_check=check)
                               ])
                           ])

    class NoCall:
        def invoke_structured(self, **kwargs):
            raise AssertionError("Numeric constraint must never be waived by a model")

    final = reconcile_candidate(report, 0, segment_ledger(segs), llm=NoCall())
    assert final["Required matched"] == 0
    assert final["Required total"] == 1
    assert final["Criteria"][0]["Result"] == "Not Found"
    assert "3 years" in final["Criteria"][0]["Why"]
    assert "2 years 4 months" in final["Criteria"][0]["Why"]


def test_openrouter_transient_rate_limit_retries_and_does_not_disable(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="sk-or-fake",
                        model_name="google/gemini-2.5-flash-lite", llm_retries=1)
    llm = StructuredLLM(settings)
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment
    calls = []

    def post(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise __import__("cv_ranker.llm", fromlist=["OpenRouterHTTPError"]).OpenRouterHTTPError(429)
        return {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"result": "not_evidenced", "explanation":
                                   "No cited CV segment demonstrates the requested skill.", "source_ids": []})
        }}]}

    monkeypatch.setattr(llm, "_post_chat", post)
    monkeypatch.setattr("cv_ranker.llm.time.sleep", lambda _: None)
    response = llm.invoke_structured(system_prompt="Return JSON", user_prompt="Judge", schema=CompactFocusedJudgment)
    assert response.result == "not_evidenced"
    assert len(calls) == 2
    assert llm.disabled_reason is None


def test_openrouter_strict_schema_rejection_uses_locally_validated_json(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="sk-or-fake",
                        model_name="google/gemini-2.5-flash-lite", llm_retries=1)
    llm = StructuredLLM(settings)
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment
    modes = []

    def post(payload):
        modes.append(payload["response_format"]["type"])
        if len(modes) == 1:
            from cv_ranker.llm import OpenRouterHTTPError
            raise OpenRouterHTTPError(422)
        return {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"result": "uncertain", "explanation":
                                   "Sources disagree about the requested capability.", "source_ids": []})
        }}]}

    monkeypatch.setattr(llm, "_post_chat", post)
    response = llm.invoke_structured(system_prompt="Return JSON", user_prompt="Judge", schema=CompactFocusedJudgment)
    assert response.result == "uncertain"
    assert modes == ["json_schema", "json_object"]


def test_focused_model_preflight_trims_only_request_window_not_source_ledger():
    from types import SimpleNamespace
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment, _judge_requirement

    class SmallWindow:
        prefer_flat_focused_judgment = True

        def prompt_fits(self, system_prompt, user_prompt):
            return len(user_prompt) < 1150

        def invoke_structured(self, **kwargs):
            assert kwargs["schema"] is CompactFocusedJudgment
            given = json.loads(kwargs["user_prompt"])["exact_cv_segments"]
            assert 1 <= len(given) < 6
            return CompactFocusedJudgment(result="not_evidenced",
                explanation="The cited excerpt does not demonstrate professional application.",
                source_ids=[])

    req = ValidatedRequirement(requirement_id="R001", name="Case management",
                               priority="required", jd_evidence="Case management")
    sources = {f"S{i:03d}": SimpleNamespace(section="experience", text=f"Work note {i}. " + "x" * 300)
               for i in range(1, 7)}
    result = _judge_requirement(SmallWindow(), req, None, [], sources)
    assert result.result == "not_evidenced"
    assert len(sources) == 6  # The complete source ledger is never altered.

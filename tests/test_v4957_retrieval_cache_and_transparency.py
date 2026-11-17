"""Cross-domain regression checks for Phase 5-10 maintenance work.

All semantic matching remains the model's job. These tests only verify
candidate source discovery, replay, protocol identity and safe evidence audit.
"""
from __future__ import annotations

import json

import pytest

from cv_ranker.llm import OpenRouterStructuredLLM
from cv_ranker.config import Settings
from cv_ranker.resume import _ASSESSMENT_LOGIC_FILES, assessment_logic_fingerprint
from cv_ranker.retrieval_priorities import prioritize_source_ids, source_overlap_score
from cv_ranker.segments import _heading, segment_resume
from cv_ranker.unified import UnifiedMetrics
from cv_ranker.schemas import StrictModel


@pytest.mark.parametrize("heading, expected", [
    ("Experience Highlights", "experience"),
    ("Professional Experience Highlights", "experience"),
    ("Relevant Work Experience", "experience"),
    ("Project Experience", "projects"),
    ("Technical and operational skills", "skills"),
    ("Experience with ERP software", None),
    ("AWS IAM", None),
])
def test_headings_follow_layout_not_profession(heading, expected):
    assert _heading(heading) == expected


def test_actual_work_after_unusual_heading_not_misclassified_as_skills():
    document = (
        "Skills\nPython\n\nExperience Highlights\n"
        "Operations Engineer | Example Services Jan 2019 - Dec 2022\n"
        "- Ran documented restore exercises and recorded recovery times.\n"
    )
    sources = segment_resume(document)
    duty = next(seg for seg in sources if "Ran documented" in seg.text)
    assert duty.section == "experience"
    assert duty.source_lines


@pytest.mark.parametrize("jd, weak, relevant", [
    (
        "Weaving production planning and achievement of shift output targets",
        "Led audits and verified energy savings on pilot machines.",
        "Set weaving production plans and closed daily shift output gaps.",
    ),
    (
        "Integrate automated regression tests into a CI pipeline",
        "Wrote unrelated documentation for the product manager.",
        "Ran regression tests in our CI pipeline on every pull request.",
    ),
    (
        "Monitor and report customer service quality metrics",
        "Helped the warehouse team with inventory reordering.",
        "Reported customer service quality and response metrics weekly.",
    ),
])
def test_retrieval_uses_uploaded_jd_terms_without_role_specific_mapping(jd, weak, relevant):
    original = {"S002": weak, "S009": relevant}
    prioritized = prioritize_source_ids(jd, ["S002", "S009"], original)
    assert prioritized[0] == "S009"
    assert source_overlap_score(jd, relevant) > source_overlap_score(jd, weak)


def test_retrieval_retains_semantic_leads_even_without_any_literal_overlap():
    sources = {"S005": "Supported the customer call", "S006": "Reviewed the sandbox logs"}
    result = prioritize_source_ids("Analyze a specialized problem", ["S005", "S006"], sources)
    assert result == ["S005", "S006"]
    assert len(result) == 2


def test_fingerprint_changes_after_source_edit_not_layout_only(tmp_path):
    for name in _ASSESSMENT_LOGIC_FILES:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("original implementation", encoding="utf-8")
    before = assessment_logic_fingerprint(tmp_path)
    (tmp_path / "README.md").write_text("new UI copy", encoding="utf-8")
    assert assessment_logic_fingerprint(tmp_path) == before
    (tmp_path / "unified.py").write_text("changed assessment", encoding="utf-8")
    assert assessment_logic_fingerprint(tmp_path) != before


def test_rejected_model_source_ids_are_distinct_from_retrieval_leads():
    metrics = UnifiedMetrics(rejected_model_citations={"R005": ["S007", "S009"]},
                             selected_source_ids=["S001", "S007", "S009"])
    public = metrics.public()
    assert public["rejected_model_citations"] == {"R005": ["S007", "S009"]}
    assert public["selected_source_ids"] == ["S001", "S007", "S009"]


class _Result(StrictModel):
    answer: str


def test_identical_successful_cloud_payload_reuses_one_result_not_network(monkeypatch):
    # No network call: the fake provider gives a strict, valid structured JSON.
    settings = Settings(llm_provider="openrouter", openrouter_api_key="placeholder-for-test",
                        openrouter_response_format="json_object")
    client = OpenRouterStructuredLLM(settings)
    client._allow_success_replay = True
    calls = []

    def fake_post(payload):
        calls.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"answer": "verified"})}}]}

    monkeypatch.setattr(client, "_post_chat", fake_post)
    first = client.invoke_structured(system_prompt="system", user_prompt="CV-1", schema=_Result)
    repeated = client.invoke_structured(system_prompt="system", user_prompt="CV-1", schema=_Result)
    changed = client.invoke_structured(system_prompt="system", user_prompt="CV-2", schema=_Result)
    assert first.answer == repeated.answer == changed.answer == "verified"
    assert len(calls) == 2
    assert client.reused_successful_calls == 1
    assert client.http_attempts == 0  # fake provider intentionally doesn't update counters


def test_failures_are_not_cached_and_retry_may_succeed(monkeypatch):
    settings = Settings(llm_provider="openrouter", openrouter_api_key="placeholder-for-test",
                        openrouter_response_format="json_object", llm_retries=0)
    client = OpenRouterStructuredLLM(settings)
    client._allow_success_replay = True
    attempts = []

    def fail_once(payload):
        attempts.append(payload)
        if len(attempts) == 1:
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{invalid"}}]}
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"ok"}'}}]}

    monkeypatch.setattr(client, "_post_chat", fail_once)
    with pytest.raises(Exception):
        client.invoke_structured(system_prompt="system", user_prompt="same", schema=_Result)
    assert client.invoke_structured(system_prompt="system", user_prompt="same", schema=_Result).answer == "ok"
    assert len(attempts) == 2


def test_majority_scope_summary_plus_dated_role_and_duties_can_prove_tenure():
    """A legitimate CV is not rejected for omitting one generic JD qualifier."""
    from cv_ranker.experience_validation import apply_experience_checks
    from cv_ranker.requirement_typing import add_requirement_types
    from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement

    jd = "Minimum 3 years of full-time professional experience in textile weaving production."
    req = add_requirement_types([ValidatedRequirement(
        requirement_id="R001", name=jd, jd_evidence=jd, priority="required")], jd)[0]
    cv = ("Professional summary\n"
          "Weaving professional with 7 years 4 months of full-time experience "
          "supervising rapier loom production and quality.\n"
          "Professional experience\n"
          "Weaving Supervisor | Example Factory Jun 2019 - Present\n"
          "- Supervised loom production and daily woven fabric output.\n")
    sources = segment_resume(cv)
    summary = next(s for s in sources if s.section == "summary")
    role = next(s for s in sources if "Jun 2019" in s.text)
    row = RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence_ids=[summary.segment_id, role.segment_id],
        evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                            section=s.section, text=s.text)
                           for s in (summary, role)],
        reason="The model established the requested production work and tenure.")
    result, _, _ = apply_experience_checks(requirements=[req],
                                             assessments=[row], resume_text=cv)
    assert result[0].status == "matched"
    assert any("Supervised loom production" in c.text
               for c in result[0].evidence_segments)


def test_majority_scope_bridge_does_not_award_unrelated_tenure():
    from cv_ranker.experience_validation import apply_experience_checks
    from cv_ranker.requirement_typing import add_requirement_types
    from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement

    jd = "Minimum 3 years of full-time professional experience in textile weaving production."
    req = add_requirement_types([ValidatedRequirement(
        requirement_id="R001", name=jd, jd_evidence=jd, priority="required")], jd)[0]
    cv = ("Professional summary\n"
          "Retail professional with 7 years 4 months of full-time experience "
          "supervising consumer product sales.\n"
          "Professional experience\n"
          "Retail Sales Supervisor | Example Store Jun 2019 - Present\n"
          "- Supervised stock replenishment and sales reports.\n")
    sources = segment_resume(cv)
    summary = next(s for s in sources if s.section == "summary")
    role = next(s for s in sources if "Jun 2019" in s.text)
    row = RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence_ids=[summary.segment_id, role.segment_id],
        evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                            section=s.section, text=s.text)
                           for s in (summary, role)],
        reason="The model proposed a match that lacks the requested work scope.")
    checked, _, _ = apply_experience_checks(requirements=[req],
                                              assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"


def test_narrative_qa_jd_explicit_coverage_7_required_3_preferred():
    from cv_ranker.jd import validate_jd_requirements
    jd = """QA Automation Engineer
    Our work involves complex merchant payments and delayed callbacks.
    Required qualifications and capabilities
    At least 3 years of full-time professional experience in software testing.
    Completed bachelor's degree in Computer Science or Software Engineering.
    Automate browser regression coverage with Playwright.
    Write automated HTTP API tests for error paths.
    Integrate automated regression tests into a CI pipeline.
    Diagnose and repair flaky tests.
    Design reproducible test data for independent test runs.
    Preferred experience
    Measure application load behavior using k6.
    Test accessibility using a screen reader.
    Write actionable defect reports with isolation steps.
    Benefits
    We offer flexible hours and health insurance.
    """
    requirements, mode, notices = validate_jd_requirements(
        jd_text=jd, candidates=[], settings=Settings(llm_provider="ollama"), llm=None)
    assert len(requirements) == 10, (mode, notices)
    assert sum(r.priority == "required" for r in requirements) == 7
    assert sum(r.priority == "preferred" for r in requirements) == 3
    assert all("health insurance" not in r.name for r in requirements)


def test_required_preferred_pool_remains_unbiased_and_transferable_unscored():
    from cv_ranker.schemas import RankingReport, RequirementAssessment, ValidatedRequirement
    from cv_ranker.scoring import score_candidate
    from cv_ranker.weighted_scoring import ScoreWeights, weighted_candidate
    reqs = [ValidatedRequirement(requirement_id=f"R{i:03}", name=f"Capability {i}",
                                 jd_evidence=f"Capability {i}",
                                 priority="required" if i <= 9 else "preferred")
            for i in range(1, 17)]
    rows = [RequirementAssessment(requirement_id=r.requirement_id,
                                  status="matched" if i == 10 else "not_matched",
                                  unified_status="Found" if i == 10 else (
                                      "Transferable" if i == 1 else "Not Found"))
            for i, r in enumerate(reqs, 1)]
    candidate = score_candidate(candidate_name="Synthetic Test", requirements=reqs,
                                assessments=rows, evaluation_mode="llm_assessed", errors=[])
    report = RankingReport(job_description_source="unit-test", jd_validation_mode="frozen",
                           yake_candidates=[], requirements=reqs, candidates=[candidate])
    scored = weighted_candidate(report, candidate, ScoreWeights(experience=10, education=10, jd=80))
    assert scored["score"] == 100 / 16  # Only JD category is active and normalized
    assert not scored["provisional"]
    assert sum(row["earned_points"] for row in scored["requirement_contributions"]) == scored["score"]

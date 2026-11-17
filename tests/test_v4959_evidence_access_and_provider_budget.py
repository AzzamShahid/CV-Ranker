"""Source-grounded cross-domain M3/M4 regression checks (no real provider calls)."""

import pytest

from cv_ranker.config import Settings
from cv_ranker.llm import LLMError, OpenRouterStructuredLLM
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import RequirementAssessment, RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import _completed_work_recall_leads, _needs_independent_overlap_review


def _requirement(sentence, *, kind="other"):
    return ValidatedRequirement(
        requirement_id="R015", name=sentence, jd_evidence=sentence,
        priority="required", constraint=RequirementConstraint(kind=kind,
            source_line_numbers=[1], origin="source_rules", requires_review=True))


@pytest.mark.parametrize("work", [
    "Weaving production planning and shift target monitoring",
    "Infrastructure maintenance and incident coordination",
    "Client onboarding and issue reporting",
    "Inventory reconciliation and shipment documentation",
])
def test_noun_form_duties_describe_responsibilities_without_domain_dictionary(work):
    req = _requirement(work)
    typed = classify_requirement(req, work)
    assert typed.kind == "responsibility"
    assert typed.requires_review  # Work-noun inference remains reviewable.


def test_related_work_other_type_still_has_one_bounded_independent_review():
    jd = "Production reporting and operations coordination"
    source = ResumeSegment("S003", "experience",
        "Built production reporting dashboards and coordinated warehouse operations.")
    req = _requirement(jd, kind="other")
    row = RequirementAssessment(requirement_id="R015", status="not_matched",
        unified_status="Not Found", reason=(
            "Related completed production reporting work, but exact system not established."))
    assert _completed_work_recall_leads(req, {source.segment_id: source}, {source.segment_id})
    assert _needs_independent_overlap_review(req, row, {source.segment_id: source}, source.text)
    # A textually unrelated negative must not itself trigger more API calls.
    unrelated = ResumeSegment("S004", "experience", "Ran a catering event registration desk.")
    assert not _needs_independent_overlap_review(req, row, {unrelated.segment_id: unrelated}, unrelated.text)


def test_cloud_fits_its_own_explicit_budget_not_ollama_values():
    shared = {"llm_provider": "openrouter", "openrouter_api_key": "test-placeholder",
              "openrouter_context_tokens": 32768, "openrouter_output_tokens": 4096}
    cloud_a = OpenRouterStructuredLLM(Settings(**shared, ollama_num_ctx=2048, ollama_num_predict=512))
    cloud_b = OpenRouterStructuredLLM(Settings(**shared, ollama_num_ctx=16384, ollama_num_predict=8192))
    request = "candidate evidence " * 800
    assert cloud_a.prompt_fits("system", request)
    assert cloud_a.prompt_fits("system", request) == cloud_b.prompt_fits("system", request)
    assert not cloud_a.prompt_fits("system", "data " * 35000)


def test_cloud_request_uses_cloud_max_output_not_local(monkeypatch):
    from cv_ranker.schemas import StrictModel
    from cv_ranker.llm import ModelStructuredResponseError
    class Answer(StrictModel):
        answer: str
    settings = Settings(llm_provider="openrouter", openrouter_api_key="test-placeholder",
                        openrouter_context_tokens=16384, openrouter_output_tokens=4096,
                        ollama_num_ctx=2048, ollama_num_predict=256, llm_retries=0,
                        openrouter_response_format="json_object")
    client = OpenRouterStructuredLLM(settings)
    sent = []
    def fake_post(payload):
        sent.append(payload)
        return {"choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"ok"}'}}]}
    monkeypatch.setattr(client, "_post_chat", fake_post)
    assert client.invoke_structured(system_prompt="system", user_prompt="short", schema=Answer).answer == "ok"
    assert len(sent) == 1
    assert sent[0]["max_tokens"] == 4096


def test_cloud_rejects_impossible_app_budget_at_config_time():
    with pytest.raises(ValueError, match="OpenRouter context/output"):
        Settings(llm_provider="openrouter", openrouter_api_key="test-placeholder",
                 openrouter_context_tokens=2048, openrouter_output_tokens=4096)


def test_source_failure_correction_expands_original_passages_without_credit():
    from cv_ranker.unified import _source_repair_hits
    req = _requirement("Operational reporting and coordination", kind="other")
    bad = ResumeSegment("S001", "summary", "Interested in operational reporting and coordination.")
    good = ResumeSegment("S009", "experience", "Built reporting dashboards and coordinated operations.")
    hits, skipped = _source_repair_hits(
        [req], {"S001": bad, "S009": good}, {"R015": ["S001"]},
        ["R015: cited segment(s) contained no qualifying capability evidence."],
        {"S001", "S009"})
    assert not skipped
    assert hits["R015"][:2] == ["S009", "S001"]


def test_source_failure_with_no_new_relevant_original_skips_identical_repair():
    from cv_ranker.unified import _source_repair_hits
    req = _requirement("Operational reporting and coordination", kind="other")
    unrelated = ResumeSegment("S001", "experience", "Built a cafeteria sign-up sheet.")
    hits, skipped = _source_repair_hits(
        [req], {"S001": unrelated}, {"R015": ["S001"]},
        ["R015: cited segment(s) contained no qualifying capability evidence."],
        {"S001"})
    assert skipped == {"R015"}
    assert hits["R015"] == ["S001"]


def test_schema_only_correction_keeps_original_source_set():
    from cv_ranker.unified import _source_repair_hits
    req = _requirement("Operational reporting and coordination", kind="other")
    source = ResumeSegment("S001", "experience", "Built production reporting dashboards.")
    hits, skipped = _source_repair_hits(
        [req], {"S001": source}, {"R015": ["S001"]},
        ["R015: response rejected because the model omitted this frozen requirement ID."],
        {"S001"})
    assert not skipped
    assert hits["R015"] == ["S001"]

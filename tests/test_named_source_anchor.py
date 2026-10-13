"""Atomic name evidence must be anchored; Qwen, not Python, decides aliases."""

from cv_ranker.assessor import assess_resume, _is_short_named_requirement
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
from cv_ranker.segments import segment_resume
from evaluation.evaluate_benchmark import RowResult, _attach_raw_observation, _measurement_quality


class FakeLLM:
    def __init__(self, *results):
        self.results = iter(results)
        self.calls = []
        self.settings = type("S", (), {"assessment_batch_size": 20})()

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls.append((system_prompt, user_prompt))
        return next(self.results)


def model_row(status, cited=None, matched_term=None):
    return LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R001", status=status,
        evidence_ids=[cited] if cited else [], matched_term=matched_term,
    )])


def assess(name, resume, first_status, *, first_term=None, second=None):
    segment = segment_resume(resume)[0]
    llm = FakeLLM(model_row(first_status, segment.segment_id, first_term), *([second] if second else []))
    requirement = ValidatedRequirement(requirement_id="R001", name=name, priority="required", jd_evidence=name)
    decisions, mode, warnings = assess_resume(resume_text=resume, requirements=[requirement], llm=llm)
    return decisions[0], mode, warnings, llm


def test_unanchored_unrelated_named_tool_requires_correction_and_no_credit():
    decision, mode, warnings, llm = assess(
        "Django", "Experience:\nMaintained PostgreSQL databases for production applications.\n",
        "matched", second=model_row("not_matched")
    )
    assert decision.status == "not_matched"
    assert len(llm.calls) == 2
    assert any("named requirement semantic claim lacked" in w for w in warnings)
    assert "actual named source phrase" in llm.calls[1][0]


def test_uncertain_about_different_named_item_also_requires_correction():
    decision, _, _, llm = assess(
        "Django", "Experience:\nBuilt APIs with FastAPI in production.\n",
        "uncertain", second=model_row("not_matched")
    )
    assert decision.status == "not_matched" and len(llm.calls) == 2


def test_genuine_abbreviation_source_term_is_accepted_with_full_line():
    decision, mode, warnings, llm = assess(
        "Google Cloud", "Skills:\nGCP, Python, Docker\n", "matched", first_term="GCP"
    )
    assert decision.status == "matched" and mode == "llm_assessed"
    assert decision.evidence_segments[0].text == "GCP, Python, Docker"
    assert len(llm.calls) == 1 and not warnings


def test_nlp_unanchored_prompts_correction_then_one_word_accepted():
    source = "Skills:\nNLP, pandas, pytorch\n"
    segment_id = segment_resume(source)[0].segment_id
    decision, mode, warnings, llm = assess(
        "Natural Language Processing", source, "matched",
        second=model_row("matched", segment_id, "NLP")
    )
    assert decision.status == "matched" and decision.matched_term == "NLP"
    assert mode == "llm_assessed" and len(llm.calls) == 2
    assert any("named requirement semantic claim" in w for w in warnings)


def test_semantic_action_paraphrase_still_accepts_no_term():
    decision, mode, warnings, llm = assess(
        "REST API development", "Projects:\nBuilt REST endpoints with FastAPI.\n", "matched"
    )
    assert decision.status == "matched"
    assert mode == "llm_assessed" and len(llm.calls) == 1 and not warnings


def test_named_wording_actually_present_needs_no_extra_citation():
    decision, mode, warnings, llm = assess(
        "PostgreSQL", "Experience:\nMaintained PostgreSQL databases for production applications.\n", "matched"
    )
    assert decision.status == "matched" and len(llm.calls) == 1
    assert not warnings


def test_heuristic_is_format_only_and_not_semantic_catalogue():
    for name in ["Django", "Google Cloud", "Natural Language Processing", "GCP", "Machine Learning"]:
        assert _is_short_named_requirement(name)
    for name in ["REST API development", "3+ years of Python experience", "AWS certification", "Bachelor's degree in Computer Science"]:
        assert not _is_short_named_requirement(name)


def test_benchmark_shows_true_per_row_paths_inside_mixed_batch():
    def r(rid, predicted, raw):
        item = RowResult("case", rid, "X", "exact", predicted, predicted, "mixed", [], None, None, True)
        return _attach_raw_observation(item, {
            "first_status": raw, "last_status": raw,
            "last_evidence_ids": [], "last_matched_term": None,
            "attempts": 1, "retried": False,
        })
    quality = _measurement_quality([r("R001", "matched", "matched"), r("R002", "matched", "not_matched")], "assessment")
    assert quality["decision_path_counts"]["llm_initial_agreed_with_final"] == 1
    assert quality["decision_path_counts"]["python_or_fallback_changed_status"] == 1
    assert quality["post_model_status_changed_rows"] == ["case/R002"]
    assert quality["qwen_initial_status_unchanged_rows"] == ["case/R001"]
    assert quality["valid_live_llm_measurement"] is False

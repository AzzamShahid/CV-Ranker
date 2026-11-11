"""Source validation recovery regressions; no cloud credentials or live CVs."""

import json
from dataclasses import replace
from types import SimpleNamespace

from cv_ranker.config import Settings
from cv_ranker.llm import ModelStructuredResponseError
from cv_ranker.schemas import (RequirementAssessment, RequirementConstraint,
                               ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import (
    UnifiedEvidenceEngine, UnifiedItem, UnifiedMetrics, UnifiedResponse,
    _review_independent_group,
)
from cv_ranker.ui.dashboard import _advance_recovery_state


def _inputs(count):
    names = ("Python", "Docker", "SQL", "Java", "Excel", "PowerPoint", "C++")
    reqs = [ValidatedRequirement(
        requirement_id=f"R{i:03d}", name=names[i - 1],
        priority="required", jd_evidence=names[i - 1])
        for i in range(1, count + 1)]
    sources = [ResumeSegment(segment_id=f"S{i:03d}", section="skills",
                             text=names[i - 1], source_lines=(i,))
               for i in range(1, count + 1)]
    return reqs, sources


def _unverified(requirements):
    return {r.requirement_id: RequirementAssessment(
        requirement_id=r.requirement_id, status="uncertain",
        unified_status="Unverified", assessment_state="unverified",
        reason="The model response still needs source validation.")
        for r in requirements}


def test_malformed_multi_id_final_response_splits_once_without_identical_requests():
    requirements, segments = _inputs(4)

    class Model:
        disabled_reason = None

        def __init__(self):
            self.calls = []

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, user_prompt, schema, **_):
            ids = tuple(schema.model_fields)
            self.calls.append(ids)
            if len(ids) > 2:
                raise ModelStructuredResponseError("grouped JSON invalid")
            return schema.model_validate({
                rid: {"decision": "found", "relation": "direct",
                      "evidence_ids": [f"S{int(rid[1:]):03d}"],
                      "proof_excerpt": None,
                      "reason": "The candidate explicitly lists the named skill."}
                for rid in ids})

    model = Model()
    results = _unverified(requirements)
    metrics = UnifiedMetrics()
    _review_independent_group(
        requirements, final_by_id=results,
        context_requirements=requirements,
        original={source.segment_id: source for source in segments},
        allowed={source.segment_id for source in segments},
        hits={r.requirement_id: [f"S{i:03d}"]
              for i, r in enumerate(requirements, 1)},
        llm=model, metrics=metrics,
        resume_text="\n".join(source.text for source in segments),
        segments=segments, top_k=2, must_complete=True)
    assert model.calls == [
        ("R001", "R002", "R003", "R004"),
        ("R001", "R002"), ("R003", "R004")]
    assert metrics.final_verification_calls == 3
    assert all(row.assessment_state == "verified" for row in results.values())
    assert all(row.unified_status == "Found" for row in results.values())


def test_invalid_original_source_id_is_not_credited_or_retried_identically():
    requirements, segments = _inputs(1)

    class Model:
        disabled_reason = None
        calls = 0

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, schema, **_):
            self.calls += 1
            return schema.model_validate({"R001": {
                "decision": "found", "relation": "direct",
                "evidence_ids": ["S999"], "proof_excerpt": None,
                "reason": "Claims to have Python without a genuine original source."}})

    model = Model()
    results = _unverified(requirements)
    metrics = UnifiedMetrics()
    _review_independent_group(
        requirements, final_by_id=results,
        context_requirements=requirements,
        original={"S001": segments[0]}, allowed={"S001"},
        hits={"R001": ["S001"]}, llm=model, metrics=metrics,
        resume_text="Python", segments=segments, top_k=2, must_complete=True)
    assert model.calls == 1
    assert results["R001"].assessment_state == "unverified"
    assert results["R001"].evidence_ids == []
    assert any("cited source was not among" in msg for msg in metrics.warnings)


def test_more_pending_requirements_than_completion_budget_all_get_checked():
    requirements, segments = _inputs(7)
    requirements = [r.model_copy(update={
        "constraint": RequirementConstraint(kind="responsibility")})
        for r in requirements]
    segments = [replace(s, section="projects",
                        text=f"Built a production-ready {requirements[i].name} application.")
        for i, s in enumerate(segments)]

    class Model:
        disabled_reason = None

        def __init__(self):
            self.initial_calls = 0
            self.final_ids = []

        def prompt_fits(self, *_):
            return True

        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            if "independent evidence adjudicator" in system_prompt.casefold():
                ids = tuple(schema.model_fields)
                self.final_ids.extend(ids)
                return schema.model_validate({
                    rid: {"decision": "found", "relation": "direct",
                          "evidence_ids": [f"S{int(rid[1:]):03d}"],
                          "proof_excerpt": None,
                          "reason": "The candidate affirmatively listed this exact skill."}
                    for rid in ids})
            self.initial_calls += 1
            incoming = json.loads(user_prompt)
            return UnifiedResponse(assessments=[
                UnifiedItem(requirement_id=r["id"], decision="found",
                            relation="direct", evidence_ids=["S999"],
                            reason="An ungrounded model source ID was supplied.")
                for r in incoming["requirements"]])

    model = Model()
    engine = UnifiedEvidenceEngine.__new__(UnifiedEvidenceEngine)
    engine.settings = Settings(llm_provider="ollama", ollama_num_predict=700,
                               assessment_batch_size=7)
    engine.llm = model
    engine.top_k = 2
    engine.progress_callback = None
    engine.retriever = SimpleNamespace(retrieve_by_query=lambda *_, **__: {
        r.requirement_id: [SimpleNamespace(source=SimpleNamespace(
            segment_id=segments[index].segment_id))]
        for index, r in enumerate(requirements)})
    rows, metrics = engine.assess(
        requirements, segments,
        "\n".join(source.text for source in segments),
        candidate_id="fake-seven-requirements")
    assert set(model.final_ids) == {r.requirement_id for r in requirements}
    assert len(model.final_ids) == len(requirements)
    assert metrics.unresolved_ids == []
    assert all(row.assessment_state == "verified" for row in rows)


def test_actual_cumulative_budget_exhaustion_pauses_with_actionable_reason():
    pending = SimpleNamespace(primary_score=None, assessments=[
        SimpleNamespace(assessment_state="unverified")])
    state = _advance_recovery_state(
        {"attempts": 0, "no_progress_streak": 0, "rate_limit_streak": 0},
        SimpleNamespace(candidates=[pending]),
        previous_complete=0, previous_verified=0,
        metrics={"assessment_http_attempts_remaining": 0,
                 "assessment_http_attempts_cumulative": 12,
                 "assessment_http_attempt_budget": 12},
        provider_hard_stop=False, cooldown_seconds=0.0)
    assert state["paused"] is True
    assert "12/12" in state["pause_reason"]
    assert "OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT" in state["pause_reason"]

"""Cross-domain safety/invariance contracts. No named applicant is privileged."""
import json

import numpy as np
import pytest
from pydantic import ValidationError

from cv_ranker.config import Settings
from cv_ranker.llm import LLMError, OpenRouterStructuredLLM
from cv_ranker.scoring import assign_ranks, score_candidate
from cv_ranker.schemas import (LLMAssessmentItem,
                               LLMCandidateAssessmentResponse,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.unified import (UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse,
                               _invoke_required_id_group, _keyed_response_schema,
                               _map_response, _repair_nonatomic_source_metadata,
                               plan_evidence_batches)


class FlatEncoder:
    fingerprint = "system-contracts-test"

    def embed_documents(self, texts):
        return np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1))

    def embed_queries(self, texts):
        return np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1))


class RecordedLLM:
    disabled_reason = None

    def __init__(self, responder):
        self.responder = responder
        self.calls = []
        self.settings = Settings(llm_provider="ollama")

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        request = json.loads(user_prompt)
        self.calls.append(request)
        return self.responder(request)


def req(rid, name, priority="required"):
    return ValidatedRequirement(requirement_id=rid, name=name,
                                priority=priority, jd_evidence=name)


def test_pdf_bullets_split_separate_education_and_project_claims():
    text = ("Education:\n\uf0b7BS Nursing | University, 2023\n"
            "Projects:\n\uf0b7Created a patient intake tracker.\n"
            "\uf0b7Never used diagnostic ultrasound.\n")
    segments = segment_resume(text)
    assert any(s.section == "education" and s.text.startswith("BS Nursing") for s in segments)
    project = [s for s in segments if s.section == "projects"]
    assert len(project) == 2
    assert all(len(s.source_lines) == 1 for s in project)


def test_metadata_quote_is_not_cleared_for_unrelated_source():
    r = req("R1", "Warehouse inventory forecasting")
    report = LLMAssessmentItem(requirement_id="R1", status="matched",
                               evidence_ids=["S1"], matched_term="forecasting",
                               reason="The warehouse reports constitute forecasting.")
    source = {"S1": ResumeSegment("S1", "experience", "Delivered warehouse inventory reports.")}
    result = _repair_nonatomic_source_metadata(
        LLMCandidateAssessmentResponse(assessments=[report]), [r], source)
    assert result.assessments[0].matched_term == "forecasting"


def test_duplicate_missing_and_unexpected_ids_are_invalid():
    required = [req("R1", "Quality inspection"), req("R2", "Supplier coordination")]
    duplicate = UnifiedItem(requirement_id="R1", decision="not_found",
                            reason="No source was given for this particular requirement.")
    _, _, invalid = _map_response(
        UnifiedResponse(assessments=[duplicate, duplicate]), required, set())
    assert invalid == {"R1", "R2"}
    extraneous = duplicate.model_copy(update={"requirement_id": "UNKNOWN"})
    _, _, invalid = _map_response(
        UnifiedResponse(assessments=[duplicate,
                                     duplicate.model_copy(update={"requirement_id": "R2"}),
                                     extraneous]), required, set())
    assert invalid == {"R1", "R2"}


def test_required_id_schema_fails_closed_for_missing_last_id_across_domains():
    ids = ("R001", "R002", "R018")
    schema = _keyed_response_schema(ids)
    properties = schema.model_json_schema()
    assert properties["required"] == list(ids)
    assert properties["additionalProperties"] is False
    assert set(properties["properties"]) == set(ids)
    answer = {rid: {"decision": "not_found",
                    "reason": "No candidate-provided evidence supports this requirement."}
              for rid in ids}
    with pytest.raises(ValidationError):
        schema.model_validate({key: value for key, value in answer.items() if key != ids[-1]})
    with pytest.raises(ValidationError):
        schema.model_validate({**answer, "invented": answer[ids[0]]})
    assert len(schema.model_validate(answer).model_dump()) == len(ids)


def test_real_cloud_adapter_validates_keyed_ids_and_rejects_duplicate_json_keys():
    settings = Settings(llm_provider="ollama", llm_retries=0)
    llm = OpenRouterStructuredLLM(settings)
    seen = []
    answer = {rid: {"decision": "not_found", "relation": "absent", "evidence_ids": [],
                    "matched_term": None,
                    "reason": "No candidate source establishes this requested duty."}
              for rid in ("R001", "R018")}

    def respond(payload):
        seen.append(payload)
        return {"choices": [{"message": {"content": json.dumps(answer)},
                              "finish_reason": "stop"}]}

    llm._post_chat = respond
    group = [req("R001", "Hospital admission coordination"),
             req("R018", "Financial forecasting")]
    rows = _invoke_required_id_group(llm=llm, group=group,
                                     user_prompt='{"sources":[],"requirements":[]}')
    assert [item.requirement_id for item in rows.assessments] == ["R001", "R018"]
    assert seen[0]["response_format"]["json_schema"]["schema"]["required"] == ["R001", "R018"]
    # A schema-valid envelope must not silently turn duplicate JSON properties
    # into a last-write-wins assessment, regardless of JD item name.
    text = json.dumps(answer)
    text = text[:-1] + ',"R018":' + json.dumps(answer["R018"]) + "}"
    llm._post_chat = lambda payload: {"choices": [{"message": {"content": text},
                                                    "finish_reason": "stop"}]}
    with pytest.raises(LLMError, match="structured JSON did not validate"):
        _invoke_required_id_group(llm=llm, group=group,
                                  user_prompt='{"sources":[],"requirements":[]}')


def test_keyed_schema_missing_response_is_not_silently_treated_as_not_found():
    llm = OpenRouterStructuredLLM(Settings(llm_provider="ollama", llm_retries=0))
    answer = {"R001": {"decision": "found", "evidence_ids": ["S001"],
                       "reason": "The source directly describes the named work."}}
    llm._post_chat = lambda payload: {"choices": [{"message": {"content": json.dumps(answer)},
                                                    "finish_reason": "stop"}]}
    with pytest.raises(LLMError, match="structured JSON did not validate"):
        _invoke_required_id_group(
            llm=llm,
            group=[req("R001", "Clinical intake"), req("R002", "Supplier negotiations")],
            user_prompt='{"sources":[],"requirements":[]}',
        )


def test_unverified_will_not_reduce_cv_score_or_receive_rank():
    jd = [req("R1", "Supplier compliance review"),
          req("R2", "Monthly cash-flow planning"),
          req("P1", "Risk dashboards", "preferred")]
    scored = [RequirementAssessment(requirement_id="R1", status="matched", unified_status="Found"),
              RequirementAssessment(requirement_id="R2", status="uncertain",
                                    unified_status="Unverified", assessment_state="unverified"),
              RequirementAssessment(requirement_id="P1", status="not_matched", unified_status="Not Found")]
    candidate = score_candidate(candidate_name="Partial", requirements=jd,
                                assessments=scored, evaluation_mode="llm_assessed", errors=[])
    assert candidate.matched_required == 1 and candidate.total_required == 2
    assert candidate.primary_score is None and candidate.required_score is None
    assert candidate.evaluation_mode == "failed"
    complete = score_candidate(candidate_name="Complete", requirements=jd,
                               assessments=[row.model_copy(update={
                                   "status": "not_matched", "unified_status": "Not Found",
                                   "assessment_state": "verified"}) if row.requirement_id == "R2" else row
                                   for row in scored], evaluation_mode="llm_assessed", errors=[])
    ordered = assign_ranks([candidate, complete])
    assert [c.candidate_name for c in ordered] == ["Complete", "Partial"]
    assert ordered[0].rank == 1 and ordered[1].rank is None


def test_ranking_preferred_tiebreak_and_equal_rank_use_identical_contract():
    jd = [req("R1", "Field inspection"), req("P1", "Audit software", "preferred")]
    def candidate(name, preferred):
        return score_candidate(candidate_name=name, requirements=jd,
                               assessments=[RequirementAssessment(requirement_id="R1", status="matched"),
                                            RequirementAssessment(requirement_id="P1",
                                                                  status="matched" if preferred else "not_matched")],
                               evaluation_mode="llm_assessed", errors=[])
    rows = assign_ranks([candidate("Alpha", False), candidate("Zulu", True),
                         candidate("Beta", False)])
    assert [(r.candidate_name, r.rank) for r in rows] == [
        ("Zulu", 1), ("Alpha", 2), ("Beta", 2)]


def test_output_capacity_caps_group_size_without_extra_verification_passes():
    requirements = [req(f"R{i}", f"Operational task {i}") for i in range(18)]
    sources = [ResumeSegment("S1", "experience", "Implemented operational improvements.")]
    hits = {r.requirement_id: ["S1"] for r in requirements}
    llm = RecordedLLM(lambda request: UnifiedResponse(assessments=[]))
    groups = plan_evidence_batches(requirements, sources, hits, llm,
                                   max_requirements=18, max_hits=8)
    assert len(groups) == 3
    assert max(len(group) for group, _, _ in groups) <= 7


def test_cross_department_source_verdicts_are_preserved_without_field_catalogue(tmp_path):
    cases = [
        ("Clinical intake workflow", "Created a patient intake workflow for shift nurses."),
        ("Monthly cash-flow planning", "Developed monthly cash-flow planning for a retail business."),
        ("Industrial quality auditing", "Implemented industrial quality auditing in a factory."),
    ]
    requirements = [req(f"R{i}", name) for i, (name, _) in enumerate(cases, 1)]
    segments = [ResumeSegment(f"S{i:03d}", "experience", statement)
                for i, (_, statement) in enumerate(cases, 1)]

    def response(request):
        return UnifiedResponse(assessments=[UnifiedItem(
            requirement_id=entry["id"], decision="found",
            evidence_ids=[f"S{int(entry['id'][1:]):03d}"],
            reason="The cited completed work demonstrates the named requested duty.")
            for entry in request["requirements"]])

    llm = RecordedLLM(response)
    engine = UnifiedEvidenceEngine(llm.settings, llm,
                                   cache_path=tmp_path / "cache.db", encoder=FlatEncoder())
    try:
        decisions, metrics = engine.assess(requirements, segments,
                                           "\n".join(s.text for s in segments),
                                           candidate_id="generic-worker")
    finally:
        engine.close()
    assert [row.unified_status for row in decisions] == ["Found"] * 3
    assert metrics.unresolved_criteria == 0 and metrics.llm_calls == 1


def test_technical_error_after_one_correction_is_unverified_not_absent(tmp_path):
    requirement = req("R1", "Building strategic supplier partnerships")
    segment = ResumeSegment("S1", "experience", "Collaborated on procurement coordination.")
    def response(request):
        return UnifiedResponse(assessments=[UnifiedItem(
            requirement_id="R1", decision="found", evidence_ids=["S999"],
            reason="A fabricated citation for a particular requested business duty.")])
    llm = RecordedLLM(response)
    engine = UnifiedEvidenceEngine(llm.settings, llm,
                                   cache_path=tmp_path / "cache.db", encoder=FlatEncoder())
    try:
        rows, metrics = engine.assess([requirement], [segment], segment.text,
                                      candidate_id="generic-worker")
    finally:
        engine.close()
    assert len(llm.calls) == 3
    assert metrics.final_verification_calls == 1
    assert metrics.correction_calls == 1 and metrics.unresolved_criteria == 1
    assert rows[0].assessment_state == "unverified" and rows[0].unified_status == "Unverified"
    assert score_candidate(candidate_name="Worker", requirements=[requirement],
                           assessments=rows, evaluation_mode="llm_assessed",
                           errors=[]).primary_score is None


def test_explicit_denial_can_coexist_with_completed_transferable_work(tmp_path):
    requirement = req("R1", "DispatchFramework")

    def run(text, candidate):
        segment = ResumeSegment("S001", "experience", text)
        llm = RecordedLLM(lambda package: UnifiedResponse(assessments=[UnifiedItem(
            requirement_id="R1", decision="transferable", evidence_ids=["S001"],
            reason="The described alternative workflow overlaps the requested function.")]))
        engine = UnifiedEvidenceEngine(llm.settings, llm, cache_path=tmp_path / f"{candidate}.db",
                                       encoder=FlatEncoder())
        try:
            rows, _ = engine.assess([requirement], [segment], text, candidate_id=candidate)
            return rows[0]
        finally:
            engine.close()

    related = run("Never used DispatchFramework; built an independent vehicle dispatch workflow.", "alt")
    only_denied = run("Never used DispatchFramework in professional assignments.", "denial")
    assert related.unified_status == "Transferable" and related.status == "not_matched"
    assert only_denied.unified_status == "Not Found" and only_denied.status == "not_matched"

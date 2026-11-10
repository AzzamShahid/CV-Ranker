"""V4.8.5 generic evidence consistency without new searches or LLM passes."""
import json
from pathlib import Path

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.evidence_bridge import performed_functional_bridge
from cv_ranker.schemas import RequirementConstraint, ValidatedRequirement
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.unified import UnifiedEvidenceEngine, UnifiedItem, UnifiedResponse


class FlatEncoder:
    fingerprint = "v485-test-only-existing-embedding-interface"

    def embed_documents(self, texts):
        return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)

    def embed_queries(self, texts):
        return np.array([[1.0, 0.0] for _ in texts], dtype=np.float32)


class PredeterminedLLM:
    disabled_reason = None

    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = 0

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        returned = next(self.answers)
        packaged = json.loads(user_prompt)
        assert len(packaged["requirements"]) == 1
        assert all(sid in {s["id"] for s in packaged["sources"]}
                   for sid in returned.evidence_ids)
        return UnifiedResponse(assessments=[returned])


def _req(name="FrameworkX"):
    return ValidatedRequirement(requirement_id="R001", name=name,
                                priority="required", jd_evidence=name,
                                constraint=RequirementConstraint(
                                    kind="skill", operator="single"))


def _segments():
    return [
        ResumeSegment("S001", "projects",
                      "Completed a response platform with AltTool; same routing, "
                      "retrieval and evidence functions often achieved with FrameworkX.", (1,)),
        ResumeSegment("S002", "experience",
                      "Delivered AltTool retrieval software with evidence routing "
                      "for customer-facing teams.", (2,)),
        ResumeSegment("S003", "summary", "Has not used FrameworkX professionally.", (3,)),
    ]


def _run(tmp_path, llm, segments, req=None):
    engine = UnifiedEvidenceEngine(
        Settings(llm_provider="ollama"), llm,
        cache_path=tmp_path / "semantic_cache.sqlite", encoder=FlatEncoder(),
    )
    try:
        return engine.assess([req or _req()], segments, "\n".join(s.text for s in segments),
                             candidate_id="v485-synthetic-candidate")
    finally:
        engine.close()


def test_named_tool_denial_with_independent_compared_work_is_transferable(tmp_path):
    llm = PredeterminedLLM([UnifiedItem(
        requirement_id="R001", decision="not_found", evidence_ids=["S003"],
        reason="No direct experience with the named framework is established."
    )])
    results, metrics = _run(tmp_path, llm, _segments())
    decision = results[0]
    assert llm.calls == metrics.llm_calls == 1
    assert metrics.correction_calls == 0
    assert decision.status == "not_matched"  # Never a point.
    assert decision.unified_status == "Transferable"
    assert decision.review_recommended
    assert decision.evidence_ids == ["S001", "S002", "S003"]
    assert "Delivered AltTool retrieval software" in decision.evidence_segments[1].text
    assert "Direct use" in decision.reason


def test_comparison_without_independent_completed_work_is_not_transferable(tmp_path):
    segments = _segments()
    segments[1] = ResumeSegment("S002", "experience",
                                  "Attended training sessions on separate subjects.", (2,))
    assert performed_functional_bridge(_req(), {s.segment_id: s for s in segments}) is None
    llm = PredeterminedLLM([UnifiedItem(
        requirement_id="R001", decision="not_found", evidence_ids=["S003"],
        reason="Only a comparison and denial are reported; no completed overlapping work."
    )])
    decisions, _ = _run(tmp_path, llm, segments)
    assert decisions[0].unified_status == "Not Found"


def test_fictional_sara_cv_has_independent_functional_bridge():
    fixture = (Path(__file__).resolve().parents[1] /
               "sample_data/applied_ai_resumes/03_sara_functional_transfer.txt")
    segments = segment_resume(fixture.read_text(encoding="utf-8"))
    requirement = _req("LangChain")
    original = {s.segment_id: s for s in segments}
    bridge = performed_functional_bridge(requirement, original)
    assert bridge is not None
    comparison_id, work_id, overlap = bridge
    assert comparison_id != work_id and len(overlap) >= 2
    assert "comparable" in original[comparison_id].text.casefold() or (
        "same" in original[comparison_id].text.casefold())
    assert "delivered" in original[work_id].text.casefold()


def test_repaired_first_pass_source_error_is_a_resolved_diagnostic(tmp_path):
    first = UnifiedItem(
        requirement_id="R001", decision="found", evidence_ids=["S001"],
        matched_term="NotInTheSource",
        reason="Named experience reported but the quoted term was invented."
    )
    second = UnifiedItem(
        requirement_id="R001", decision="found", evidence_ids=["S001"],
        matched_term="FrameworkX",
        reason="The CV explicitly lists the named skill in a positive skills section."
    )
    llm = PredeterminedLLM([first, second])
    source = [ResumeSegment("S001", "skills", "FrameworkX, OtherTool", (1,))]
    decisions, metrics = _run(tmp_path, llm, source)
    # The exact positive named source independently establishes this claim;
    # optional fabricated quote metadata is dropped without a paid retry.
    assert llm.calls == 1 and metrics.correction_calls == 0
    assert decisions[0].unified_status == "Found"
    assert not metrics.warnings
    assert not metrics.resolved_validation_notices
    assert metrics.public()["resolved_validation_notices"] == metrics.resolved_validation_notices


def test_supervisor_ui_uses_supported_streamlit_width_property():
    source = (Path(__file__).resolve().parents[1] /
              "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    assert "use_container_width" not in source
    assert 'width="stretch"' in source

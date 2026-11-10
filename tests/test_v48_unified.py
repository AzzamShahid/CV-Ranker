"""V4.8 isolation, evidence packing, and model-request budget contracts."""
import json
from pathlib import Path

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.segments import ResumeSegment
from cv_ranker.scoring import score_candidate
from cv_ranker.ui.evidence_inspection import segment_ledger
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.ui_support import final_leaderboard_rows
from cv_ranker.llm import LLMError, OpenRouterStructuredLLM, StructuredLLM
from cv_ranker.schemas import CandidateAssessmentResponse
from cv_ranker.unified import (_payload, UnifiedEvidenceEngine, UnifiedItem,
                               UnifiedResponse)


class FakeEncoder:
    fingerprint = "test-v48-embeddinggemma-interface"

    def _vector(self, text):
        t = text.casefold()
        return [2.0, 0.0, 0.0] if "python" in t else [0.0, 2.0, 0.0]

    def embed_documents(self, texts):
        return np.array([self._vector(t) for t in texts], dtype=np.float32)

    def embed_queries(self, texts):
        return np.array([self._vector(t) for t in texts], dtype=np.float32)


class FakeLLM:
    disabled_reason = None

    def __init__(self, bad_first=False):
        self.calls = 0
        self.bad_first = bad_first
        self.payloads = []

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        payload = json.loads(user_prompt)
        self.payloads.append(payload)
        rows = []
        for req in payload["requirements"]:
            if req["name"] == "Python":
                rows.append(UnifiedItem(
                    requirement_id=req["id"], decision="found",
                    evidence_ids=["S999" if self.bad_first and self.calls == 1 else "S001"],
                    matched_term="Python", reason="The applicant lists Python as a stated skill."))
            else:
                rows.append(UnifiedItem(
                    requirement_id=req["id"], decision="transferable",
                    evidence_ids=["S002"], matched_term="state-graph",
                    reason="A developed state-graph workflow is analogous but not the named tool."))
        return UnifiedResponse(assessments=rows)


class AlwaysInvalidLLM(FakeLLM):
    """Simulate a model that keeps hallucinating one selected source ID."""
    def __init__(self, invalid_name):
        super().__init__()
        self.invalid_name = invalid_name

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        result = super().invoke_structured(system_prompt=system_prompt,
                                           user_prompt=user_prompt, schema=schema)
        payload = json.loads(user_prompt)
        req_name = {item["id"]: item["name"] for item in payload["requirements"]}
        return UnifiedResponse(assessments=[
            row.model_copy(update={"decision": "found", "evidence_ids": ["S999"]})
            if req_name.get(row.requirement_id) == self.invalid_name else row
            for row in result.assessments
        ])


def _fixtures():
    requirements = [
        ValidatedRequirement(requirement_id="R001", name="Python",
                             priority="required", jd_evidence="Python"),
        ValidatedRequirement(requirement_id="R002", name="LangGraph",
                             priority="preferred", jd_evidence="LangGraph"),
    ]
    sources = [
        ResumeSegment(segment_id="S001", section="skills", text="Python, FastAPI", source_lines=(1,)),
        ResumeSegment(segment_id="S002", section="projects",
                      text="Developed a state-graph workflow with routing and tools.", source_lines=(2,)),
    ]
    return requirements, sources


def test_source_payload_deduplicates_text_with_repeated_ids():
    requirements, segments = _fixtures()
    text = _payload(requirements, {s.segment_id: s for s in segments},
                    {"R001": ["S001", "S002"], "R002": ["S002", "S001"]}, 2)
    payload = json.loads(text)
    assert [source["id"] for source in payload["sources"]] == ["S001", "S002"]
    assert text.count("Developed a state-graph workflow") == 1
    assert payload["requirements"][1]["priority_segments"] == ["S002", "S001"]


def test_one_assessment_call_and_transfer_has_no_point(tmp_path):
    requirements, segments = _fixtures()
    llm = FakeLLM()
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "vectors.db",
                                   encoder=FakeEncoder())
    try:
        assessments, metrics = engine.assess(requirements, segments,
                                              "\n".join(s.text for s in segments),
                                              candidate_id="candidate_1")
    finally:
        engine.close()
    assert llm.calls == 1
    assert metrics.llm_calls == 1 and metrics.correction_calls == 0
    assert [a.unified_status for a in assessments] == ["Found", "Transferable"]
    assert [a.status for a in assessments] == ["matched", "not_matched"]
    assert all(len({s["id"] for s in payload["sources"]}) == len(payload["sources"])
               for payload in llm.payloads)


def test_bad_source_id_gets_one_grouped_correction(tmp_path):
    requirements, segments = _fixtures()
    llm = FakeLLM(bad_first=True)
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "vectors.db",
                                   encoder=FakeEncoder())
    try:
        assessments, metrics = engine.assess(requirements, segments,
                                              "\n".join(s.text for s in segments),
                                              candidate_id="candidate_2")
    finally:
        engine.close()
    assert metrics.llm_calls == llm.calls == 2
    assert metrics.correction_calls == 1
    assert "correction" in llm.payloads[1]
    assert [a.unified_status for a in assessments] == ["Found", "Transferable"]
    assert "S999" not in {sid for a in assessments for sid in a.evidence_ids}


def test_unresolved_model_row_does_not_discard_verified_peer(tmp_path):
    requirements, segments = _fixtures()
    llm = AlwaysInvalidLLM(invalid_name="LangGraph")
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "vectors.db", encoder=FakeEncoder())
    try:
        assessments, metrics = engine.assess(requirements, segments,
                                              "\n".join(s.text for s in segments),
                                              candidate_id="candidate_partial")
    finally:
        engine.close()
    assert llm.calls == metrics.llm_calls == 3
    assert metrics.final_verification_calls == 1
    assert metrics.correction_calls == 1
    assert metrics.unresolved_criteria == 1
    assert metrics.exact_source_recoveries == 0
    assert assessments[0].status == "matched" and assessments[0].unified_status == "Found"
    assert assessments[1].status == "uncertain" and assessments[1].unified_status == "Unverified"
    assert assessments[1].assessment_state == "unverified"
    assert assessments[1].review_recommended
    assert "UNVERIFIED" in assessments[1].reason
    assert assessments[1].evidence_ids and "S999" not in assessments[1].evidence_ids


def test_unresolved_row_can_recover_stated_skill_without_extra_llm(tmp_path):
    requirements, segments = _fixtures()
    llm = AlwaysInvalidLLM(invalid_name="Python")
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), llm,
                                   cache_path=tmp_path / "vectors.db", encoder=FakeEncoder())
    try:
        assessments, metrics = engine.assess(requirements, segments,
                                              "\n".join(s.text for s in segments),
                                              candidate_id="candidate_direct_recovery")
    finally:
        engine.close()
    assert metrics.llm_calls == llm.calls == 2
    # Independently recovered direct evidence is not an unresolved criterion.
    assert metrics.unresolved_criteria == 0 and metrics.exact_source_recoveries == 1
    assert any("R001:" in note for note in metrics.resolved_validation_notices)
    assert assessments[0].unified_status == "Found" and assessments[0].review_recommended
    assert assessments[0].evidence_ids == ["S001"]


def test_source_page_no_longer_references_removed_shadow_state():
    source = (Path(__file__).resolve().parents[1] /
              "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    body = source.split("def _source_segments_page(", 1)[1].split("def _technical(", 1)[0]
    assert "semantic_ids" not in body
    assert '"Prioritized for assessment"' in body
    assert "selected_source_ids" in body


def test_source_page_renders_with_only_unified_retrieval_state():
    """Execute the real tab function body without starting Streamlit."""
    import ast
    from types import SimpleNamespace

    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(
        encoding="utf-8")
    functions = [node for node in ast.parse(source).body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == "_source_segments_page"]

    class FakeStreamlit:
        def __init__(self):
            self.session_state = {
                "cv_source_ledgers": {"0": {"source": "retained"}},
                "cv_unified_metrics": {"0": {"selected_sources": 1,
                                             "selected_source_ids": ["S001"]}},
            }
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def columns(self, widths):
            return [self] * (widths if isinstance(widths, int) else len(widths))

        def selectbox(self, label, values, **kwargs):
            return values[0]

        def text_input(self, *args, **kwargs):
            return ""

        def dataframe(self, rows, **kwargs):
            self.rows = rows

        def expander(self, *args, **kwargs):
            return self

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    fake_st = FakeStreamlit()
    segments = [ResumeSegment(segment_id="S001", section="skills",
                              text="Python, FastAPI", source_lines=())]
    environment = {"RankingReport": object, "st": fake_st, "json": json,
                   "resume_segments": lambda ledger: segments,
                   "highlighted_source_html": lambda value, query: value}
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, "cv_ranker/ui/dashboard.py", "exec"), environment)
    report = SimpleNamespace(candidates=[SimpleNamespace(
        candidate_name="Candidate A", assessments=[])])
    environment["_source_segments_page"](report)

    assert len(fake_st.rows) == 1
    assert fake_st.rows[0]["Prioritized for assessment"] == "Yes"
    assert fake_st.rows[0]["Primary citation"] == ""


def test_final_leaderboard_counts_use_same_validated_assessments(tmp_path):
    requirements, segments = _fixtures()
    engine = UnifiedEvidenceEngine(Settings(llm_provider="ollama"), FakeLLM(),
                                   cache_path=tmp_path / "vectors.db", encoder=FakeEncoder())
    try:
        assessments, _ = engine.assess(requirements, segments,
                                       "\n".join(s.text for s in segments),
                                       candidate_id="candidate_3")
    finally:
        engine.close()
    candidate = score_candidate(candidate_name="sample.txt", candidate_source="sample.txt",
                                requirements=requirements, assessments=assessments,
                                evaluation_mode="llm_assessed", errors=[])
    report = RankingReport(job_description_source="jd.txt", jd_validation_mode="test",
                           yake_candidates=[], requirements=requirements, candidates=[candidate])
    final = reconcile_unified_candidate(report, 0, segment_ledger(segments))
    assert candidate.matched_required == final["Required matched"] == 1
    assert candidate.matched_preferred == final["Preferred matched"] == 0
    assert final["Transferable"] == 1
    assert final["Criteria"][0]["Checkpoints"][0]["Validated against CV"]
    assert not final["Criteria"][0]["Review recommended"]


def test_provider_failure_is_unscored_not_zero_percent():
    requirements, _ = _fixtures()
    failed = CandidateResult(candidate_name="unavailable.txt", candidate_source="unavailable.txt",
                             primary_score=None, evaluation_mode="failed",
                             errors=["Provider rate limit; rerun later."])
    report = RankingReport(job_description_source="jd.txt", jd_validation_mode="test",
                           yake_candidates=[], requirements=requirements, candidates=[failed])
    final = reconcile_unified_candidate(report, 0, [])
    row = final_leaderboard_rows(report, {"0": final})[0]
    assert row["Score"] is None
    assert row["Required"] == "Not assessed"
    assert row["Rank"] == "-"
    assert row["Review"] == "Assessment unavailable · rerun"


def test_context_refusal_needs_no_initialized_request_counter():
    # Mirrors minimal __new__ constructions used in prior phase tests.
    for cls, settings in (
        (StructuredLLM, Settings(ollama_num_ctx=2048, ollama_num_predict=1024)),
        (OpenRouterStructuredLLM,
         Settings(llm_provider="openrouter", openrouter_api_key="dummy-test-only",
                  ollama_num_ctx=2048, ollama_num_predict=1024)),
    ):
        client = cls.__new__(cls)
        client.settings = settings
        client.disabled_reason = None
        try:
            client.invoke_structured(system_prompt="test", user_prompt="x" * 10000,
                                     schema=CandidateAssessmentResponse)
        except LLMError as exc:
            assert "Context budget exceeded" in str(exc)
        else:
            raise AssertionError("Oversized prompts must be refused before any call")
        assert getattr(client, "logical_calls", 0) == 0
        assert getattr(client, "http_attempts", 0) == 0

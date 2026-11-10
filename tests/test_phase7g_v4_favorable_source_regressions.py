"""Regression cases from Sara's exported 22-Oct final-evidence failure."""
import json
from pathlib import Path

from cv_ranker.documents import extract_text
from cv_ranker.schemas import (CandidateResult, EvidenceCitation, RankingReport,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.segments import segment_resume
from cv_ranker.ui.evidence_inspection import segment_ledger, literal_mentions
from cv_ranker.ui.final_decisions import FocusedJudgment, reconcile_candidate
from cv_ranker.ui_support import highlighted_source_html


SARA = (Path(__file__).resolve().parents[1] /
        "sample_data/applied_ai_documents/pdf/03_sara_functional_transfer.pdf")


def test_contrast_without_langchain_is_never_positive_cv_claim():
    segments = segment_resume(extract_text(SARA))
    req = ValidatedRequirement(requirement_id="R001", name="LangChain",
                               priority="required", jd_evidence="LangChain")
    found = literal_mentions(req, segments)
    assert any("rather than LangChain" in hit["Text"] for hit in found)
    assert not any(hit["Finding"] in {"Explicit CV skill claim", "Named in work/project account"}
                   for hit in found)


def test_recover_implicit_skills_platform_and_two_transfers_from_original_pdf():
    segments = segment_resume(extract_text(SARA))
    by_text = {s.segment_id: s for s in segments}
    requirements = [
        ("Python", "required"), ("Machine Learning", "required"),
        ("Deep Learning", "required"), ("LangChain", "required"),
        ("Model evaluation", "required"), ("AI application development", "required"),
        ("LangGraph", "preferred"), ("Time-series forecasting", "preferred"),
        ("Google Cloud", "preferred"),
    ]
    frozen = [ValidatedRequirement(requirement_id=f"R{i:03}", name=n,
             priority=p, jd_evidence=n) for i, (n, p) in enumerate(requirements, 1)]
    python = next(s for s in segments if s.section == "skills" and "Python" in s.text)
    primary = [RequirementAssessment(
        requirement_id=req.requirement_id,
        status="matched" if req.name == "Python" else "not_matched",
        evidence_ids=[python.segment_id] if req.name == "Python" else [],
        evidence_segments=[EvidenceCitation(segment_id=python.segment_id,
                                           section=python.section, text=python.text)]
        if req.name == "Python" else []) for req in frozen]
    report = RankingReport(job_description_source="replay", jd_validation_mode="test",
                           yake_candidates=[], requirements=frozen,
                           candidates=[CandidateResult(candidate_name="Sara", rank=1,
                                       primary_score=16.67, assessments=primary)])

    class GroundedModel:
        def invoke_structured(self, **kwargs):
            req = json.loads(kwargs["user_prompt"])["frozen_requirement"]["name"]
            def cite(fragment, highlight, why):
                source = next(s for s in by_text.values() if fragment in s.text)
                return {"segment_id": source.segment_id, "why": why,
                        "highlight_terms": [highlight]}
            if req in {"Machine Learning", "Deep Learning"}:
                return FocusedJudgment(result="matched", explanation=(
                    "Trained a PyTorch transformer classifier on annotated documents; "
                    "this is performed neural-model training, not just a nearby title."),
                    supporting_sources=[cite("Trained PyTorch transformer", "PyTorch transformer",
                                             "Trained a neural transformer classifier with evaluation data")])
            if req == "Google Cloud":
                return FocusedJudgment(result="matched", explanation=(
                    "GCP Cloud Run and BigQuery are an affirmative self-reported Google Cloud skill; "
                    "the JD does not require a deployment project."),
                    supporting_sources=[cite("GCP Cloud Run", "GCP",
                                             "GCP Cloud Run and BigQuery listed affirmatively in skills")])
            if req == "LangChain":
                return FocusedJudgment(result="transferable", explanation=(
                    "Haystack retrieval and Python tool routing implement overlapping functions, "
                    "while the CV explicitly says without LangChain."),
                    supporting_sources=[cite("Implemented tool routing", "tool routing",
                                             "Implemented routing and answer generation with a different framework")])
            if req == "LangGraph":
                return FocusedJudgment(result="transferable", explanation=(
                    "The implemented Python state workflow overlaps graph orchestration; "
                    "LangGraph professional use is denied."),
                    supporting_sources=[cite("Orchestrated LLM calls", "conditional Python workflows",
                                             "Orchestrated branching, retries and tool calls without LangGraph")])
            if req == "Model evaluation":
                return FocusedJudgment(result="matched", explanation=(
                    "Designed and ran independent grounded-answer evaluation with measured coverage."),
                    supporting_sources=[cite("450-question grounded-answer audit", "grounded-answer audit",
                                             "Measured answer coverage and abstention from an actual audit")])
            if req == "AI application development":
                return FocusedJudgment(result="matched", explanation=(
                    "Delivered a customer-facing LLM assistant integrating retrieval and an API."),
                    supporting_sources=[cite("Delivered a customer-facing knowledge assistant", "knowledge assistant",
                                             "Delivered a working AI application to customers")])
            return FocusedJudgment(result="not_evidenced", explanation=(
                "The CV demonstrates seasonal anomaly screening but not forecasting "
                "future quantities or trends; these are distinct tasks."))

    final = reconcile_candidate(report, 0, segment_ledger(segments), llm=GroundedModel())
    by_name = {r["Requirement"]: r for r in final["Criteria"]}
    assert {by_name[n]["Result"] for n in ("Machine Learning", "Deep Learning", "Google Cloud")} == {"Found"}
    assert by_name["LangChain"]["Result"] == "Transferable"
    assert by_name["LangGraph"]["Result"] == "Transferable"
    assert by_name["Time-series forecasting"]["Result"] == "Not Found"
    assert final["Required matched"] == 5 and final["Required total"] == 6
    assert final["Preferred matched"] == 1 and final["Preferred total"] == 3
    assert final["Transferable"] == 2
    assert all(item["Why"] for item in final["Criteria"])
    assert all(item["Checkpoints"] for item in final["Criteria"] if item["Result"] in {"Found", "Transferable"})
    for skill, term in (("Deep Learning", "PyTorch transformer"), ("Google Cloud", "GCP")):
        checkpoint = next(c for c in by_name[skill]["Checkpoints"] if term in c["Highlight terms"])
        assert "<mark>" in highlighted_source_html(checkpoint["Text"], checkpoint["Highlight terms"])


def test_html_highlighter_supports_multiple_exact_phrases_without_untrusted_html():
    rendered = highlighted_source_html("GCP Cloud Run, PyTorch <script>bad</script>", ["GCP", "PyTorch"])
    assert "<mark>GCP</mark>" in rendered and "<mark>PyTorch</mark>" in rendered
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered


def test_flat_structured_retry_keeps_real_source_and_automatic_highlighting():
    from cv_ranker.ui.final_decisions import CompactFocusedJudgment
    req = ValidatedRequirement(requirement_id="R001", name="Google Cloud", priority="preferred",
                               jd_evidence="Google Cloud")
    report = RankingReport(job_description_source="JD", jd_validation_mode="test",
                           yake_candidates=[], requirements=[req], candidates=[CandidateResult(
                               candidate_name="Cloud", assessments=[RequirementAssessment(
                                   requirement_id="R001", status="not_matched")])])
    class FlatOnly:
        def invoke_structured(self, **kwargs):
            if kwargs["schema"] is FocusedJudgment:
                raise ValueError("Nested schema unavailable")
            assert kwargs["schema"] is CompactFocusedJudgment
            return CompactFocusedJudgment(result="matched",
                explanation="GCP Cloud Run is explicitly listed in the CV's skills section.",
                source_ids=["S001"])
    ledger = [{"segment_id": "S001", "section": "skills",
               "text": "GCP Cloud Run, BigQuery", "source_lines": []}]
    final = reconcile_candidate(report, 0, ledger, llm=FlatOnly())
    row = final["Criteria"][0]
    assert row["Result"] == "Found"
    assert row["Checkpoints"][0]["Highlight terms"] == ["GCP Cloud Run"]

"""Source-audited reconciliation regressions for the Sara V4 two-table conflict."""
from __future__ import annotations

from pathlib import Path

from cv_ranker.schemas import (CandidateResult, EvidenceCitation, RankingReport,
                               RequirementAssessment, RequirementConstraint,
                               ValidatedRequirement)
from cv_ranker.semantic.transferability import (
    AuditedCapability, CandidateProposalReport,
    EvidenceCitation as ShadowCitation, TransferabilityShadowReport,
)
from cv_ranker.ui.final_decisions import FocusedJudgment, reconcile_candidate


LEDGER = [
    {"segment_id": "S001", "section": "skills", "text": "GCP Cloud Run, BigQuery, Docker", "source_lines": []},
    {"segment_id": "S002", "section": "experience", "text": "Trained PyTorch transformer classifiers for document tagging.", "source_lines": []},
    {"segment_id": "S003", "section": "experience", "text": "Built comparable routing workflows with Haystack, without LangChain.", "source_lines": []},
    {"segment_id": "S004", "section": "skills", "text": "NLP, NER and text classification", "source_lines": []},
    {"segment_id": "S005", "section": "experience", "text": "Built demand-anomaly screening with seasonal features and out-of-time validation.", "source_lines": []},
]


def requirement(rid, name, priority, kind="skill"):
    return ValidatedRequirement(requirement_id=rid, name=name, priority=priority,
        jd_evidence=name, constraint=RequirementConstraint(kind=kind, origin="source_rules", requires_review=False))


def assessment(rid, status, sid=None, reason=""):
    original = next((s for s in LEDGER if s["segment_id"] == sid), None)
    return RequirementAssessment(requirement_id=rid, status=status,
        evidence_segments=[EvidenceCitation(segment_id=sid, section=original["section"], text=original["text"])] if original else [],
        evidence_ids=[sid] if sid else [], reason=reason)


def fixtures():
    requirements = [
        requirement("R001", "Google Cloud", "preferred"),
        requirement("R002", "Deep Learning", "required"),
        requirement("R003", "LangChain", "required"),
        requirement("R004", "Natural Language Processing", "required"),
        requirement("R005", "Time-series forecasting", "preferred"),
    ]
    cv = CandidateResult(candidate_name="Sara", rank=1, primary_score=33.3, evaluation_mode="mixed",
                         assessments=[
        assessment("R001", "matched", "S001", "The CV states Google Cloud via GCP Cloud Run."),
        assessment("R002", "not_matched"),
        assessment("R003", "uncertain", "S003", "Comparable routing, not the named tool."),
        assessment("R004", "not_matched"),
        assessment("R005", "matched", "S005", "Model thought anomaly detection meant forecasting."),
    ])
    report = RankingReport(job_description_source="test", jd_validation_mode="test",
                           yake_candidates=[], requirements=requirements, candidates=[cv])
    proposals = [
        ("R001", "not_evidenced", None, "No project uses the words Google Cloud."),
        ("R002", "direct", "S002", "Training transformer classifiers demonstrates deep learning."),
        ("R003", "transferable", "S003", "Haystack orchestration is functional overlap, not LangChain."),
        ("R004", "not_evidenced", None, "The model missed the NLP abbreviation."),
        ("R005", "direct", "S005", "Anomaly screening implies forecasting (incorrect)."),
    ]
    semantic = TransferabilityShadowReport(complete=True, candidate_count=1,
        frozen_required_count=3, planned_capability_count=5, warnings=[], candidates=[
        CandidateProposalReport(candidate_id="c1", candidate_name="Sara",
            original_primary_score=cv.primary_score, original_rank=cv.rank,
            status="completed_provisional", warnings=[], assessments=[
                AuditedCapability(requirement_id=rid, capability_id=rid,
                    relationship=relationship, explanation=why,
                    citations=[ShadowCitation(segment_id=sid,
                        exact_quote=next(s["text"] for s in LEDGER if s["segment_id"] == sid))] if sid else [],
                    citation_audit="source_validated" if sid else "not_cited")
                for rid, relationship, sid, why in proposals
            ])])
    return report, semantic


class FocusedModel:
    def __init__(self):
        self.calls = []

    def invoke_structured(self, **kwargs):
        prompt = kwargs["user_prompt"]
        self.calls.append(prompt)
        if '"id": "R002"' in prompt:
            return FocusedJudgment(result="matched", explanation="Training PyTorch transformers is an applied deep-learning task.",
                supporting_sources=[{"segment_id": "S002", "why": "Trained transformer neural classifiers in a work role."}])
        if '"id": "R005"' in prompt:
            return FocusedJudgment(result="not_evidenced", explanation="Anomaly screening does not demonstrate forecasting future numeric values.",
                supporting_sources=[])
        raise AssertionError("Unnecessary model call")


def test_one_final_result_per_requirement_and_counts_use_both_assessments():
    report, semantic = fixtures()
    model = FocusedModel()
    initial = report.model_dump()
    final = reconcile_candidate(report, 0, LEDGER, semantic, llm=model)
    assert report.model_dump() == initial  # V4 forensic report remains immutable
    assert len(final["Criteria"]) == 5
    assert len({r["ID"] for r in final["Criteria"]}) == 5
    by_id = {r["ID"]: r for r in final["Criteria"]}
    assert by_id["R001"]["Result"] == "Found"  # GCP claim beats shadow false negative
    assert by_id["R001"]["Evidence level"] == "Stated in skills"
    assert by_id["R002"]["Result"] == "Found"  # Deep Learning verified using work
    assert by_id["R003"]["Result"] == "Transferable"  # different named tool; not an exact match
    assert by_id["R004"]["Result"] == "Found"  # literal NLP recovered
    assert by_id["R005"]["Result"] == "Not Found"  # screening != forecasting
    assert final["Required matched"] == 2 and final["Required total"] == 3
    assert final["Preferred matched"] == 1 and final["Preferred total"] == 2
    assert final["Transferable"] == 1
    assert len(model.calls) == 2


def test_all_segments_and_explanations_survive_deduplication():
    report, semantic = fixtures()
    final = reconcile_candidate(report, 0, LEDGER, semantic, llm=FocusedModel())
    rows = {r["ID"]: r for r in final["Criteria"]}
    cloud = rows["R001"]["Checkpoints"]
    assert [item["Segment"] for item in cloud] == ["S001"]
    assert "V4 primary citation" in cloud[0]["Sources"]
    assert cloud[0]["Why"] and cloud[0]["Text"] == LEDGER[0]["text"]
    deep = rows["R002"]["Checkpoints"]
    assert [item["Segment"] for item in deep] == ["S002"]
    assert "AI relationship citation" in deep[0]["Sources"]
    assert "Focused final verification" in deep[0]["Sources"]
    assert all(item["Why"] for row in final["Criteria"] for item in row["Checkpoints"])


def test_unavailable_model_only_reviews_disputed_capabilities():
    report, semantic = fixtures()
    final = reconcile_candidate(report, 0, LEDGER, semantic)
    by_id = {r["ID"]: r for r in final["Criteria"]}
    assert by_id["R001"]["Result"] == "Found"
    assert by_id["R004"]["Result"] == "Found"
    assert by_id["R003"]["Result"] == "Transferable"
    assert by_id["R002"]["Result"] == "Not Found"
    assert by_id["R002"]["Review recommended"] is True
    assert by_id["R005"]["Result"] == "Found"  # keep original sourced decision if second pass unavailable
    assert final["Provisional"] is True


def test_fake_semantic_quote_cannot_itself_award_skill_but_real_source_can_be_reexamined():
    report, semantic = fixtures()
    proposal = semantic.candidates[0].assessments[1]
    altered = proposal.model_copy(update={"citations": [ShadowCitation(segment_id="S002", exact_quote="They built every cloud product")],
                                  "citation_audit": "source_validated"})
    candidate = semantic.candidates[0].model_copy(update={
        "assessments": [semantic.candidates[0].assessments[0], altered] + semantic.candidates[0].assessments[2:]
    })
    altered_semantic = semantic.model_copy(update={"candidates": [candidate]})
    final = reconcile_candidate(report, 0, LEDGER, altered_semantic, llm=FocusedModel())
    deep = next(r for r in final["Criteria"] if r["ID"] == "R002")
    assert deep["Result"] == "Found"  # independent, source-cited focused model recovered actual work
    assert all("They built every cloud product" not in c["Text"] for c in deep["Checkpoints"])
    assert any("Focused final verification" in c["Sources"] for c in deep["Checkpoints"])


def test_named_tool_denial_overrules_a_hallucinated_direct_verdict():
    report, semantic = fixtures()
    old = semantic.candidates[0].assessments[2]
    proposal = old.model_copy(update={"relationship": "direct"})
    candidate = semantic.candidates[0].model_copy(update={
        "assessments": semantic.candidates[0].assessments[:2] +
                       [proposal] + semantic.candidates[0].assessments[3:]
    })
    altered = semantic.model_copy(update={"candidates": [candidate]})

    class IncorrectModel(FocusedModel):
        def invoke_structured(self, **kwargs):
            if '"id": "R003"' in kwargs["user_prompt"]:
                return FocusedJudgment(result="matched", explanation="Incorrectly claimed that Haystack proves named LangChain usage.",
                    supporting_sources=[{"segment_id": "S003", "why": "Wrongly interprets text saying without LangChain."}])
            return super().invoke_structured(**kwargs)

    final = reconcile_candidate(report, 0, LEDGER, altered, llm=IncorrectModel())
    langchain = next(r for r in final["Criteria"] if r["ID"] == "R003")
    assert langchain["Result"] == "Not Found"
    assert langchain["Review recommended"] is True
    assert any("explicit named-skill denial" in msg for msg in final["Notices"])


def test_ui_only_calls_one_final_matrix_and_retains_original_source_viewer():
    text = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    candidate_fn = text.split("def _candidate_evidence(", 1)[1].split("def _jd_details(", 1)[0]
    assert candidate_fn.count("st.dataframe(") == 1
    assert "_semantic_review(" not in candidate_fn
    assert "03  CV source segments" in text
    assert "cv_final_decisions.csv" in candidate_fn

"""Regression checks for final evidence and presentation after supervisor review.

All applicants and employers below are fictional. Transferable gives no score.
"""
from pathlib import Path

from cv_ranker.schemas import (
    CandidateResult, EvidenceCitation, RankingReport, RequirementAssessment,
    RequirementConstraint, ValidatedRequirement,
)
from cv_ranker.ui.final_decisions import FocusedJudgment, reconcile_candidate


LEDGER = [
    {"segment_id": "S001", "section": "summary",
     "text": "I develop knowledge-grounded assistants with Haystack rather than LangChain."},
    {"segment_id": "S002", "section": "experience",
     "text": "Implemented Haystack tool routing, document retrieval, and evidence assembly for a customer assistant."},
    {"segment_id": "S003", "section": "projects",
     "text": "Knowledge-grounded response platform: Haystack with hosted LLM API; same retrieval, tool routing and evidence assembly functions often achieved with LangChain."},
    {"segment_id": "S004", "section": "skills",
     "text": "Skills: Python, FastAPI, containerization, SQL."},
    {"segment_id": "S005", "section": "experience",
     "text": "Exposed inference endpoints with FastAPI, containerized releases, and maintained observability."},
    {"segment_id": "S006", "section": "projects",
     "text": "Built weekly demand forecasts and evaluated prediction errors for sales planning."},
    {"segment_id": "S007", "section": "experience",
     "text": "Developed support dashboards, review checklists and automated document ingestion."},
    {"segment_id": "S008", "section": "education", "text": "Completed BS Computer Science in 2022."},
    {"segment_id": "S009", "section": "experience",
     "text": "Designed REST API validation and monitored Python application incidents."},
]


def _requirement(rid: str, name: str, priority: str = "required") -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id=rid, name=name, priority=priority, jd_evidence=name,
        constraint=RequirementConstraint(kind="skill", origin="source_rules", requires_review=False),
    )


def _assessment(rid: str, status: str, cited: str | None = None) -> RequirementAssessment:
    source = next((s for s in LEDGER if s["segment_id"] == cited), None)
    return RequirementAssessment(
        requirement_id=rid, status=status, reason=f"Initial reviewer assessed {rid}.",
        evidence_segments=[EvidenceCitation(segment_id=cited, section=source["section"],
                                            text=source["text"])] if source else [],
        evidence_ids=[cited] if cited else [],
    )


def _report(*, errors=None) -> RankingReport:
    return RankingReport(
        job_description_source="Fictional test JD", jd_validation_mode="test",
        yake_candidates=[],
        requirements=[
            _requirement("R009", "LangChain"),
            _requirement("R014", "Time-series forecasting", "preferred"),
            _requirement("R016", "Node.js", "preferred"),
        ],
        candidates=[CandidateResult(
            candidate_name="Fictional applicant", rank=1, primary_score=33.3,
            evaluation_mode="llm_assessed", errors=errors or [], assessments=[
                _assessment("R009", "not_matched", "S001"),
                _assessment("R014", "matched", "S006"),
                _assessment("R016", "not_matched"),
            ],
        )],
    )


class NegativeFocused:
    def __init__(self):
        self.ids = []

    def invoke_structured(self, **kwargs):
        prompt = kwargs["user_prompt"]
        if '"id": "R009"' in prompt:
            self.ids.append("R009")
            return FocusedJudgment(
                result="not_evidenced",
                explanation="Applicant denies direct LangChain use. The model overlooked comparable work.",
                supporting_sources=[{"segment_id": "S001", "why": "Denied direct named-framework use."}],
            )
        if '"id": "R016"' in prompt:
            self.ids.append("R016")
            return FocusedJudgment(
                result="not_evidenced", explanation="Only Python/FastAPI projects were documented, not Node.js.",
                supporting_sources=[{"segment_id": f"S{x:03}", "why": "Checked this original CV segment."}
                                    for x in range(1, 10)],
            )
        raise AssertionError("Unexpected LLM call")


def test_explicit_work_bridge_recovers_transfer_without_direct_credit():
    model = NegativeFocused()
    final = reconcile_candidate(_report(), 0, LEDGER, llm=model)
    rows = {r["ID"]: r for r in final["Criteria"]}
    lang = rows["R009"]
    assert lang["Result"] == "Transferable"
    assert lang["Review recommended"] is True
    assert "Direct use of LangChain is not established" in lang["Why"]
    assert "S002" in [e["Segment"] for e in lang["Checkpoints"]]
    assert "S003" in [e["Segment"] for e in lang["Checkpoints"]]
    assert final["Required matched"] == 0  # transfer is NOT a required skill point
    assert final["Transferable"] == 1
    assert rows["R014"]["Result"] == "Found"  # explicitly preserve time-series decision
    assert model.ids == ["R009", "R016"]


def test_node_search_is_shown_in_four_representative_checkpoints_not_nine():
    final = reconcile_candidate(_report(), 0, LEDGER, llm=NegativeFocused())
    node = next(r for r in final["Criteria"] if r["ID"] == "R016")
    assert node["Result"] == "Not Found"
    assert len(node["Checkpoints"]) == 9  # complete audit preserved for JSON export
    assert node["Total checkpoints considered"] == 9
    shown = node["Display checkpoints"]
    assert len(shown) == 4
    assert any(item["Section"] == "skills" for item in shown)
    assert any(item["Section"] == "experience" for item in shown)
    assert any(item["Section"] == "projects" for item in shown)


def test_simple_denial_plus_unrelated_performance_is_not_transferable():
    entries = [
        {"segment_id": "S001", "section": "summary", "text": "Never used Node.js professionally."},
        {"segment_id": "S002", "section": "experience", "text": "Built graphic design posters and organized local exhibitions."},
    ]
    report = RankingReport(
        job_description_source="test", jd_validation_mode="test", yake_candidates=[],
        requirements=[_requirement("R016", "Node.js")],
        candidates=[CandidateResult(candidate_name="Unrelated applicant", rank=1,
                primary_score=0, evaluation_mode="llm_assessed",
            assessments=[_assessment("R016", "not_matched")])],
    )

    class NotEvidenced:
        def invoke_structured(self, **_):
            return FocusedJudgment(result="not_evidenced",
                                   explanation="There is no Node.js skill claim or comparable performed work.")

    final = reconcile_candidate(report, 0, entries, llm=NotEvidenced())
    assert final["Criteria"][0]["Result"] == "Not Found"
    assert final["Transferable"] == 0


def test_incomplete_semantic_run_and_initial_citation_notices_are_visible():
    final = reconcile_candidate(
        _report(errors=["R009: preliminary citation missing"]), 0, LEDGER,
        semantic={"complete": False}, llm=NegativeFocused(),
    )
    assert final["Provisional"] is True
    assert any("incomplete" in msg for msg in final["Notices"])
    assert any("earlier pass" in msg for msg in final["Notices"])
    assert sum(row["Review recommended"] for row in final["Criteria"]) >= 1


def test_ui_keeps_full_audit_export_and_caps_nonmatches_at_render():
    source = (Path(__file__).resolve().parents[1] / "cv_ranker/ui/dashboard.py").read_text(encoding="utf-8")
    assert 'item.get("Display checkpoints", item["Checkpoints"])' in source
    assert '"cv_final_evidence.json"' in source
    # V4.8 has one main evidence pass; the V4.7-specific label was retired.
    assert 'Assessment and validation notices' in source
    assert 'if final.get("Provisional")' in source

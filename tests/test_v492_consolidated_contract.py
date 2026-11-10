"""V4.9.2 evidence semantics, cross-domain source and UI invariants.

All examples are independent generic claims; no test CV or job vocabulary is
encoded in production behavior. Live provider accuracy is evaluated separately.
"""
import json

import pytest
import numpy as np

from cv_ranker.assessor import _positive_literal_segment_is_capability_evidence, _validate_rows
from cv_ranker.config import Settings
from cv_ranker.experience_validation import _tone
from cv_ranker.llm import LLMError, OpenRouterStructuredLLM
from cv_ranker.qualification_validation import _state, check_qualification
from cv_ranker.schemas import (
    CandidateResult, EvidenceCitation, LLMAssessmentItem,
    LLMCandidateAssessmentResponse, RankingReport, RequirementAssessment,
    RequirementConstraint, ValidatedRequirement,
)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.ui_support import final_leaderboard_rows
from cv_ranker.unified import UnifiedEvidenceEngine, _independently_adjudicate


def req(name, kind="skill", rid="R001", **properties):
    return ValidatedRequirement(
        requirement_id=rid, name=name, jd_evidence=name, priority="required",
        constraint=RequirementConstraint(kind=kind, origin="source_rules", **properties),
    )


class IndependentProvider:
    def __init__(self, decision="found", relation="entailed", quote=None):
        self.decision, self.relation, self.quote = decision, relation, quote
        self.calls = 0

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        assert "second, independent" in system_prompt
        assert "return an assessments array" not in system_prompt
        data = json.loads(user_prompt)
        evidence = data["sources"][0]
        return schema.model_validate({r["id"]: {
            "decision": self.decision,
            "relation": self.relation,
            "evidence_ids": [evidence["id"]] if self.decision != "not_found" else [],
            "proof_excerpt": (self.quote if self.quote is not None else evidence["text"])
                             if self.decision != "not_found" else None,
            "reason": "The candidate describes a completed, directly entailing task.",
        } for r in data["requirements"]})


@pytest.mark.parametrize("title", ["Deep Learning", "deep learning", "DEEP LEARNING"])
def test_independently_validated_entailment_is_case_invariant(title):
    requirement = req(title)
    source = ResumeSegment("S001", "experience", "Trained a PyTorch text classifier for live inference.")
    prompt = json.dumps({"requirements": [{"id": "R001", "name": title}],
                         "sources": [{"id": "S001", "text": source.text}]})
    model = IndependentProvider()
    response, proposals, rejected = _independently_adjudicate(
        model, [requirement], prompt, {"S001"}, {"S001": source})
    assert not rejected
    checked, invalid, warnings, _ = _validate_rows(
        response=response, requirements=[requirement], resume_text=source.text,
        segments=[source], semantic_grounded=True)
    assert not invalid, warnings
    assert checked["R001"].status == "matched"
    assert proposals["R001"].decision == "found"
    assert model.calls == 1


@pytest.mark.parametrize("quote", ["Invented activity", "TRAINED A DIFFERENT MODEL"])
def test_independent_semantic_decision_cannot_invent_its_cited_claim(quote):
    requirement = req("Quality management")
    source = ResumeSegment("S001", "experience", "Implemented inspections on the production line.")
    prompt = json.dumps({"requirements": [{"id": "R001", "name": requirement.name}],
                         "sources": [{"id": "S001", "text": source.text}]})
    response, proposals, rejected = _independently_adjudicate(
        IndependentProvider(quote=quote), [requirement], prompt,
        {"S001"}, {"S001": source})
    assert rejected == {"R001"} and not response.assessments and not proposals


@pytest.mark.parametrize("line", [
    "4 years of professional warehouse work; no relocation required.",
    "6 years of clinical practice, without weekend shifts.",
    "3 years of software delivery but not cloud deployment.",
])
def test_unrelated_negative_clause_does_not_negate_completed_tenure(line):
    assert _tone(line, None) == "positive"


@pytest.mark.parametrize("line", [
    "No formal logistics degree.",
    "No nursing license.",
    "Never obtained a safety certification.",
])
def test_explicit_credential_denials_remain_denied(line):
    assert _state(line) == "denied"


@pytest.mark.parametrize("line", [
    "Bachelor of Science in Computer Science, completed, no restrictions.",
    "Active professional license, never expired.",
    "Valid certification with no conditions.",
])
def test_unrelated_negative_words_do_not_cancel_credentials(line):
    assert _state(line) == "claimed"


@pytest.mark.parametrize("name,kind", [
    ("Manage supplier invoices", "responsibility"),
    ("Deliver monthly reports", "responsibility"),
    ("Five years of professional practice", "experience"),
])
def test_skill_list_is_not_automatic_proof_of_performed_duties(name, kind):
    requirement = req(name, kind=kind)
    source = ResumeSegment("S001", "skills", name)
    assert not _positive_literal_segment_is_capability_evidence(requirement, source)


@pytest.mark.parametrize("source", [
    "Education:\nBachelor of Science in Computer Science, completed 2024.",
    "Education:\nBachelor of Science in\nComputer Science, completed 2024.",
])
def test_degree_field_survives_a_physical_line_wrap(source):
    requirement = req("Bachelor of Science in Computer Science", kind="education",
                      degree_level="bachelor", field_of_study="Computer Science")
    checked = check_qualification(requirement, source, segment_resume(source))
    assert checked.outcome == "satisfied"


def test_failed_rank_shows_verified_peer_rows_with_no_rank_or_percent():
    r1, r2 = req("Quality assurance", rid="R001"), req("Warehouse maintenance", rid="R002")
    source = ResumeSegment("S001", "skills", "Quality assurance")
    found = RequirementAssessment(
        requirement_id="R001", status="matched", unified_status="Found",
        evidence_ids=["S001"], evidence=source.text,
        evidence_segments=[EvidenceCitation(segment_id="S001", section="skills", text=source.text)],
    )
    unavailable = RequirementAssessment(requirement_id="R002", status="uncertain",
                                        unified_status="Unverified", assessment_state="unverified")
    scored = score_candidate(candidate_name="Candidate X", requirements=[r1, r2],
                             assessments=[found, unavailable], evaluation_mode="llm_assessed", errors=[])
    assert scored.primary_score is None and scored.matched_required == 1
    report = RankingReport(job_description_source="jd.txt", jd_validation_mode="llm_validated",
                           yake_candidates=[], requirements=[r1, r2], candidates=[scored])
    detailed = reconcile_unified_candidate(report, 0, [{"segment_id": "S001",
                                                     "section": "skills", "text": source.text}])
    assert detailed["Required matched"] == 1 and detailed["Unverified"] == 1
    assert [r["Result"] for r in detailed["Criteria"]] == ["Found", "Unverified"]
    lead = final_leaderboard_rows(report, {"0": detailed})[0]
    assert lead["Rank"] == "-" and lead["Score"] is None
    assert "1/2" in lead["Required"] and "partial" in lead["Required"]


def test_cloud_request_budget_is_hard_capped_before_sending_any_more_data():
    from unittest.mock import patch
    model = OpenRouterStructuredLLM(Settings(
        llm_provider="openrouter", openrouter_api_key="synthetic-key-only",
        openrouter_max_requests_per_run=1, openrouter_request_interval_seconds=0,
    ))
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *unused):
            return False
        def read(self):
            return b'{"choices":[],"usage":{}}'
    with patch("cv_ranker.llm.urlopen", return_value=FakeResponse()) as post:
        model._post_chat({"messages": []})
        with pytest.raises(LLMError, match="budget reached"):
            model._post_chat({"messages": []})
        assert post.call_count == 1
        assert model.http_attempts == 1


class UniformEncoder:
    fingerprint = "cross-domain-contract-local-encoder"
    def embed_documents(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)
    def embed_queries(self, texts):
        return np.ones((len(texts), 4), dtype=np.float32)


class FinalOnlySemanticVerifier:
    disabled_reason = None
    def __init__(self, confirmed=True):
        self.settings = Settings(llm_provider="ollama")
        self.confirmed = confirmed
        self.calls = 0
        self.adjudications = 0

    def prompt_fits(self, *_):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        data = json.loads(user_prompt)
        sources = data["sources"]
        final = "IndependentSemantic" in schema.__name__
        self.adjudications += int(final)
        returned = {}
        for requirement in data["requirements"]:
            rid = requirement["id"]
            if final:
                status = "found" if self.confirmed else "not_found"
                returned[rid] = {
                    "decision": status,
                    "relation": "entailed" if self.confirmed else "absent",
                    "evidence_ids": [sources[0]["id"]] if self.confirmed else [],
                    "proof_excerpt": sources[0]["text"] if self.confirmed else None,
                    "reason": "Completed work entails the functional request." if self.confirmed
                              else "The cited report does not establish the requested output.",
                }
            else:
                # A deliberately invalid first-pass implication; the ordinary
                # grouped correction may repeat it, but never gives credit.
                returned[rid] = {
                    "decision": "found", "evidence_ids": [sources[0]["id"]],
                    "matched_term": None,
                    "reason": "Provisional source-based semantic judgment.",
                }
        return schema.model_validate(returned)


@pytest.mark.parametrize("accepted", [True, False])
def test_independent_grouped_adjudication_changes_unverified_into_a_real_decision(tmp_path, accepted):
    name = "Applied Anomaly Recognition"
    source = ResumeSegment("S001", "projects", "Built a statistical outlier recognition service.")
    requirement = req(name)
    model = FinalOnlySemanticVerifier(confirmed=accepted)
    with UnifiedEvidenceEngine(model.settings, model, encoder=UniformEncoder(),
                               cache_path=tmp_path / "evidence.db") as engine:
        rows, metrics = engine.assess([requirement], [source], source.text,
                                      candidate_id="generic-validating-candidate")
    assert model.calls == 3  # one grouped assessment, one correction, one final
    assert model.adjudications == 1 and metrics.final_verification_calls == 1
    assert metrics.unresolved_criteria == 0
    assert rows[0].unified_status == ("Found" if accepted else "Not Found")
    if accepted:
        assert rows[0].review_recommended  # semantic implication remains auditable

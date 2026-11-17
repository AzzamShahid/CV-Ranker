"""Scripted-provider full CVRanker(unified=True) source/score/resume checks.

This is an execution-path regression, not independent live LLM accuracy.
"""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from cv_ranker.config import Settings
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.pipeline import CVRanker
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.resume import candidate_resume_keys
from cv_ranker.schemas import JDReviewDraft, ValidatedRequirement
from cv_ranker.unified import UnifiedItem, UnifiedResponse
from cv_ranker.weighted_scoring import ScoreWeights
from evaluation.evaluate_supervisor import SyntheticEncoder


JD = "Interpretation of woven fabric construction, including weave pattern, ends per inch (EPI), and picks per inch (PPI)."
CV = "Experience:\nCheck weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets."


class SourceProvider:
    disabled_reason = None
    http_attempts = 0
    http_429_count = 0
    token_usage = {}

    def __init__(self, settings, *, invalid_syntax_review=False):
        self.settings = settings
        self.calls = 0
        self.invalid_syntax_review = invalid_syntax_review
    def prompt_fits(self, sys, usr):
        return True
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        pkt = json.loads(user_prompt)
        sources = pkt.get("sources", [])
        sid = next((s["id"] for s in sources if "fabric style sheets" in s["text"]),
                   sources[0]["id"] if sources else "S001")
        if schema.__name__ == "ConditionReviewResponse":
            if self.invalid_syntax_review:
                # No substantive conditions were reviewed: fail closed.
                return schema.model_validate({"assessments":[{"requirement_id":"R001",
                    "decision":"found", "facets": [], "source_ids":[sid],
                    "missing_parts": [], "reason":"No real requirement facets were assessed."}]})
            return schema.model_validate({"assessments":[{"requirement_id":"R001",
                 "decision":"found", "facets":[{
                     "jd_exact_span":span,"relation":"satisfied","source_ids":[sid],
                     "explanation":"Cited completed construction checks in this candidate source."}
                     for span in ["Interpretation of woven fabric construction",
                                  "weave pattern", "ends per inch (EPI)", "picks per inch (PPI)" ]],
                  "source_ids":[sid],"missing_parts":[],
                  "reason":"Each JD construction parameter is checked in the original work source."}]})
        if schema.__name__ == "IndependentSemanticDecisionByID":
            return schema.model_validate({"R001":{
                "decision":"found", "relation":"entailed", "evidence_ids":[sid],
                "proof_excerpt":None, "reason":"The source describes completed fabric construction checks."}})
        return UnifiedResponse(assessments=[UnifiedItem(requirement_id="R001",
            decision="found",relation="direct",evidence_ids=[sid],
            reason="Completed weaving construction checks for fabric style settings.")])


def run(tmp_path, provider, *, report=None, cached=None):
    jd_file = tmp_path/"jd.txt"
    cv_file = tmp_path/"cv.txt"
    jd_file.write_text(JD, encoding="utf-8")
    cv_file.write_text(CV, encoding="utf-8")
    req = ValidatedRequirement(requirement_id="R001",name=JD,jd_evidence=JD,priority="required")
    req.constraint=classify_requirement(req,JD)
    draft=JDReviewDraft(jd_sha256=jd_source_sha256(JD),yake_candidates=[],requirements=[req],
                        jd_validation_mode="manual",approved=True)
    with patch("cv_ranker.pipeline.StructuredLLM", return_value=provider):
        engine=CVRanker(settings=provider.settings, use_llm=True, unified=True,
                        embedding_encoder=SyntheticEncoder(),
                        embedding_cache_path=tmp_path/"embedding.sqlite")
        outcome=engine.run(jd_file,[cv_file], approved_jd=draft if report is None else None,
                           resume_report=report, resume_candidates=cached)
    return outcome, engine, cv_file


def test_compound_resolution_reaches_final_supervisor_export(tmp_path):
    model=SourceProvider(Settings(llm_provider="ollama"))
    result,engine,_=run(tmp_path,model)
    row=result.candidates[0].assessments[0]
    assert row.unified_status=="Found" and row.assessment_state=="verified"
    assert result.candidates[0].primary_score == 100
    assert model.calls == 3 and engine.unified_metrics[next(iter(engine.unified_metrics))]["compound_review_calls"] == 1
    with ZipFile(io.BytesIO(complete_results_zip(result, ScoreWeights(0,0,100)))) as archive:
        record=next(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
    assert record["Score status"]=="Verified"
    assert row.evidence_ids and row.decision_trace[-1].stage == "independent_compound_review"


def test_failed_compound_review_resume_does_not_repeat_identical_call(tmp_path):
    model=SourceProvider(Settings(llm_provider="ollama"),invalid_syntax_review=True)
    original,engine,cv_file=run(tmp_path,model)
    row=original.candidates[0].assessments[0]
    assert row.assessment_state=="unverified" and row.condition_review_attempt_signature
    assert original.candidates[0].primary_score is None
    attempts=model.calls
    keys=candidate_resume_keys([(cv_file.name,cv_file.read_bytes())])
    continued,engine2,_=run(tmp_path,model,report=original,cached={keys[0]:original.candidates[0]})
    assert model.calls==attempts
    assert continued.candidates[0].assessments[0].condition_review_attempt_signature == row.condition_review_attempt_signature
    assert continued.candidates[0].primary_score is None
    assert engine2.unified_metrics[next(iter(engine2.unified_metrics))]["reused_paused_semantic_review"]==1


def test_partial_fabric_defect_duty_stays_transferable_in_supervisor_and_zip(tmp_path):
    """A purposely mistaken primary Found cannot earn corrected-action points."""
    from cv_ranker.unified import UnifiedItem, UnifiedResponse
    from cv_ranker.eligibility import jd_source_sha256
    from cv_ranker.requirement_typing import classify_requirement
    jd = "Fabric defect identification and corrective action during weaving."
    cv = "Experience:\nIdentified fabric defects during weaving and wrote observations in the shift log."
    jd_file=tmp_path/"jd_partial.txt"
    cv_file=tmp_path/"cv_partial.txt"
    jd_file.write_text(jd)
    cv_file.write_text(cv)
    req=ValidatedRequirement(requirement_id="R001",name=jd,jd_evidence=jd,priority="required")
    req.constraint=classify_requirement(req,jd)
    draft=JDReviewDraft(jd_sha256=jd_source_sha256(jd),yake_candidates=[],
                        requirements=[req],jd_validation_mode="manual",approved=True)
    class PartialSourceProvider(SourceProvider):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.calls+=1
            packet=json.loads(user_prompt)
            sid=next((s["id"] for s in packet["sources"] if "fabric defects" in s["text"]),
                     packet["sources"][0]["id"])
            if schema.__name__=="ConditionReviewResponse":
                return schema.model_validate({"assessments":[{
                    "requirement_id":"R001","decision":"transferable",
                    "source_ids":[sid],
                    "facets":[{
                        "jd_exact_span":"Fabric defect identification",
                        "relation":"satisfied","source_ids":[sid],
                        "explanation":"Candidate documented identification of defects."},{
                        "jd_exact_span":"corrective action during weaving",
                        "relation":"missing","source_ids":[],
                        "explanation":"No corrective action described in submitted evidence."}],
                    "missing_parts":["corrective action during weaving"],
                    "reason":"Only identified defects; no corrective action is evidenced."}]})
            if schema.__name__=="IndependentSemanticDecisionByID":
                return schema.model_validate({"R001":{
                    "decision":"found","relation":"entailed","evidence_ids":[sid],
                    "proof_excerpt":None,
                    "reason":"Primary and review both initially proposed a complete result."}})
            return UnifiedResponse(assessments=[UnifiedItem(requirement_id="R001",
                    decision="found",relation="direct",evidence_ids=[sid],
                    reason="Primary model incorrectly inferred defect correction from observation.")])

    model=PartialSourceProvider(Settings(llm_provider="ollama"))
    with patch("cv_ranker.pipeline.StructuredLLM",return_value=model):
        ranker=CVRanker(settings=model.settings,use_llm=True,unified=True,
            embedding_encoder=SyntheticEncoder(),embedding_cache_path=tmp_path/"partial_vectors.sqlite")
        report=ranker.run(jd_file,[cv_file],approved_jd=draft)
    row=report.candidates[0].assessments[0]
    assert row.assessment_state=="verified" and row.unified_status=="Transferable"
    assert report.candidates[0].primary_score==0
    assert model.calls<=3
    assert row.decision_trace[-1].reason_code=="source_bound_condition_review"
    with ZipFile(io.BytesIO(complete_results_zip(report,ScoreWeights(0,0,100)))) as archive:
        export=next(csv.DictReader(io.StringIO(
            archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
    assert export["Score status"]=="Verified"
    assert export["Weighted score (%)"] in {"0.00","0.0","0"}


def test_independently_entailing_zero_word_overlap_completes_without_repeating_correction(tmp_path):
    """The lexical mismatch flag is a review trigger, never a final veto."""
    jd="Resolve customer complaints end-to-end."
    cv="Experience:\nHandled client grievances from intake through closure."
    a=tmp_path/"jd_paraphrase.txt"
    b=tmp_path/"cv_paraphrase.txt"
    a.write_text(jd)
    b.write_text(cv)
    req=ValidatedRequirement(requirement_id="R001",name=jd,jd_evidence=jd,priority="required")
    req.constraint=classify_requirement(req,jd)
    reviewed=JDReviewDraft(jd_sha256=jd_source_sha256(jd),yake_candidates=[],
                           requirements=[req],jd_validation_mode="manual",approved=True)
    class IndependentSynonymProvider(SourceProvider):
        def invoke_structured(self, *, system_prompt, user_prompt, schema):
            self.calls+=1
            packet=json.loads(user_prompt)
            sid=next(s["id"] for s in packet["sources"] if "client grievances" in s["text"])
            if schema.__name__ == "IndependentSemanticDecisionByID":
                return schema.model_validate({"R001":{
                    "decision":"found", "relation":"entailed", "evidence_ids":[sid],
                    "proof_excerpt":None,
                    "reason":"Resolved client grievances end to end through closure, the required complaint function."}})
            return UnifiedResponse(assessments=[UnifiedItem(requirement_id="R001",
                decision="found",relation="entailed",evidence_ids=[sid],
                reason="Candidate handled client grievances end to end from receipt to resolution.")])

    provider=IndependentSynonymProvider(Settings(llm_provider="ollama"))
    with patch("cv_ranker.pipeline.StructuredLLM",return_value=provider):
        ranker=CVRanker(settings=provider.settings,use_llm=True,unified=True,
                        embedding_encoder=SyntheticEncoder(),
                        embedding_cache_path=tmp_path/"paraphrase_embeds.sqlite")
        report=ranker.run(a,[b],approved_jd=reviewed)
    row=report.candidates[0].assessments[0]
    assert row.unified_status=="Found" and row.assessment_state=="verified"
    assert report.candidates[0].primary_score==100
    assert provider.calls==2  # primary + independent; no identical-source correction
    assert ranker.unified_metrics[str(b)]["correction_calls"]==0

"""Actual untrusted source packet and response-schema tests of syntax review.

Controlled scripted model replies are not a live model accuracy benchmark.
"""
from __future__ import annotations
import io
import json
from zipfile import ZipFile
import csv

from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.condition_review import review_compound_uncertainty
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import (EvidenceCitation, JDReviewDraft, RequirementAssessment,
                               ValidatedRequirement, RankingReport)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import segment_resume
from cv_ranker.weighted_scoring import ScoreWeights, weighted_leaderboard

R005 = "Interpretation of woven fabric construction, including weave pattern, ends per inch (EPI), and picks per inch (PPI)."
R008 = "Fabric defect identification and corrective action during weaving."


class ScriptedIndependentReview:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.packet = None
    def prompt_fits(self, system_prompt, user_prompt):
        return True
    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        self.packet = json.loads(user_prompt)
        return schema.model_validate(self.response)


def original_row(jd, cv, rid="R601"):
    r = ValidatedRequirement(requirement_id=rid,name=jd,jd_evidence=jd,priority="required")
    r.constraint = classify_requirement(r,jd)
    cv_text = "Experience\n" + cv
    evidence = next(s for s in segment_resume(cv_text) if cv in s.text)
    citation = EvidenceCitation(segment_id=evidence.segment_id, section=evidence.section,
                                text=evidence.text)
    prior = RequirementAssessment(requirement_id=rid, status="matched", unified_status="Found",
                                  evidence_ids=[evidence.segment_id],evidence_segments=[citation],
                                  reason="Unresolved semantic proposal from primary provider.")
    rows, _, _ = apply_compound_checks(requirements=[r], assessments=[prior], resume_text=cv_text)
    assert rows[0].assessment_state == "unverified"
    return r, cv_text, rows[0], evidence.segment_id


def make_reply(rid, decision, sid, spans, *, missing=None, relation=None):
    missing = missing or []
    return {"assessments":[{"requirement_id":rid,"decision":decision,
         "source_ids": [sid] if decision in {"found", "transferable"} else [],
         "facets":[{"jd_exact_span":s, "relation": (relation or
                      ("satisfied" if decision == "found" else "missing")),
                    "source_ids":[sid] if decision in {"found", "transferable"} else [],
                    "explanation":"Source reviewed for this employer-approved condition."}
                   for s in spans],
         "missing_parts":missing,"reason":"Reviewed original applicant sources and the complete JD obligation."}]}


def read_result(r, row):
    final = reconcile_final_assessments(requirements=[r],assessments=[row])[0]
    candidate = score_candidate(candidate_name="Fictional.txt",requirements=[r],
          assessments=[final],evaluation_mode="llm_assessed",errors=[])
    report = RankingReport(job_description_source="fictional_jd.txt",jd_validation_mode="manual",
           yake_candidates=[],requirements=[r], candidates=[candidate])
    w = ScoreWeights(0,0,100)
    leaderboard = weighted_leaderboard(report,w)
    archive = ZipFile(io.BytesIO(complete_results_zip(report,w)))
    csv_row = next(csv.DictReader(io.StringIO(archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))
    return final,candidate,leaderboard[0],csv_row


def test_r005_independently_reviewed_complete_construction_is_found_once():
    cv="Check weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets."
    r,cv_text,row,sid=original_row(R005,cv)
    spans=["Interpretation of woven fabric construction", "weave pattern",
           "ends per inch (EPI)","picks per inch (PPI)"]
    model=ScriptedIndependentReview(make_reply("R601","found",sid,spans))
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv_text,llm=model)
    final,candidate,leaderboard,record=read_result(r,reviewed[0])
    assert stats.attempted==stats.resolved==model.calls==1
    assert final.assessment_state=="verified" and final.unified_status=="Found"
    assert candidate.primary_score==100.0 and leaderboard["weighted_score"]==100
    assert record["Score status"]=="Verified"
    assert final.evidence_ids==[sid]
    assert final.decision_trace[-1].reason_code=="source_bound_condition_review"


def test_r008_only_defect_observation_can_be_transferable_not_full_found():
    cv="Recorded defect observations at shift handover."
    r,cv_text,row,sid=original_row(R008,cv)
    model=ScriptedIndependentReview(make_reply("R601","transferable",sid,
        ["Fabric defect identification","corrective action during weaving"],
        missing=["corrective action during weaving"],relation="satisfied"))
    model.response["assessments"][0]["facets"][1]["relation"] = "missing"
    model.response["assessments"][0]["facets"][1]["source_ids"] = []
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv_text,llm=model)
    final,candidate,leaderboard,record=read_result(r,reviewed[0])
    assert final.unified_status=="Transferable" and final.assessment_state=="verified"
    assert candidate.primary_score==0 and leaderboard["weighted_score"]==0
    assert record["Score status"]=="Verified"
    assert "corrective" in final.reason or model.response["assessments"][0]["missing_parts"]


def test_r008_complete_both_duties_may_be_found_with_independent_facet_proof():
    cv="Identified fabric defects on the loom and documented corrective adjustments during weaving."
    r,cv_text,row,sid=original_row(R008,cv)
    model=ScriptedIndependentReview(make_reply("R601","found",sid,
        ["Fabric defect identification","corrective action during weaving"]))
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv_text,llm=model)
    assert stats.resolved==1
    assert read_result(r,reviewed[0])[0].unified_status=="Found"


def test_catch_all_single_facet_cannot_override_mandatory_and():
    r,cv,row,sid=original_row(R008,"Recorded defect observations at shift handover.")
    model=ScriptedIndependentReview(make_reply("R601","found",sid,[R008]))
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=model)
    assert stats.resolved==0
    final,candidate,leaderboard,record=read_result(r,reviewed[0])
    assert final.unified_status is None
    assert final.current_decision.verdict is None
    assert final.current_decision.processing_state == "failed"
    assert final.current_decision.failure.code == "response_schema_invalid"
    assert candidate.primary_score is None and leaderboard["weighted_score"] is None


def test_wrong_source_ids_and_unquoted_jd_span_fail_closed():
    r,cv,row,sid=original_row(R008,"Recorded defect observations at shift handover.")
    for forged in [make_reply("R601","found","S999",r.constraint.options),
                   make_reply("R601","found",sid,["fabricated extra qualification",r.constraint.options[1]])]:
        m=ScriptedIndependentReview(forged)
        reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=m)
        assert stats.attempted==m.calls==2 and stats.resolved==0  # original + one bounded correction
        assert reviewed[0].assessment_state=="unverified"
        assert reviewed[0].unified_status is None
        assert reviewed[0].current_decision.verdict is None
        assert reviewed[0].current_decision.failure.code == "response_schema_invalid"


def test_missing_provider_and_context_budget_preserve_unverified_without_calls():
    r,cv,row,sid=original_row(R005,"Check weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets.")
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=None)
    assert stats.attempted==0 and reviewed[0].assessment_state=="unverified"
    m=ScriptedIndependentReview(make_reply("R601","found",sid,[R005]))
    m.prompt_fits=lambda *_:False
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=m)
    assert stats.attempted==m.calls==0 and reviewed[0].assessment_state=="unverified"


def test_review_already_verified_does_not_reinvoke_model():
    r,cv,row,sid=original_row(R008,"Identified fabric defects on loom and documented corrective adjustments during weaving.")
    m=ScriptedIndependentReview(make_reply("R601","found",sid,r.constraint.options))
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=m)
    reviewed2,stats2=review_compound_uncertainty(requirements=[r],assessments=reviewed,resume_text=cv,llm=m)
    assert stats2.attempted==0 and m.calls==1
    assert reviewed2[0].model_dump()==reviewed[0].model_dump()


def test_hr_can_freeze_exact_mandatory_fragments_and_reject_invented_ones():
    from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
    from cv_ranker.eligibility import jd_source_sha256
    from cv_ranker.schemas import JDReviewDraft
    jd=R008
    r=ValidatedRequirement(requirement_id="R601",name=jd,jd_evidence=jd,priority="required")
    r.constraint=classify_requirement(r,jd)
    draft=JDReviewDraft(jd_sha256=jd_source_sha256(jd),yake_candidates=[],
                        requirements=[r],jd_validation_mode="manual",approved=False)
    base=editable_jd_rows(draft)[0]
    base["Mandatory JD parts"]="Fabric defect identification | corrective action during weaving"
    approved=approve_jd_rows(draft=draft,rows=[base],jd_text=jd,max_requirements=100)
    assert approved.requirements[0].constraint.approved_mandatory_parts == r.constraint.options
    assert not approved.requirements[0].constraint.requires_review
    restored=JDReviewDraft.model_validate(approved.model_dump())
    assert restored.requirements[0].constraint.approved_mandatory_parts == r.constraint.options
    base["Mandatory JD parts"]="Fabric defect identification | perform unrelated invented certification"
    import pytest
    with pytest.raises(ValueError,match="not quoted in the frozen JD"):
        approve_jd_rows(draft=draft,rows=[base],jd_text=jd,max_requirements=100)


def test_approved_condition_group_must_be_supported_before_found():
    r,cv,row,sid=original_row(R005,
        "Check weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets.")
    r.constraint = r.constraint.model_copy(update={
        "approved_mandatory_parts":["weave pattern","ends per inch (EPI)","picks per inch (PPI)"],
        "requires_review":False})
    model=ScriptedIndependentReview(make_reply("R601","found",sid,
        ["Interpretation of woven fabric construction", "weave pattern"]))
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=model)
    assert stats.resolved==0 and reviewed[0].unified_status is None
    assert reviewed[0].current_decision.verdict is None
    assert reviewed[0].current_decision.failure.code == "response_schema_invalid"
    model2=ScriptedIndependentReview(make_reply("R601","found",sid,
        ["Interpretation of woven fabric construction", "weave pattern",
         "ends per inch (EPI)","picks per inch (PPI)"]))
    reviewed2,stats2=review_compound_uncertainty(requirements=[r],assessments=[row],resume_text=cv,llm=model2)
    assert stats2.resolved==1 and reviewed2[0].unified_status=="Found"


def test_reviewed_alternative_groups_are_source_grounded():
    from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
    from cv_ranker.schemas import JDReviewDraft
    from cv_ranker.eligibility import jd_source_sha256
    jd="Use ERP, MES or SAP for reporting."
    r=ValidatedRequirement(requirement_id="R001",name=jd,jd_evidence=jd,priority="required")
    r.constraint=classify_requirement(r,jd)
    draft=JDReviewDraft(jd_sha256=jd_source_sha256(jd),yake_candidates=[],
                        requirements=[r],jd_validation_mode="manual")
    fields=editable_jd_rows(draft)[0]
    fields["Alternative groups JSON"]='[["ERP", "MES", "SAP"]]'
    approved=approve_jd_rows(draft=draft,rows=[fields],jd_text=jd,max_requirements=100)
    assert approved.requirements[0].constraint.approved_alternative_groups == [["ERP","MES","SAP"]]
    fields["Alternative groups JSON"]='[["ERP", "unmentioned model"]]'
    import pytest
    with pytest.raises(ValueError, match="not quoted in the frozen JD"):
        approve_jd_rows(draft=draft,rows=[fields],jd_text=jd,max_requirements=100)


def test_reviewed_jd_parts_reject_duplicate_approvals(tmp_path):
    """Pydantic must validate fresh mapping, not silently trust model_copy instances."""
    from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
    from cv_ranker.schemas import JDReviewDraft, ValidatedRequirement
    from cv_ranker.eligibility import jd_source_sha256
    import pytest
    jd = "Fabric defect identification and corrective action during weaving."
    req = ValidatedRequirement(requirement_id="R001", name=jd, priority="required", jd_evidence=jd)
    req.constraint = classify_requirement(req, jd)
    draft = JDReviewDraft(jd_sha256=jd_source_sha256(jd), yake_candidates=[], requirements=[req],
                          jd_validation_mode="manual", approved=False)
    rows = editable_jd_rows(draft)
    rows[0]["Mandatory JD parts"] = "Fabric defect identification | Fabric defect identification"
    with pytest.raises(ValueError):
        approve_jd_rows(draft=draft, rows=rows, jd_text=jd, max_requirements=30)


def test_display_brand_configuration_cannot_change_assessment_identity():
    """Changing organization display label must not invalidate assessed sources."""
    import os
    from unittest.mock import patch
    from cv_ranker.resume import _ASSESSMENT_LOGIC_FILES
    from cv_ranker.build_info import ASSESSMENT_PROTOCOL_VERSION
    assert "ui/dashboard.py" not in _ASSESSMENT_LOGIC_FILES
    frozen_protocol = ASSESSMENT_PROTOCOL_VERSION
    with patch.dict(os.environ, {"CVR_ORGANIZATION_NAME": "Neutral Company"}):
        assert ASSESSMENT_PROTOCOL_VERSION == frozen_protocol
    with patch.dict(os.environ, {"CVR_ORGANIZATION_NAME": "<script>"}):
        from html import escape
        assert escape(os.environ["CVR_ORGANIZATION_NAME"]) == "&lt;script&gt;"

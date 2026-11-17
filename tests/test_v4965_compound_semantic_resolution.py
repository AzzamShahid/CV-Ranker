"""Prevent syntax uncertainty from becoming a verified candidate negative.

This uses synthetic JD and CV evidence and does not measure provider accuracy.
"""
from __future__ import annotations

import pytest

from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import segment_resume


EXAMPLES = [
    ("R005", "Interpretation of woven fabric construction, including weave pattern, ends per inch (EPI), and picks per inch (PPI).",
     "Check weave patterns, EPI, PPI, pick density, and selvage settings against fabric style sheets."),
    ("R008", "Fabric defect identification and corrective action during weaving.",
     "Recorded defect observations at shift handover."),
]


def make_work(rid, jd, cv, relation="Found"):
    req = ValidatedRequirement(requirement_id=rid, name=jd, jd_evidence=jd, priority="required")
    req.constraint = classify_requirement(req, jd)
    resume = "Experience\n" + cv
    seg = next(s for s in segment_resume(resume) if cv in s.text)
    citation = EvidenceCitation(segment_id=seg.segment_id, section=seg.section, text=seg.text)
    proposal = RequirementAssessment(requirement_id=rid, status="matched" if relation == "Found" else "not_matched",
                                     unified_status=relation, evidence_ids=[citation.segment_id],
                                     evidence_segments=[citation], evidence=seg.text,
                                     reason="The provider proposed this source as a complete requirement match.")
    return req, resume, proposal


@pytest.mark.parametrize("rid,jd,cv", EXAMPLES)
def test_parser_uncertainty_does_not_export_a_verified_negative(rid,jd,cv):
    req, resume, proposal = make_work(rid,jd,cv)
    checked, notices, _ = apply_compound_checks(requirements=[req], assessments=[proposal], resume_text=resume)
    assert checked[0].compound_check and checked[0].compound_check.outcome == "needs_review"
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status is None
    assert final.current_decision.processing_state == "pending"
    assert final.current_decision.verdict is None
    assert final.assessment_state == "unverified"
    assert final.review_recommended
    assert final.evidence_ids == proposal.evidence_ids
    scored = score_candidate(candidate_name="Synthetic.txt", requirements=[req], assessments=[final],
                             evaluation_mode="llm_assessed", errors=[])
    assert scored.primary_score is None
    assert final.decision_trace
    assert not any(t.reason_code == "direct_or_related_not_established" for t in final.decision_trace)


def test_explicit_unsupported_and_does_not_become_found():
    req, resume, proposal = make_work(*EXAMPLES[1])
    checked, _, _ = apply_compound_checks(requirements=[req], assessments=[proposal], resume_text=resume)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status != "Found"


def test_original_verified_negative_does_not_automatically_become_unverified():
    req, resume, proposed = make_work(*EXAMPLES[1])
    original = proposed.model_copy(update={"status":"not_matched", "unified_status":"Not Found",
                                         "reason":"Full original CV assessed; corrective work is not stated."})
    checked, _, _ = apply_compound_checks(requirements=[req], assessments=[original], resume_text=resume)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status == "Not Found"
    assert final.assessment_state == "verified"


def test_retained_source_backed_transferable_stays_zero_credit():
    req, resume, proposed = make_work(*EXAMPLES[1], relation="Transferable")
    checked, _, _ = apply_compound_checks(requirements=[req], assessments=[proposed], resume_text=resume)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.unified_status == "Transferable"
    score = score_candidate(candidate_name="Synthetic.txt", requirements=[req], assessments=[final],
                            evaluation_mode="llm_assessed", errors=[])
    assert score.primary_score == 0


def test_novel_paraphrase_can_pass_source_checks_after_independent_review_only():
    from cv_ranker.assessor import _validate_rows
    from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse
    from cv_ranker.segments import ResumeSegment
    from cv_ranker.requirement_typing import classify_requirement
    jd = "Resolve customer complaints end-to-end."
    r = ValidatedRequirement(requirement_id="R991", name=jd,jd_evidence=jd,priority="required")
    r.constraint = classify_requirement(r,jd)
    source = ResumeSegment("S401", "experience", "Handled client grievances from intake through closure.")
    proposal = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R991",status="matched",evidence_ids=["S401"],
        reason="Performed resolution work from first contact to closure.")])
    first, invalid, _, _ = _validate_rows(response=proposal, requirements=[r],
                                          resume_text=source.text, segments=[source], semantic_grounded=True)
    assert not first and "R991" in invalid  # primary cannot guess an alias safely
    second, invalid, notices, _ = _validate_rows(
        response=proposal,requirements=[r],resume_text=source.text,segments=[source],
        semantic_grounded=True,independently_reviewed_ids={"R991"})
    assert not invalid, notices
    assert second["R991"].status == "matched"


def test_independent_exemption_does_not_override_invalid_source_identity():
    from cv_ranker.assessor import _validate_rows
    from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse
    from cv_ranker.segments import ResumeSegment
    jd = "Resolve customer complaints end-to-end."
    r = ValidatedRequirement(requirement_id="R991",name=jd,jd_evidence=jd,priority="required")
    r.constraint = classify_requirement(r,jd)
    cv = ResumeSegment("S401","experience","Handled client grievances from intake through closure.")
    bad = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R991",status="matched",evidence_ids=["S999"],
        reason="Invented source ID but plausible looking description.")])
    accepted, rejected, _, _ = _validate_rows(response=bad,requirements=[r],
        resume_text=cv.text,segments=[cv],semantic_grounded=True,
        independently_reviewed_ids={"R991"})
    assert not accepted and "R991" in rejected

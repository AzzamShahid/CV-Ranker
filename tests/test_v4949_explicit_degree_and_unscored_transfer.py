"""Domain-neutral regression for explicit degree OR fields and related tenure.

All names and companies below are fictional. No matching skill dictionary or
requirement-ID exception is permitted in production validation.
"""

from cv_ranker.experience_validation import apply_experience_checks
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.qualification_validation import (apply_qualification_checks,
                                               check_qualification)
from cv_ranker.requirement_typing import add_requirement_types
from cv_ranker.schemas import EvidenceCitation, RequirementAssessment, ValidatedRequirement
from cv_ranker.segments import segment_resume


DEGREE = ("Completed Bachelor's degree in Textile Engineering or Textile "
          "Technology, or a three-year DAE diploma in Textile Technology.")
TENURE = "Minimum 3 years of full-time professional experience in textile weaving production."


def _req(text, rid="R001"):
    return add_requirement_types([ValidatedRequirement(
        requirement_id=rid, name=text, jd_evidence=text, priority="required")], text)[0]


def _assessed(req, text, fragments, *, status="matched", unified="Found", reason=""):
    sources = segment_resume(text)
    cited = [next(s for s in sources if fragment in s.text) for fragment in fragments]
    return RequirementAssessment(requirement_id=req.requirement_id, status=status,
                                 unified_status=unified, reason=reason,
                                 evidence_ids=[s.segment_id for s in cited],
                                 evidence_segments=[EvidenceCitation(segment_id=s.segment_id,
                                                                    section=s.section,
                                                                    text=s.text) for s in cited])


def test_bachelor_second_field_is_a_direct_jd_alternative():
    req = _req(DEGREE, "R002")
    text = "Education\nBS Textile Technology, East Bay Textile University (fictional), 2021"
    assert check_qualification(req, text).outcome == "satisfied"
    for old in ("matched", "not_matched"):
        row = _assessed(req, text, ["BS Textile Technology"], status=old,
                        unified="Found" if old == "matched" else "Not Found",
                        reason="Could not verify the first named degree.")
        after, _, _ = apply_qualification_checks(
            requirements=[req], assessments=[row], resume_text=text)
        final = reconcile_final_assessments(requirements=[req], assessments=after)[0]
        assert final.status == "matched"
        assert final.unified_status == "Found"
        assert "Textile Technology" in final.evidence_segments[0].text
        if old == "not_matched":
            assert "explicitly accepted" in final.reason


def test_other_major_is_not_invented_as_an_or_alternative():
    req = _req(DEGREE)
    text = "Education\nBS Industrial Engineering, Example University, 2020"
    row = _assessed(req, text, ["BS Industrial Engineering"])
    checked, _, _ = apply_qualification_checks(
        requirements=[req], assessments=[row], resume_text=text)
    assert checked[0].status != "matched"


def test_and_credentials_are_not_satisfied_by_only_one_field():
    jd = "Completed Bachelor's degree in Textile Engineering and a diploma in Textile Technology."
    req = _req(jd)
    text = "Education\nBS Textile Engineering, Sample University, 2021"
    assert check_qualification(req, text).outcome != "satisfied"


def test_unscored_neighboring_work_is_transferable_but_not_weaving_tenure():
    req = _req(TENURE)
    cv = """Professional summary
Textile production supervisor with 4 years 6 months of full-time experience in circular knitting, machine efficiency reporting, fabric defect prevention, and shift coordination.
Professional experience
Circular Knitting Supervisor | Harbour Knit Mills (fictional) Apr 2022 - Present
- Manage 35 circular knitting machines, allocate operators, and achieve daily fabric output targets.
- Participated in a three-week observation placement in an air-jet weaving hall; did not independently operate or supervise weaving looms.
"""
    row = _assessed(req, cv, ["Textile production supervisor", "Circular Knitting Supervisor",
                              "Manage 35", "three-week observation"],
                    status="not_matched", unified="Not Found", reason=(
                        "The candidate has experience in circular knitting production, "
                        "not textile weaving production as required."))
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.status != "matched"
    assert final.unified_status == "Transferable"
    assert final.review_recommended
    assert "not Found or numeric credit" in final.reason


def test_unrelated_career_is_not_transferable_on_generic_work_verb_alone():
    req = _req(TENURE)
    cv = """Professional summary
Sales operations manager with 4 years 6 months of full-time experience selling consumer products.
Professional experience
Sales Supervisor | Harbour Wholesale (fictional) Apr 2022 - Present
- Manage 35 sales representatives, allocate shifts, and achieve revenue targets.
"""
    row = _assessed(req, cv, ["Sales operations", "Sales Supervisor", "Manage 35"],
                    status="not_matched", unified="Not Found", reason=(
                        "The candidate has experience in sales, not textile weaving production."))
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=checked)[0]
    assert final.status != "matched"
    assert final.unified_status == "Not Found"

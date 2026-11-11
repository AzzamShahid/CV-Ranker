"""Deadline regressions: source-valid duties must not cause paid retry loops.

The same rules apply to any profession. The weaving text is one synthetic
cross-domain fixture, never a runtime skill list or requirement-ID exception.
"""

from cv_ranker.assessor import _validate_rows
from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.experience_validation import apply_experience_checks, check_experience
from cv_ranker.qualification_validation import check_qualification, apply_qualification_checks
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.requirement_typing import add_requirement_types
from cv_ranker.scoring import score_candidate
from cv_ranker.schemas import (EvidenceCitation, LLMAssessmentItem,
                               LLMCandidateAssessmentResponse,
                               RequirementAssessment, ValidatedRequirement)
from cv_ranker.segments import segment_resume


JD_ITEMS = [
    "Minimum 3 years of full-time professional experience in textile weaving production.",
    "Completed Bachelor's degree in Textile Engineering or Textile Technology, or a three-year DAE diploma in Textile Technology.",
    "Operation or supervision of air-jet or rapier weaving looms",
    "Weaving production planning and achievement of shift output targets.",
    "Interpretation of woven fabric construction, including weave pattern, ends per inch (EPI), and picks per inch (PPI).",
    "Coordination of warping and sizing processes with weaving production.",
    "Troubleshooting warp or weft breaks and recurring loom stoppages.",
    "Fabric defect identification and corrective action during weaving.",
    "Monitoring and reporting loom efficiency, woven output, and fabric rejection KPIs.",
    "Coordination of preventive loom maintenance and safe operating practices.",
    "Shift handover documentation and coordination with operators, maintenance, and quality teams.",
    "Hands-on exposure to both air-jet and rapier weaving technologies.",
    "Experience with electronic dobby or jacquard weaving setups.",
    "Use of CAD-based fabric design or weave-planning software.",
    "Use of ERP or manufacturing execution systems (MES) for weaving production reporting.",
    "Lean manufacturing, 5S, or root-cause analysis improvement projects.",
    "Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.",
    "Experience reducing compressed-air or energy consumption in weaving operations.",
]

CV = """Professional summary
Weaving professional with 7 years 4 months of full-time experience supervising air-jet and rapier loom production and textile teams.
Professional experience
Production Supervisor | Sample Company | Jun 2019 - Present
- Supervise 76 air-jet and 24 rapier looms across shifts; set daily weaving plans and close output gaps.
- Read weave patterns, EPI, PPI, and construction sheets to confirm style changeovers.
- Coordinate beam availability, warping quality, sizing recipes, and tension issues with preparation.
- Investigate warp breaks, weft breaks, stop marks and loom stoppages; document root causes and fabric defect corrections.
- Report loom efficiency, metres woven, rejection rate, and downtime in ERP/MES dashboards.
- Plan preventive maintenance with mechanical teams and run safe-start checks before restart.
- Prepare shift handovers with operators, quality inspectors, and maintenance staff.
- Operate electronic dobby and jacquard jobs; use fabric CAD software to review weave plans.
- Led 5S and compressed-air leakage audits and verified lower loom air consumption.
- Worked with cotton and polyester-blend yarn counts and monitored incoming yarn quality.
Education
BS Textile Engineering, Example Institute, 2018
Technical and operational skills
Air-jet looms; rapier looms; warping; sizing; EPI/PPI
Training and certifications
Industrial machine safety workshop.
"""


def _typed():
    jd = "\n".join(JD_ITEMS)
    reqs = [ValidatedRequirement(requirement_id=f"R{n:03d}", name=name,
                                 jd_evidence=name,
                                 priority="required" if n <= 11 else "preferred")
            for n, name in enumerate(JD_ITEMS, 1)]
    return add_requirement_types(reqs, jd)


def _row(req, source):
    citation = EvidenceCitation(segment_id=source.segment_id,
                                section=source.section, text=source.text)
    return RequirementAssessment(requirement_id=req.requirement_id,
                                 status="matched", unified_status="Found",
                                 evidence=source.text, evidence_ids=[source.segment_id],
                                 evidence_segments=[citation],
                                 reason="Model confirms that the cited completed duty supports the stated JD scope.")


def test_realistic_present_tense_duties_are_source_valid_not_retried():
    reqs = _typed()
    sources = segment_resume(CV)
    pairs = {
        4: "set daily weaving plans", 5: "Read weave patterns",
        6: "Coordinate beam availability", 7: "Investigate warp breaks",
        8: "fabric defect corrections", 9: "Report loom efficiency",
        11: "Prepare shift handovers", 13: "Operate electronic dobby",
        14: "fabric CAD software", 15: "ERP/MES dashboards",
    }
    selected = {f"R{n:03d}": next(s for s in sources if snippet in s.text)
                for n, snippet in pairs.items()}
    assessments = [LLMAssessmentItem(requirement_id=rid, status="matched",
                                     evidence_ids=[source.segment_id],
                                     reason="The candidate completed the explicitly stated activity.")
                   for rid, source in selected.items()]
    chosen_reqs = [r for r in reqs if r.requirement_id in selected]
    valid, invalid, notices, _ = _validate_rows(
        response=LLMCandidateAssessmentResponse(assessments=assessments),
        requirements=chosen_reqs, resume_text=CV, segments=sources,
        semantic_grounded=True)
    assert invalid == set(), notices
    assert set(valid) == set(selected)
    assert all(row.evidence_ids for row in valid.values())


def test_role_links_all_present_tense_duties_and_can_credit_cited_role():
    req = _typed()[0]
    sources = segment_resume(CV)
    check = check_experience(req, CV, sources)
    assert check.outcome == "role_semantic"
    assert len(check.role_tenure[0].duty_segment_ids) >= 9
    role_id = check.role_tenure[0].role_segment_id
    duty_id = next(s.segment_id for s in sources if "set daily weaving plans" in s.text)
    row = _row(req, next(s for s in sources if s.segment_id == duty_id))
    row = row.model_copy(update={"evidence_ids": [role_id, duty_id],
                                 "evidence_segments": [
                                     EvidenceCitation(segment_id=s.segment_id, section=s.section,
                                                      text=s.text)
                                     for s in sources if s.segment_id in {role_id, duty_id}]})
    result, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=CV)
    assert result[0].status == "matched"


def test_explicit_or_degree_can_match_direct_first_option_without_diploma_equivalence():
    req = _typed()[1]
    sources = segment_resume(CV)
    assert check_qualification(req, CV, sources).outcome == "satisfied"
    mandatory_both = req.model_copy(update={"jd_evidence":
        "Completed Bachelor's degree in Textile Engineering and a diploma in Textile Technology."})
    assert check_qualification(mandatory_both, CV, sources).outcome == "ambiguous"


def test_nonatomic_work_clause_preserves_only_positive_source_grounded_model_verdict():
    reqs = _typed()
    sources = segment_resume(CV)
    assert reqs[2].constraint.operator == "complex"
    assert reqs[15].constraint.operator == "any_of"
    assert reqs[15].constraint.options == [
        "Lean manufacturing", "5S", "root-cause analysis improvement projects"]
    for index, snippet in ((2, "Supervise 76"), (9, "Plan preventive maintenance"),
                           (11, "Supervise 76"), (16, "Worked with cotton"),
                           (17, "Led 5S")):
        req = reqs[index]
        row = _row(req, next(s for s in sources if snippet in s.text))
        checked, _, _ = apply_compound_checks(
            requirements=[req], assessments=[row], resume_text=CV)
        assert checked[0].status == "matched", (req.name, checked[0].compound_check)
        assert checked[0].review_recommended


def test_mixed_and_or_compound_and_bare_title_still_cannot_earn_credit():
    text = "Python and Django or Flask"
    req = ValidatedRequirement(requirement_id="R001", name=text, jd_evidence=text,
                               priority="required",
                               constraint=_typed()[2].constraint.model_copy(update={"operator": "complex"}))
    source = segment_resume("Professional experience\nSoftware Engineer | Company | 2021 - 2024")[0]
    row = _row(req, source)
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[row], resume_text=source.text)
    assert checked[0].status != "matched"


def test_live_regression_summary_role_and_duty_can_establish_experience_without_repeated_model_call():
    req = _typed()[0]
    sources = segment_resume(CV)
    summary = next(s for s in sources if s.section == "summary" and "7 years" in s.text)
    role = next(s for s in sources if s.section == "experience" and "2019" in s.text)
    row = _row(req, summary).model_copy(update={
        "evidence_ids": [summary.segment_id, role.segment_id],
        "evidence_segments": [EvidenceCitation(segment_id=s.segment_id,
                                               section=s.section, text=s.text)
                              for s in (summary, role)],
    })
    checked, warnings, changed = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=CV)
    result = checked[0]
    assert not changed and not warnings
    assert result.status == "matched"
    assert result.experience_check.outcome == "role_semantic"
    assert result.review_recommended
    assert {summary.segment_id, role.segment_id}.issubset(result.evidence_ids)
    # The validator attaches independently located work to the same dated role.
    assert any("Supervise 76" in c.text for c in result.evidence_segments)
    assert "CV-reported" in result.reason


def test_live_regression_ambiguous_compound_preserves_validated_work_and_citations():
    reqs = _typed()
    work = next(s for s in segment_resume(CV) if "Investigate warp breaks" in s.text)
    for req in (reqs[6], reqs[7]):
        row = _row(req, work)
        checked, warnings, changed = apply_compound_checks(
            requirements=[req], assessments=[row], resume_text=CV)
        assert not warnings and not changed
        assert checked[0].status == "matched", req.name
        assert checked[0].evidence_ids == [work.segment_id]
        assert checked[0].compound_check.outcome == "matched"
        assert checked[0].review_recommended


def test_summary_without_related_role_work_does_not_earn_automatic_tenure():
    req = _typed()[0]
    cv = """Professional summary
Weaving professional with 7 years of full-time experience supervising textile weaving production.
Professional experience
Sales Manager | Fictional Company | Jun 2019 - Present
- Managed customer sales calls and reported monthly revenue.
"""
    sources = segment_resume(cv)
    summary = next(s for s in sources if s.section == "summary")
    role = next(s for s in sources if "2019" in s.text)
    row = _row(req, summary).model_copy(update={
        "evidence_ids": [summary.segment_id, role.segment_id],
        "evidence_segments": [EvidenceCitation(segment_id=s.segment_id,
                                               section=s.section, text=s.text)
                              for s in (summary, role)],
    })
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"


def test_summary_in_an_unrelated_profession_does_not_borrow_role_dates():
    req = _typed()[0]
    cv = """Professional summary
Seven years of full-time experience supervising marketing content production.
Professional experience
Weaving Production Trainee | Fictional Company | Jun 2019 - Present
- Managed weaving shift schedules and checked output targets.
"""
    sources = segment_resume(cv)
    summary = next(s for s in sources if s.section == "summary")
    role = next(s for s in sources if "2019" in s.text)
    row = _row(req, summary).model_copy(update={
        "evidence_ids": [summary.segment_id, role.segment_id],
        "evidence_segments": [EvidenceCitation(segment_id=s.segment_id,
                                               section=s.section, text=s.text)
                              for s in (summary, role)],
    })
    checked, _, _ = apply_experience_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    assert checked[0].status != "matched"


def test_compound_partial_natural_language_is_not_awarded_and_its_citations_remain():
    req = _typed()[7]
    cv = "Professional experience\n- Investigated fabric defects on production lines."
    source = next(s for s in segment_resume(cv) if "Investigated" in s.text)
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[_row(req, source)], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].evidence_ids == [source.segment_id]
    assert checked[0].evidence_segments[0].text == source.text


def test_compound_mixed_partial_work_does_not_earn_credit():
    req = _typed()[6]
    cv = "Professional experience\n- Investigated warp and weft breaks on site."
    source = next(s for s in segment_resume(cv) if "Investigated" in s.text)
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[_row(req, source)], resume_text=cv)
    assert checked[0].status != "matched"
    assert checked[0].evidence_ids == [source.segment_id]


def test_compound_qualitative_work_is_cross_profession_without_skill_dictionary():
    requirement = "Incident identification and corrective action during audits"
    req = add_requirement_types([ValidatedRequirement(requirement_id="R777",
                              name=requirement, jd_evidence=requirement,
                              priority="required")], requirement)[0]
    cv = "Professional experience\n- Investigated incidents and recorded corrections during audits."
    source = next(s for s in segment_resume(cv) if "Investigated" in s.text)
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[_row(req, source)], resume_text=cv)
    assert checked[0].status == "matched"
    assert checked[0].review_recommended


def test_compound_negated_work_cannot_become_a_model_confirmed_match():
    req = _typed()[7]
    cv = "Professional experience\n- Investigated fabric defects but never performed corrective actions."
    source = next(s for s in segment_resume(cv) if "Investigated" in s.text)
    checked, _, _ = apply_compound_checks(
        requirements=[req], assessments=[_row(req, source)], resume_text=cv)
    assert checked[0].status != "matched"


def test_complete_source_grounded_assessment_keeps_all_18_validated_requirements():
    """Replays the approved 16 JD + 2 qualification requirements end to end.

    It does not fake cloud replies: all supplied model verdicts are explicitly
    marked as synthetic and every source segment is independently validated.
    """
    requirements = _typed()
    segments = segment_resume(CV)
    excerpts = [
        "7 years 4 months", "BS Textile Engineering", "Supervise 76",
        "set daily weaving plans", "Read weave patterns", "Coordinate beam",
        "Investigate warp", "fabric defect corrections", "Report loom efficiency",
        "Plan preventive", "Prepare shift handovers", "Supervise 76",
        "Operate electronic dobby", "fabric CAD software", "ERP/MES dashboards",
        "Led 5S", "Worked with cotton", "compressed-air leakage",
    ]
    rows = []
    for req, excerpt in zip(requirements, excerpts, strict=True):
        source = next(s for s in segments if excerpt in s.text)
        row = _row(req, source)
        if req.requirement_id == "R001":
            heading = next(s for s in segments if "2019 - Present" in s.text)
            row = row.model_copy(update={
                "evidence_ids": [source.segment_id, heading.segment_id],
                "evidence_segments": [
                    EvidenceCitation(segment_id=s.segment_id,
                                     section=s.section, text=s.text)
                    for s in (source, heading)
                ],
            })
        rows.append(row)
    after_exp, _, _ = apply_experience_checks(
        requirements=requirements, assessments=rows, resume_text=CV)
    after_degree, _, _ = apply_qualification_checks(
        requirements=requirements, assessments=after_exp, resume_text=CV)
    after_compound, _, _ = apply_compound_checks(
        requirements=requirements, assessments=after_degree, resume_text=CV)
    final = reconcile_final_assessments(
        requirements=requirements, assessments=after_compound)
    assert len(final) == 18
    assert all(r.status == 'matched' and r.unified_status == 'Found'
               for r in final), [(r.requirement_id, r.status, r.reason)
                                 for r in final if r.status != 'matched']
    assert all(r.evidence_segments for r in final)
    score = score_candidate(candidate_name="Test CV", requirements=requirements,
                            assessments=final, evaluation_mode="mixed", errors=[])
    assert score.matched_required == score.total_required == 11
    assert score.matched_preferred == score.total_preferred == 7
    assert score.primary_score == 100.0

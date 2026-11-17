"""M0/M2 regressions: unambiguous prior source-grounded verdicts must survive
syntactic JD review, while genuine explicit conditions and missing proof remain strict.
All identities and source text are fictional. No LLM/provider calls are performed.
"""

from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.pipeline import reconcile_final_assessments
from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.scoring import score_candidate
from cv_ranker.segments import segment_resume


def _req(text, kind="other", operator="complex", options=None):
    return ValidatedRequirement(
        requirement_id="R001", name=text, jd_evidence=text, priority="required",
        constraint=RequirementConstraint(kind=kind, operator=operator,
                                         options=options or [], requires_review=True),
    )


def _row(cv, status, verdict, reason="Previously source-validated model relationship"):
    segments = segment_resume(cv)
    # Citation identity always uses actual segment_resume output.
    chosen = next(s for s in segments if s.section in {"skills", "experience", "projects"}
                  and any(w in s.text.casefold() for w in ("yarn", "dashboard", "python", "inventory")))
    source = EvidenceCitation(segment_id=chosen.segment_id, section=chosen.section,
                              text=chosen.text)
    return RequirementAssessment(
        requirement_id="R001", status=status, unified_status=verdict,
        evidence_ids=[source.segment_id], evidence_segments=[source],
        evidence=source.text, reason=reason,
    )


def _final(req, cv, row):
    compound, _, _ = apply_compound_checks(
        requirements=[req], assessments=[row], resume_text=cv)
    final = reconcile_final_assessments(requirements=[req], assessments=compound)[0]
    return compound[0], final


def test_complex_knowledge_self_report_is_not_destroyed_by_surface_syntax():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Technical skills\nKnowledge of yarn count and quality for cotton and polyester-blend woven fabrics."
    before = _row(cv, "matched", "Found")
    checked, final = _final(req, cv, before)
    assert checked.status == "matched"
    assert final.unified_status == "Found"
    assert final.evidence_ids == before.evidence_ids
    assert final.review_recommended
    score = score_candidate(candidate_name="Fictional", requirements=[req],
                            assessments=[final], evaluation_mode="llm_assessed", errors=[])
    assert score.primary_score == 100.0


def test_source_backed_adjacent_work_is_not_deleted_by_complex_syntax():
    req = _req("Use of ERP or manufacturing execution systems (MES) for weaving production reporting")
    cv = "Professional experience\n- Built SQL dashboards for production and shift reporting without ERP or MES access."
    before = _row(cv, "not_matched", "Transferable",
                  "Built reporting dashboards; ERP/MES use is not established.")
    checked, final = _final(req, cv, before)
    assert checked.status != "matched"
    assert final.unified_status == "Transferable"
    assert final.evidence_ids == before.evidence_ids
    score = score_candidate(candidate_name="Fictional", requirements=[req],
                            assessments=[final], evaluation_mode="llm_assessed", errors=[])
    assert score.primary_score == 0.0


def test_no_positive_citation_cannot_become_found_from_syntax_review():
    req = _req("Both Python and SQL are required for operational reports.", "skill")
    row = RequirementAssessment(requirement_id="R001", status="matched", unified_status="Found",
                                evidence_ids=[], evidence_segments=[], reason="Unsubstantiated proposal")
    checked, final = _final(req, "Experience\nUnrelated inventory work", row)
    assert final.unified_status != "Found"


def test_explicit_both_skills_must_satisfy_both_parts():
    req = _req("Python and Django", "skill", "all_of", ["Python", "Django"])
    cv = "Technical skills\nPython only. No Django."
    row = _row(cv, "matched", "Found")
    checked, final = _final(req, cv, row)
    assert final.unified_status != "Found"


def test_original_negative_stays_negative_after_review():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Skills\nOnly inventory ordering and purchasing controls."
    row = RequirementAssessment(requirement_id="R001", status="not_matched", unified_status="Not Found")
    checked, final = _final(req, cv, row)
    assert final.unified_status == "Not Found"


def test_technical_failure_stays_unverified():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    row = RequirementAssessment(requirement_id="R001", status="uncertain", unified_status="Unverified",
                                assessment_state="unverified")
    _, final = _final(req, "Experience\nInventory supervisor", row)
    assert final.unified_status is None
    assert final.current_decision.verdict is None
    assert final.assessment_state == "unverified"


def test_reapplying_finalizer_does_not_change_successful_decision():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Skills\nKnowledge of yarn count and quality for cotton and polyester-blend woven fabrics."
    _, final = _final(req, cv, _row(cv, "matched", "Found"))
    second = reconcile_final_assessments(requirements=[req], assessments=[final])[0]
    assert second.model_dump() == final.model_dump()


def test_citation_with_foreign_segment_id_cannot_rescue_complex_found():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Skills\nKnowledge of yarn count and quality for cotton and polyester-blend woven fabrics."
    forged = _row(cv, "matched", "Found")
    forged = forged.model_copy(update={
        "evidence_ids": ["S999"],
        "evidence_segments": [EvidenceCitation(segment_id="S999", section="skills",
                                             text=forged.evidence_segments[0].text)],
    })
    checked, final = _final(req, cv, forged)
    assert checked.status != "matched"
    assert final.unified_status != "Found"


def test_same_segment_id_with_wrong_original_text_cannot_rescue():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Skills\nKnowledge of yarn count and quality for cotton and polyester-blend woven fabrics."
    forged = _row(cv, "matched", "Found")
    forged = forged.model_copy(update={
        "evidence_segments": [EvidenceCitation(
            segment_id=forged.evidence_ids[0], section="skills",
            text=forged.evidence_segments[0].text + " Fake extra capability")]
    })
    _, final = _final(req, cv, forged)
    assert final.unified_status != "Found"


def test_syntax_review_retains_structured_transition_without_cv_text():
    req = _req("Knowledge of yarn count and quality for cotton and polyester-blend woven fabrics.", "skill")
    cv = "Skills\nKnowledge of yarn count and quality for cotton and polyester-blend woven fabrics."
    before = _row(cv, "matched", "Found")
    checked, final = _final(req, cv, before)
    assert not before.decision_trace
    assert final.decision_trace
    assert final.decision_trace[0].reason_code == "syntax_review_not_candidate_failure"
    assert final.decision_trace[0].evidence_ids == before.evidence_ids
    assert cv not in str(final.decision_trace[0].model_dump())
    assert final.model_dump() == reconcile_final_assessments(
        requirements=[req], assessments=[final])[0].model_dump()


def test_compound_negative_transition_is_explained_and_source_preserved():
    req = _req("Python and Django", "skill", "all_of", ["Python", "Django"])
    cv = "Technical skills\nPython only, never used Django."
    before = _row(cv, "matched", "Found")
    checked, final = _final(req, cv, before)
    assert final.status != "matched"
    assert final.unified_status != "Found"
    assert any(t.stage == "compound_validation" and
               t.reason_code == "explicit_compound_source_check" for t in final.decision_trace)
    assert final.evidence_segments


def test_context_fingerprint_includes_final_reconciliation(tmp_path):
    """An edited decision module must never reuse a previous cached outcome."""
    from cv_ranker.resume import _ASSESSMENT_LOGIC_FILES, assessment_logic_fingerprint
    from pathlib import Path
    package_root = Path(__file__).resolve().parents[1] / "cv_ranker"
    assert "pipeline.py" in _ASSESSMENT_LOGIC_FILES
    assert "schemas.py" in _ASSESSMENT_LOGIC_FILES
    for name in _ASSESSMENT_LOGIC_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((package_root / name).read_bytes())
    baseline = assessment_logic_fingerprint(tmp_path)
    module = tmp_path / "pipeline.py"
    module.write_bytes(module.read_bytes() + b"\n# synthetic change to decision logic\n")
    assert assessment_logic_fingerprint(tmp_path) != baseline
    # A presentation file is deliberately outside the decision fingerprint.
    (tmp_path / "style.css").write_text("body { color: blue; }")
    assert assessment_logic_fingerprint(tmp_path) != baseline

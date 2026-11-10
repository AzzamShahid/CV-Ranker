"""Render V4.8 verified candidate assessments without calling an LLM again.

The existing assessment pipeline is the only source of scoring decisions. This
adapter preserves the long-standing supervisor UI/export shape and source IDs.
"""
from __future__ import annotations

from cv_ranker.schemas import RankingReport
from cv_ranker.ui.evidence_inspection import resume_segments


def reconcile_unified_candidate(report: RankingReport, candidate_index: int,
                                ledger: list[dict]) -> dict:
    candidate = report.candidates[candidate_index]
    originals = {s.segment_id: s for s in resume_segments(ledger)}
    assessments = {a.requirement_id: a for a in candidate.assessments}
    criteria: list[dict] = []
    # These are the same assessment/validation notices shown in the candidate
    # panel, preserved in the complete audit JSON for supervisor review.
    notices: list[str] = list(dict.fromkeys(candidate.errors))
    if candidate.primary_score is None:
        failure = ("Candidate assessment is incomplete; valid individual requirement "
                   "decisions remain available, but no overall score or rank is claimed."
                   if candidate.assessments else
                   "Candidate assessment failed before individual requirement decisions were available.")
        if failure not in notices:
            notices.append(failure)

    for req in report.requirements:
        assessment = assessments.get(req.requirement_id)
        final = (assessment.unified_status if assessment is not None else None)
        if (assessment is not None and assessment.assessment_state == "unverified") or (
                assessment is None and candidate.primary_score is None):
            final = "Unverified"
        elif final is None:
            final = "Found" if assessment is not None and assessment.status == "matched" else "Not Found"
        # The score boundary remains authoritative after qualification/tenure
        # validators. A display verdict can never add a scoring point.
        if final == "Found" and (assessment is None or assessment.status != "matched"):
            final = "Not Found"
        elif final == "Transferable" and assessment is not None and assessment.status == "matched":
            final = "Found"

        checkpoints = []
        if assessment is not None:
            if assessment.reason.startswith("The model did not produce a valid source-grounded decision"):
                source_label = "Unverified retrieval lead · human review only"
            elif assessment.reason.startswith("The LLM response remained invalid"):
                source_label = "Existing exact-source validator · review recommended"
            elif assessment.review_checkpoint_origin == "retrieval":
                source_label = "Original CV passage · review context, not scoring evidence"
            elif assessment.unified_status == "Not Found":
                source_label = "Original CV checkpoint · reviewed but not credited"
            else:
                source_label = "Unified LLM assessment · original CV citation"
            seen = set()
            for citation in assessment.evidence_segments:
                if citation.segment_id in seen:
                    continue
                seen.add(citation.segment_id)
                original = originals.get(citation.segment_id)
                verified = (original is not None and original.text == citation.text)
                checkpoints.append({
                    "Segment": citation.segment_id,
                    "Section": original.section if original else citation.section,
                    "Text": original.text if original else citation.text,
                    "Sources": [source_label],
                    "Why": ["Criterion-level reasoning (considers the cited evidence together): " +
                            (assessment.reason or "This source was cited by the assessed requirement.")],
                    "Highlight terms": [assessment.matched_term] if assessment.matched_term else [],
                    "Validated against CV": verified,
                })

        review = bool(assessment.review_recommended) if assessment is not None else True
        if candidate.primary_score is None or any(not p["Validated against CV"] for p in checkpoints):
            review = True
        if final == "Found" and not checkpoints:
            # An ungrounded positive has no right to survive presentation.
            final, review = "Unverified", True
        explanation = assessment.reason if assessment else "Assessment unavailable; this is not evidence of absence."
        # The *final* row reasoning is authoritative: specialist validators
        # already reconciled it with the changed status. Overwriting it here
        # with a lower-level diagnostic was the root cause of an explanation
        # saying "closely related" under a Not Found degree label, and of
        # experience rows displaying a generic role-date message instead of
        # why their final decision was made.
        if final == "Unverified":
            level = "Technical assessment incomplete · retrieval leads are not proof"
            review = True
        elif final == "Transferable":
            level = ("Related completed qualification, not direct requirement credit"
                     if req.constraint.kind == 'education' else
                     "Related completed work, not direct requirement credit")
            review = True
        elif final == "Not Found":
            level = "Uncertain evidence" if review else "Not established by this CV"
        elif any(p["Section"] in {"work_experience", "experience", "projects"} for p in checkpoints):
            level = "Described in work/projects"
        elif any(p["Section"] in {"skills", "inferred_skills"} for p in checkpoints):
            level = "Stated in skills"
        else:
            level = "CV-reported capability"

        criteria.append({
            "ID": req.requirement_id, "Requirement": req.name,
            "Priority": req.priority.title(), "Result": final,
            "Evidence level": level, "Why": explanation or "No supporting source was established.",
            "JD source": req.jd_evidence, "Kind": req.constraint.kind,
            "Checkpoints": checkpoints, "Focused check": False,
            "Display checkpoints": checkpoints[:4] if final == "Not Found" else checkpoints,
            "Total checkpoints considered": len(checkpoints),
            "Review recommended": review,
            "Primary diagnostic": {
                "status": assessment.status if assessment else "missing",
                "reason": assessment.reason if assessment else "",
            },
            "AI diagnostic": [],
        })

    return {
        "Candidate": candidate.candidate_name,
        "Required matched": sum(r["Priority"] == "Required" and r["Result"] == "Found" for r in criteria),
        "Required total": sum(r["Priority"] == "Required" for r in criteria),
        "Preferred matched": sum(r["Priority"] == "Preferred" and r["Result"] == "Found" for r in criteria),
        "Preferred total": sum(r["Priority"] == "Preferred" for r in criteria),
        "Transferable": sum(r["Result"] == "Transferable" for r in criteria),
        "Unverified": sum(r["Result"] == "Unverified" for r in criteria),
        "Criteria": criteria, "Notices": notices,
        "Run warnings": list(report.warnings),
        # A successfully corrected model citation/typed check is a historical
        # notice, not evidence that the *final* verdict remains provisional.
        "Provisional": (candidate.primary_score is None or
                        any(r["Review recommended"] for r in criteria)),
    }

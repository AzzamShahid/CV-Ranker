"""Evidence-traceable, call-free explanations of the *current* weighted ranking.

Never modifies frozen JD, CV decisions, primary scores, or leaderboard ranks.
Reasoning is projected from checked result rows and the same score contributions
that drive the table. Structural inconsistencies are repaired deterministically;
an unbounded additional model request is neither needed nor permitted here.
"""
from __future__ import annotations

import re

from .schemas import RankingReport, RequirementAssessment
from .weighted_scoring import ScoreWeights, weighted_candidate, weighted_leaderboard


def _assessment_verdict(assessment: RequirementAssessment | None) -> str:
    if assessment is None or assessment.assessment_state == "unverified" or assessment.unified_status == "Unverified":
        return "Unverified"
    if assessment.status == "matched" and assessment.unified_status in (None, "Found"):
        return "Found"
    if assessment.unified_status == "Transferable" and assessment.status != "matched":
        return "Transferable"
    return "Not Found"


def _fallback_reason(requirement: str, verdict: str, sources: list[str]) -> str:
    if verdict == "Found":
        suffix = " Supporting statements were verified against the original CV." if sources else (
            " The original CV citation was not independently available for this summary; inspect the assessment.")
        return f"The validated assessment records {requirement} as Found.{suffix}"
    if verdict == "Transferable":
        return (f"The assessment records work related to {requirement}, but not direct satisfaction "
                "of this specific requirement; this receives no scoring credit.")
    if verdict == "Unverified":
        return f"The assessment of {requirement} is incomplete; no match or nonmatch can safely be asserted."
    return (f"The validated assessment does not establish {requirement} from this CV. "
            "This is not proof that the candidate lacks the capability.")


def _reader_reason(value: str) -> str:
    """Keep internal source IDs in audit data, not supervisor-facing prose."""
    clean = re.sub(r"\b(?:CV\s+)?(?:segment|source)\s+S\d{2,}\b",
                   "the cited CV passage", value, flags=re.I)
    clean = re.sub(r"\bS\d{2,}\b", "the cited CV passage", clean)
    return clean.strip()


def _criterion_preview(items: list[dict], *, limit: int = 3) -> str:
    names = [item["requirement"] for item in items[:limit]]
    return ", ".join(names)


def candidate_reasoning(
    report: RankingReport, candidate_index: int, weights: ScoreWeights,
    final_results: dict[str, dict] | None = None,
    source_ledgers: dict[str, list[dict]] | None = None,
) -> dict:
    """Audit and repair reasoning, preserving the authoritative scored decisions.

    A "repair" here is a local regeneration of a missing/inconsistent explanation
    from the already validated source IDs. It never issues an HTTP/model call.
    The audit checks structural/source consistency, not semantic truth of free text.
    """
    candidate = report.candidates[candidate_index]
    score = weighted_candidate(report, candidate, weights)
    leaderboard = weighted_leaderboard(report, weights)
    rank = next(row["rank"] for row in leaderboard if row["candidate_index"] == candidate_index)
    final = (final_results or {}).get(str(candidate_index)) or {}
    retained = (source_ledgers or {}).get(str(candidate_index))
    originals = ({entry["segment_id"]: entry["text"] for entry in retained
                  if isinstance(entry, dict) and isinstance(entry.get("segment_id"), str)
                  and isinstance(entry.get("text"), str)} if isinstance(retained, list) else None)
    rows = {row.get("ID"): row for row in final.get("Criteria", []) if isinstance(row, dict)}
    assessments = {item.requirement_id: item for item in candidate.assessments}
    contributions = {row["requirement_id"]: row for row in score.get("requirement_contributions", [])}
    checks = []
    repairs = []
    details = []
    for req in report.requirements:
        rid = req.requirement_id
        assessment = assessments.get(rid)
        verdict = _assessment_verdict(assessment)
        row = rows.get(rid)
        errors = []
        if row is None:
            errors.append("Final reasoning row missing")
        elif row.get("Result") != verdict:
            errors.append("Final decision contradicts the validated assessment")
        checkpoints = row.get("Checkpoints", []) if row else []
        if not isinstance(checkpoints, list):
            checkpoints = []
            errors.append("Invalid source checkpoint list")
        source_ids = []
        for checkpoint in checkpoints:
            if not isinstance(checkpoint, dict):
                errors.append("Malformed source checkpoint")
                continue
            sid = checkpoint.get("Segment")
            source_matches = (originals is None or originals.get(sid) == checkpoint.get("Text"))
            if (checkpoint.get("Validated against CV") is True and isinstance(sid, str)
                    and sid and source_matches):
                if sid not in source_ids:
                    source_ids.append(sid)
            else:
                errors.append("Unverified, absent or altered original CV source excluded from reasoning")
        text = row.get("Why", "") if row else ""
        if not isinstance(text, str) or not text.strip():
            errors.append("Reasoning absent")
        if verdict == "Found" and not source_ids:
            errors.append("Found without independently retained, validated source passage")
        if row is not None and row.get("Result") != verdict:
            text = ""
        if errors or not text:
            text = _fallback_reason(req.name, verdict, source_ids)
            repairs.append({"requirement_id": rid, "issues": list(dict.fromkeys(errors)),
                            "action": "reconstructed explanation; scoring unchanged"})
        points = contributions.get(rid, {})
        details.append({
            "requirement_id": rid, "requirement": req.name, "priority": req.priority,
            "category": points.get("category"), "decision": verdict,
            "why": _reader_reason(text), "validated_segment_ids": source_ids,
            "possible_points": points.get("possible_points"),
            "earned_points": points.get("earned_points"),
            "reasoning_repaired": bool(errors),
        })
    if candidate.primary_score is None:
        checks.append("Assessment incomplete; no weighted score/rank is asserted")
    elif originals is None:
        checks.append("Original CV source ledger unavailable for independent reasoning revalidation")
    elif not contributions:
        checks.append("Weighted scoring was not available")
    elif abs(sum(row["earned_points"] for row in details) - score["score"]) > 0.011:
        checks.append("Reasoning contribution totals disagree with weighted score")

    found = sorted((item for item in details if item["decision"] == "Found"),
                   key=lambda item: (-(item["earned_points"] or 0), item["requirement_id"]))
    missed = sorted((item for item in details if item["decision"] == "Not Found"),
                    key=lambda item: (-(item["possible_points"] or 0), item["requirement_id"]))
    transferable = [item for item in details if item["decision"] == "Transferable"]
    if score["score"] is None:
        summary = (f"{candidate.candidate_name}: ranking withheld because the validated "
                   "assessment is incomplete. Available reasoning is provisional.")
    else:
        summary = (f"{candidate.candidate_name} ranks #{rank} at {score['score']:.2f}%. "
                   f"The candidate earns credit for {len(found)} verified Found criteria; "
                   f"{len(missed)} Not Found and {len(transferable)} Transferable criteria "
                   "earn no credit. Each criterion contributes according to its edited category share.")
        if found:
            summary += " Strongest scored evidence: " + _criterion_preview(found) + "."
        if missed:
            summary += " Largest unmet requirements: " + _criterion_preview(missed, limit=2) + "."
    return {
        "candidate_index": candidate_index, "candidate": candidate.candidate_name,
        "rank": rank, "weighted_score": score["score"], "summary": summary,
        "strengths": found, "gaps": missed, "transferable": transferable,
        "criteria": details, "audit": {
            "checked_requirements": len(report.requirements),
            "repairs": repairs, "warnings": checks,
            "status": "incomplete" if score["score"] is None else (
                "needs_review" if checks or repairs else "structurally_valid"),
            "external_reasoning_requests": 0,
            "validation_scope": "Final-decision consistency, scoring arithmetic and retained CV source IDs; free-text semantic truth still requires human review",
        },
    }


def comparative_reasoning(report: RankingReport, weights: ScoreWeights,
                          final_results: dict[str, dict] | None = None,
                          source_ledgers: dict[str, list[dict]] | None = None) -> dict:
    """Explain every ranked placement, including ties and withheld candidates."""
    rows = weighted_leaderboard(report, weights)
    explanations = {i: candidate_reasoning(report, i, weights, final_results, source_ledgers)
                    for i in range(len(report.candidates))}
    ranked = [row for row in rows if row["rank"] is not None]
    if not ranked:
        for explanation in explanations.values():
            pending = [item["requirement"] for item in explanation["criteria"]
                       if item["decision"] == "Unverified"]
            explanation["placement_reason"] = (
                "A reliable rank cannot be assigned while the assessment remains unverified"
                + (": " + ", ".join(pending[:4]) if pending else "") + ".")
        return {"summary": "No verified weighted ranking is available yet.",
                "top_candidate_indices": [], "comparisons": [],
                "candidates": [explanations[row["candidate_index"]] for row in rows]}
    first = ranked[0]
    winners = [r for r in ranked if r["rank"] == 1]
    if len(winners) > 1:
        summary = ("Joint top priority: " + ", ".join(r["candidate"] for r in winners)
                   + f" each scores {first['weighted_score']:.2f}%. "
                   "Equal weighted scores are ties; preference ordering is not invented.")
    else:
        summary = (f"{first['candidate']} is top priority with {first['weighted_score']:.2f}% "
                   "on the current approved weights and validated Found evidence.")
    comparisons = []
    for row in ranked[1:]:
        if row["candidate_index"] == first["candidate_index"]:
            continue
        a = {item["requirement_id"]: item for item in explanations[first["candidate_index"]]["criteria"]}
        b = {item["requirement_id"]: item for item in explanations[row["candidate_index"]]["criteria"]}
        advantages = [a[rid] for rid in a if a[rid]["decision"] == "Found" and b[rid]["decision"] != "Found"]
        counteradvantages = [b[rid] for rid in b if b[rid]["decision"] == "Found" and a[rid]["decision"] != "Found"]
        comparisons.append({
            "against_candidate_index": row["candidate_index"],
            "against": row["candidate"], "rank": row["rank"],
            "score_gap": round(first["weighted_score"] - row["weighted_score"], 2),
            "top_candidate_advantages": sorted(advantages, key=lambda v: -(v["possible_points"] or 0)),
            "other_candidate_advantages": sorted(counteradvantages, key=lambda v: -(v["possible_points"] or 0)),
            "is_tie": row["rank"] == 1,
        })
    by_other = {item["against_candidate_index"]: item for item in comparisons}
    for row in rows:
        explanation = explanations[row["candidate_index"]]
        if row["rank"] is None:
            pending = [item["requirement"] for item in explanation["criteria"]
                       if item["decision"] == "Unverified"]
            explanation["placement_reason"] = (
                "No rank has been issued because "
                + ("the following requirements still need a valid assessment: "
                   + ", ".join(pending[:4]) + "." if pending else
                   "the assessment is technically incomplete."))
        elif row["rank"] == 1:
            explanation["placement_reason"] = (
                f"Top-ranked at {row['weighted_score']:.2f}% because the "
                "current JD weights favor the candidate's verified matches"
                + (", especially " + _criterion_preview(explanation["strengths"])
                   if explanation["strengths"] else "")
                + (". This position is tied with another candidate." if len(winners) > 1 else
                   ". This is the highest verified weighted total."))
        else:
            diff = by_other.get(row["candidate_index"], {})
            leading = diff.get("top_candidate_advantages", [])
            own = diff.get("other_candidate_advantages", [])
            explanation["placement_reason"] = (
                f"Rank #{row['rank']} at {row['weighted_score']:.2f}% "
                f"({diff.get('score_gap', 0):.2f} points behind the top candidate). "
                + ("The leader has additional verified credit for "
                   + _criterion_preview(leading) + ". " if leading else "")
                + ("This candidate has an advantage in "
                   + _criterion_preview(own, limit=2) + ". " if own else "")
                + ("Their largest gaps include "
                   + _criterion_preview(explanation["gaps"], limit=2) + "."
                   if explanation["gaps"] else
                   "Their position follows the verified scoring contributions."))
    return {"summary": summary,
            "top_candidate_indices": [r["candidate_index"] for r in winners],
            "comparisons": comparisons,
            "candidates": [explanations[row["candidate_index"]] for row in rows]}

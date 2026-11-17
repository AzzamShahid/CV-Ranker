"""Configurable supervisor weights over *existing, validated* JD decisions.

The 10/10/80 view is a reporting/ranking projection, not a second assessor.
Every frozen criterion belongs to exactly one category; no CV-only category
can invent a requirement or provide automatic scoring credit.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

from .schemas import CandidateResult, RankingReport, RequirementAssessment, ValidatedRequirement
from .decision_contract import incomplete


@dataclass(frozen=True)
class ScoreWeights:
    experience: int = 10
    education: int = 10
    jd: int = 80
    split_jd: bool = False  # Only changes how the JD groups are displayed.
    required_share: int = 80  # Legacy setting: ignored for scoring.
    # Frozen JD requirement IDs and their percentage of their OWN category.
    # Empty means equal shares, preserving the previous scoring defaults.
    requirement_shares: tuple[tuple[str, float], ...] = ()
    # Explicit v48 opt-in: old split_jd remains a display-only legacy option.
    jd_allocation_mode: str = "pooled"  # pooled | weighted_split

    def __post_init__(self) -> None:
        for name in ("experience", "education", "jd", "required_share"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                raise ValueError(f"{name} must be an integer from 0 to 100")
        if not isinstance(self.split_jd, bool):
            raise ValueError("split_jd must be a Boolean")
        if self.jd_allocation_mode not in {"pooled", "weighted_split"}:
            raise ValueError("jd_allocation_mode must be pooled or weighted_split")
        if not self.experience + self.education + self.jd:
            raise ValueError("At least one category must have positive weight")
        if self.experience + self.education + self.jd != 100:
            raise ValueError("Weights must add to exactly 100 marks")
        ids = set()
        for requirement_id, share in self.requirement_shares:
            if not isinstance(requirement_id, str) or not requirement_id.strip() or requirement_id in ids:
                raise ValueError("Requirement allocation IDs must be unique and nonempty")
            if isinstance(share, bool) or not isinstance(share, (int, float)) or not isfinite(share) or not 0 <= share <= 100:
                raise ValueError("Requirement shares must be finite percentages from 0 to 100")
            ids.add(requirement_id)

    @property
    def jd_required_share(self) -> int:
        return self.required_share

    @property
    def jd_preferred_share(self) -> int:
        return 100 - self.jd_required_share

    def as_dict(self) -> dict[str, object]:
        return {"experience": self.experience, "education": self.education,
                "jd": self.jd, "split_jd": self.split_jd,
                "jd_view": "separate_counts" if self.split_jd else "combined_counts",
                "jd_allocation": self.jd_allocation_mode,
                "jd_required_share": self.required_share if self.jd_allocation_mode == "weighted_split" else None,
                "jd_preferred_share": (100 - self.required_share) if self.jd_allocation_mode == "weighted_split" else None,
                "requirement_shares_percent_of_category": dict(self.requirement_shares),
                "default_requirement_allocation": "equal" if not self.requirement_shares else "custom"}


def requirement_bucket(req: ValidatedRequirement) -> str:
    # Calendar-gated tenure has its own weight. Qualitative completed-work
    # competency (e.g. shipping APIs) remains a JD requirement even when the
    # extractor calls its type "experience"; it has no year threshold.
    if req.constraint.kind == "experience" and req.constraint.minimum_years is not None:
        return "experience"
    if req.constraint.kind == "education":
        return "education"
    return "jd_preferred" if req.priority == "preferred" else "jd_required"


def jd_scoring_group(req: ValidatedRequirement) -> str:
    """Unknown priority is scored with Required, but remains labeled unknown.

    This is a JD bucket policy, not an assertion that the employer said
    'Required'. Preserve the original priority in exports and review.
    """
    return "preferred" if req.priority == "preferred" else "required"


def _earned(item: RequirementAssessment) -> bool:
    if item.current_decision is not None:
        return (item.current_decision.processing_state == "completed" and
                item.current_decision.verdict == "Found")
    return (item.assessment_state == "verified" and item.status == "matched"
            and item.unified_status in {None, "Found"})


def allocation_bucket(req: ValidatedRequirement) -> str:
    """Required and Preferred deliberately share ONE JD denominator."""
    bucket = requirement_bucket(req)
    return "jd" if bucket.startswith("jd_") else bucket


def even_requirement_shares(requirements: list[ValidatedRequirement]) -> dict[str, float]:
    """Full-precision equal category shares (avoid rounding bias across JD items)."""
    buckets: dict[str, list[str]] = {}
    for req in requirements:
        buckets.setdefault(allocation_bucket(req), []).append(req.requirement_id)
    if len({r.requirement_id for r in requirements}) != len(requirements):
        raise ValueError("Frozen JD requirement IDs must be unique")
    result: dict[str, float] = {}
    for ids in buckets.values():
        for identifier in ids:
            result[identifier] = 100.0 / len(ids)
    return result


def rebalance_requirement_share(
    requirements: list[ValidatedRequirement], shares: dict[str, float],
    changed_id: str, new_share: float,
) -> dict[str, float]:
    """Set one share exactly; redistribute its peers proportionally to total 100%."""
    expected = {r.requirement_id: allocation_bucket(r) for r in requirements}
    if changed_id not in expected or set(shares) != set(expected):
        raise ValueError("Allocation does not match the approved frozen JD")
    # Validate raw user input BEFORE rounding: -0.001 and 100.001 must
    # not become valid endpoints through centi-percent quantization.
    if (not isinstance(new_share, (int, float)) or isinstance(new_share, bool)
            or not isfinite(new_share) or not 0 <= new_share <= 100):
        raise ValueError("New share must be a finite number between 0 and 100")
    target_units = int((Decimal(str(new_share)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not 0 <= target_units <= 10000:
        raise ValueError("New share must be between 0 and 100%")
    peers = [rid for rid, bucket in expected.items()
             if bucket == expected[changed_id] and rid != changed_id]
    if not peers:
        if target_units != 10000:
            raise ValueError("A category with one requirement must allocate it 100%")
        return dict(shares)
    remaining = 10000 - target_units
    peer_values = [max(0.0, shares[rid]) for rid in peers]
    peer_total = sum(peer_values)
    ratios = ([v / peer_total for v in peer_values] if peer_total > 0
              else [1 / len(peers)] * len(peers))
    exact = [remaining * ratio for ratio in ratios]
    units = [int(value) for value in exact]
    spare = remaining - sum(units)
    for index in sorted(range(len(peers)), key=lambda i: (-(exact[i] - units[i]), i))[:spare]:
        units[index] += 1
    updated = dict(shares)
    updated[changed_id] = target_units / 100
    for rid, value in zip(peers, units):
        updated[rid] = value / 100
    return updated


def _validated_shares(report: RankingReport, weights: ScoreWeights) -> dict[str, float]:
    if not weights.requirement_shares:
        return even_requirement_shares(report.requirements)
    shares = dict(weights.requirement_shares)
    known = {r.requirement_id: allocation_bucket(r) for r in report.requirements}
    if len(known) != len(report.requirements) or set(shares) != set(known):
        raise ValueError("Customized allocations must cover precisely the approved JD IDs")
    totals: dict[str, float] = {}
    for identifier, share in shares.items():
        totals[known[identifier]] = totals.get(known[identifier], 0.0) + share
    for category, total in totals.items():
        if abs(total - 100.0) > 1e-6:
            raise ValueError(f"{category} requirement shares must total 100%, got {total:.2f}%")
    return shares


def criterion_bucket_counts(report: RankingReport,
                            candidate: CandidateResult | None = None) -> dict[str, dict[str, int]]:
    """Disjoint counts for the weighted Experience/Education/JD categories.

    These are presentation/scoring buckets, not replacements for the full
    frozen-JD reconciliation totals retained in the original audit record.
    """
    counts = {key: {"found": 0, "total": 0}
              for key in ("experience", "education", "jd_required", "jd_preferred")}
    assessments = ({a.requirement_id: a for a in candidate.assessments}
                   if candidate is not None else {})
    for requirement in report.requirements:
        bucket = requirement_bucket(requirement)
        counts[bucket]["total"] += 1
        evidence = assessments.get(requirement.requirement_id)
        counts[bucket]["found"] += int(evidence is not None and _earned(evidence))
    return counts


def weighted_candidate(report: RankingReport, candidate: CandidateResult,
                       weights: ScoreWeights) -> dict[str, object]:
    """Return verified Found credit, marking incomplete assessments provisional.

    Category weights are renormalized across present buckets only. JD always
    has exactly one scoring denominator: all Required + Preferred criteria,
    excluding separately weighted Experience and Education. The split option
    changes presentation only, never the points per JD requirement.
    Missing candidate evidence in a present bucket counts as zero.
    """
    requirements = {r.requirement_id: r for r in report.requirements}
    assessments = {a.requirement_id: a for a in candidate.assessments}
    if len(requirements) != len(report.requirements):
        raise ValueError("Duplicate frozen JD requirement IDs")
    if len(assessments) != len(candidate.assessments):
        raise ValueError("Duplicate candidate assessment IDs")
    if set(assessments) - set(requirements):
        raise ValueError("Candidate contains a foreign JD requirement ID")
    if not assessments:
        # An entirely missing evaluation is not a verified 0%. The old
        # supervisor report explicitly distinguishes Unavailable from zero.
        return {"score": None, "components": criterion_bucket_counts(report),
                "effective_weights": {}, "provisional": True,
                "unverified_ids": list(requirements), "possible_ceiling": None,
                "reason": "No candidate assessment was completed"}
    # Missing rows denote absent response data, never a current candidate
    # verdict or a mutation of the saved candidate/report.
    missing = set(requirements) - set(assessments)
    if missing:
        assessments.update({identifier: RequirementAssessment(
            requirement_id=identifier, status="uncertain", unified_status=None,
            assessment_state="unverified", review_recommended=True,
            reason="No assessment row was produced for the frozen requirement.",
            current_decision=incomplete("response_row_missing", stage="weighted_projection",
                detail="The frozen requirement has no candidate assessment row.")
        )
            for identifier in missing})
    snapshot = candidate.model_copy(update={"assessments": list(assessments.values())})
    counts = criterion_bucket_counts(report, snapshot)
    shares = _validated_shares(report, weights)

    raw = {"experience": weights.experience, "education": weights.education, "jd": weights.jd}
    jd_exists = counts["jd_required"]["total"] + counts["jd_preferred"]["total"] > 0
    enabled = {"experience": counts["experience"]["total"] > 0,
               "education": counts["education"]["total"] > 0,
               "jd": jd_exists}
    active = sum(value for key, value in raw.items() if enabled[key])
    if not active:
        return {"score": None, "components": counts, "effective_weights": {},
                "reason": "No positive weight applies to the frozen JD"}

    # In explicit weighted-split mode, normalize custom criterion shares
    # *within* each Required/Preferred group. The reviewed group percentage
    # controls their relative overall weight; no arbitrary 50/50 default.
    split_group_totals = {
        "required": sum(shares[r.requirement_id] for r in report.requirements
                        if allocation_bucket(r) == "jd" and jd_scoring_group(r) == "required"),
        "preferred": sum(shares[r.requirement_id] for r in report.requirements
                         if allocation_bucket(r) == "jd" and jd_scoring_group(r) == "preferred"),
    }
    group_allocations = {"required": weights.required_share,
                         "preferred": 100 - weights.required_share}
    if weights.jd_allocation_mode == "weighted_split":
        active_group_total = sum(group_allocations[k] for k, v in split_group_totals.items() if v)
        if not active_group_total:
            # A single nonempty JD group with a user-selected zero share
            # still receives the entire active JD category (no lost points).
            group_allocations = {k: int(v > 0) for k, v in split_group_totals.items()}
            active_group_total = sum(group_allocations.values())
        for key in group_allocations:
            group_allocations[key] = (100.0 * group_allocations[key] / active_group_total
                                      if split_group_totals[key] else 0.0)
    jd_total = counts["jd_required"]["total"] + counts["jd_preferred"]["total"]
    jd_found = counts["jd_required"]["found"] + counts["jd_preferred"]["found"]
    effective: dict[str, float] = {}
    for key in ("experience", "education"):
        effective[key] = 100.0 * raw[key] / active if enabled[key] else 0.0
    effective["jd"] = 100.0 * weights.jd / active if jd_exists else 0.0
    contributions = []
    score = 0.0
    unresolved_ids: list[str] = []
    possible_remaining = 0.0
    for requirement in report.requirements:
        key = allocation_bucket(requirement)
        item = assessments[requirement.requirement_id]
        if key == "jd" and weights.jd_allocation_mode == "weighted_split":
            group = jd_scoring_group(requirement)
            group_total = split_group_totals[group]
            item_fraction = (shares[requirement.requirement_id] / group_total
                             if group_total > 0 else 0)
            possible = effective[key] * group_allocations[group] / 100 * item_fraction
        else:
            possible = effective[key] * shares[requirement.requirement_id] / 100
        earned = possible if _earned(item) else 0.0
        score += earned
        if ((item.current_decision is not None and
             item.current_decision.processing_state != "completed") or
            (item.current_decision is None and item.assessment_state == "unverified")):
            unresolved_ids.append(requirement.requirement_id)
            possible_remaining += possible
        contributions.append({
            "requirement_id": requirement.requirement_id,
            "requirement": requirement.name,
            "priority": requirement.priority,
            "category": key,
            "share_of_category": shares[requirement.requirement_id],
            "jd_group_allocation": (group_allocations.get(jd_scoring_group(requirement))
                                    if key == "jd" and weights.jd_allocation_mode == "weighted_split"
                                    else None),
            "possible_points": round(possible, 6),
            "earned_points": round(earned, 6),
            "found": bool(_earned(item)),
            "incomplete": item.assessment_state == "unverified",
        })
    provisional = bool(unresolved_ids)
    return {"score": round(score, 2), "components": counts,
            "jd_combined": {"found": jd_found, "total": jd_total},
            "effective_weights": {k: round(v, 4) for k, v in effective.items()},
            "requirement_contributions": contributions,
            "provisional": provisional, "unverified_ids": unresolved_ids,
            "possible_ceiling": round(min(100.0, score + possible_remaining), 2),
            "reason": ("Provisional lower-bound score: verified Found credit only; "
                       "incomplete criteria may change the order and require review"
                       if provisional else
                       "Verified Found only; Transferable and Not Found earn zero")}


def provisional_score_bounds(report: RankingReport, candidate: CandidateResult,
                             weights: ScoreWeights) -> dict[str, object]:
    """Project partial-credit bounds through the SAME allocation as leaderboard.

    Never derive a second, incompatible weighted formula. Missing rows are
    accounted for by weighted_candidate on an isolated in-memory snapshot.
    No persisted verdict, source evidence or score is changed by this view.
    """
    projected = weighted_candidate(report, candidate, weights)
    if projected["score"] is None:
        return {"verified_floor": None, "possible_ceiling": None,
                "unverified_requirements": len(projected.get("unverified_ids", [])),
                "provisional": True, "reason": projected["reason"]}
    return {"verified_floor": projected["score"],
            "possible_ceiling": projected["possible_ceiling"],
            "unverified_requirements": len(projected["unverified_ids"]),
            "provisional": bool(projected["provisional"]),
            "reason": ("Only verified Found credit contributes to the floor; "
                       "unresolved frozen criteria contribute to the ceiling "
                       "using exactly the leaderboard's approved weighting.")}


def weighted_leaderboard(report: RankingReport, weights: ScoreWeights) -> list[dict[str, object]]:
    rows = []
    for index, candidate in enumerate(report.candidates):
        scored = weighted_candidate(report, candidate, weights)
        grouped = criterion_bucket_counts(report, candidate)
        # Derive weighted-score completeness from the canonical per-JD rows,
        # not a possibly absent/stale primary-score display projection. A
        # fully examined negative remains a verified zero, even if no prior
        # unweighted display score was populated in a saved report.
        provisional = bool(scored.get("provisional", False) or scored.get("score") is None)
        # Never rank a provisional lower bound; retain that number separately.
        official_score = scored["score"] if not provisional else None
        rows.append({"candidate_index": index, "candidate": candidate.candidate_name,
                     "weighted_score": official_score,
                     "verified_floor": scored["score"] if provisional else None,
                     "provisional": provisional,
                     "score_status": ("Unavailable" if scored["score"] is None else
                                       "Unavailable · incomplete" if provisional else "Verified"),
                     "unverified_count": len(scored.get("unverified_ids", [])),
                     "jd_overall": f"{grouped['jd_required']['found'] + grouped['jd_preferred']['found']}/"
                                   f"{grouped['jd_required']['total'] + grouped['jd_preferred']['total']}",
                     "required": f"{grouped['jd_required']['found']}/{grouped['jd_required']['total']}",
                     "preferred": f"{grouped['jd_preferred']['found']}/{grouped['jd_preferred']['total']}",
                     "experience": f"{grouped['experience']['found']}/{grouped['experience']['total']}",
                     "education": f"{grouped['education']['found']}/{grouped['education']['total']}",
                     "review": ("Unavailable · incomplete coverage" if scored["score"] is None else
                                f"Incomplete · {len(scored['unverified_ids'])} pending/failed"
                                if scored.get("provisional") else "Review evidence"),
                     "breakdown": scored})
    rows.sort(key=lambda row: (
        row["weighted_score"] is None, -(row["weighted_score"] or 0),
        row["provisional"],
        row["candidate"].casefold(),
        report.candidates[int(row["candidate_index"])].candidate_source.casefold()))
    last_key = None
    last_rank = 0
    for position, row in enumerate(rows, 1):
        if row["weighted_score"] is None:
            row["rank"] = None
            continue
        # Within the weighted leaderboard, equal pooled scores are genuine
        # ties: Preferred coverage must not reintroduce hidden extra weight.
        key = (row["weighted_score"], row["provisional"])
        if key != last_key:
            last_rank = position
            last_key = key
        row["rank"] = last_rank
    return rows

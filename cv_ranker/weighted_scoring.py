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

    def __post_init__(self) -> None:
        for name in ("experience", "education", "jd", "required_share"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                raise ValueError(f"{name} must be an integer from 0 to 100")
        if not isinstance(self.split_jd, bool):
            raise ValueError("split_jd must be a Boolean")
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
                "jd_allocation": "pooled",
                "jd_required_share": None,
                "jd_preferred_share": None,
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


def _earned(item: RequirementAssessment) -> bool:
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
    if not isinstance(new_share, (int, float)) or isinstance(new_share, bool) or not isfinite(new_share):
        raise ValueError("New share must be a finite number")
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
    """Return a 0–100 result; `None` signals incomplete/invalid scoring.

    Category weights are renormalized across present buckets only. JD always
    has exactly one scoring denominator: all Required + Preferred criteria,
    excluding separately weighted Experience and Education. The split option
    changes presentation only, never the points per JD requirement.
    Missing candidate evidence in a present bucket counts as zero.
    """
    if candidate.primary_score is None or any(
            a.assessment_state == "unverified" for a in candidate.assessments):
        return {"score": None, "components": {}, "effective_weights": {},
                "reason": "Assessment incomplete; weighted rank withheld"}
    requirements = {r.requirement_id: r for r in report.requirements}
    assessments = {a.requirement_id: a for a in candidate.assessments}
    if len(assessments) != len(candidate.assessments) or set(requirements) != set(assessments):
        return {"score": None, "components": {}, "effective_weights": {},
                "reason": "Incomplete frozen JD coverage; weighted rank withheld"}
    counts = criterion_bucket_counts(report, candidate)
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

    jd_total = counts["jd_required"]["total"] + counts["jd_preferred"]["total"]
    jd_found = counts["jd_required"]["found"] + counts["jd_preferred"]["found"]
    effective: dict[str, float] = {}
    for key in ("experience", "education"):
        effective[key] = 100.0 * raw[key] / active if enabled[key] else 0.0
    effective["jd"] = 100.0 * weights.jd / active if jd_exists else 0.0
    contributions = []
    score = 0.0
    for requirement in report.requirements:
        key = allocation_bucket(requirement)
        item = assessments[requirement.requirement_id]
        possible = effective[key] * shares[requirement.requirement_id] / 100
        earned = possible if _earned(item) else 0.0
        score += earned
        contributions.append({
            "requirement_id": requirement.requirement_id,
            "requirement": requirement.name,
            "priority": requirement.priority,
            "category": key,
            "share_of_category": shares[requirement.requirement_id],
            "possible_points": round(possible, 6),
            "earned_points": round(earned, 6),
            "found": bool(_earned(item)),
        })
    return {"score": round(score, 2), "components": counts,
            "jd_combined": {"found": jd_found, "total": jd_total},
            "effective_weights": {k: round(v, 4) for k, v in effective.items()},
            "requirement_contributions": contributions,
            "reason": "Verified Found only; Transferable and Not Found earn zero"}


def weighted_leaderboard(report: RankingReport, weights: ScoreWeights) -> list[dict[str, object]]:
    rows = []
    for index, candidate in enumerate(report.candidates):
        scored = weighted_candidate(report, candidate, weights)
        grouped = criterion_bucket_counts(report, candidate)
        rows.append({"candidate_index": index, "candidate": candidate.candidate_name,
                     "weighted_score": scored["score"],
                     "jd_overall": f"{grouped['jd_required']['found'] + grouped['jd_preferred']['found']}/"
                                   f"{grouped['jd_required']['total'] + grouped['jd_preferred']['total']}",
                     "required": f"{grouped['jd_required']['found']}/{grouped['jd_required']['total']}",
                     "preferred": f"{grouped['jd_preferred']['found']}/{grouped['jd_preferred']['total']}",
                     "experience": f"{grouped['experience']['found']}/{grouped['experience']['total']}",
                     "education": f"{grouped['education']['found']}/{grouped['education']['total']}",
                     "review": "Unverified" if scored["score"] is None else "Review evidence",
                     "breakdown": scored})
    rows.sort(key=lambda row: (
        row["weighted_score"] is None, -(row["weighted_score"] or 0),
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
        key = row["weighted_score"]
        if key != last_key:
            last_rank = position
            last_key = key
        row["rank"] = last_rank
    return rows

import json
from pathlib import Path

from .schemas import RankingReport


def write_json(report: RankingReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_report(report: RankingReport, details: bool = False) -> None:
    print("=" * 72)
    print("                 EXPLAINABLE CV RANKING ENGINE")
    print("=" * 72)
    print(f"JD: {report.job_description_source}")
    print(f"JD validation mode: {report.jd_validation_mode}")
    print(f"Frozen requirements: {len(report.requirements)}")
    if report.warnings:
        print("System warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
    print()

    print("REQUIREMENTS")
    print("-" * 72)
    for item in report.requirements:
        print(f"[{item.requirement_id}] {item.priority.upper():9} {item.name}"
              f" | type={item.constraint.kind}"
              f" | JD lines={item.constraint.source_line_numbers}"
              f" | review={'yes' if item.constraint.requires_review else 'no'}")
    print()

    print("RANKING")
    print("-" * 72)
    print(f"{'Rank':<6}{'Candidate':<34}{'Primary':>12}{'Mode':>18}")
    for candidate in report.candidates:
        rank = str(candidate.rank) if candidate.rank is not None else "-"
        score = (
            f"{candidate.primary_score:.2f}%"
            if candidate.primary_score is not None
            else "FAILED"
        )
        print(
            f"{rank:<6}{candidate.candidate_name:<34}{score:>12}"
            f"{candidate.evaluation_mode:>18}"
        )
    print()

    if not details:
        return

    req_by_id = {item.requirement_id: item for item in report.requirements}
    for candidate in report.candidates:
        print("=" * 72)
        print(
            f"{candidate.candidate_name} | rank={candidate.rank} | "
            f"score={candidate.primary_score}"
        )
        print(f"Score basis: {candidate.score_basis}")
        print(f"HR eligibility criteria: {candidate.eligibility.status}")
        if candidate.eligibility.gated_requirement_ids:
            print(f"Gated IDs: {candidate.eligibility.gated_requirement_ids}")
        for issue in candidate.eligibility.issues:
            print(f"  - {issue}")
        if candidate.required_score is not None:
            print(
                f"Required coverage: {candidate.matched_required}/{candidate.total_required} "
                f"({candidate.required_score:.2f}%)"
            )
        if candidate.preferred_score is not None:
            print(
                f"Preferred coverage (reported separately): "
                f"{candidate.matched_preferred}/{candidate.total_preferred} "
                f"({candidate.preferred_score:.2f}%)"
            )
        if candidate.unknown_score is not None:
            print(
                f"Unknown-priority coverage: {candidate.matched_unknown}/{candidate.total_unknown} "
                f"({candidate.unknown_score:.2f}%)"
            )
        if candidate.errors:
            print("Warnings:")
            for error in candidate.errors:
                print(f"  - {error}")
        print()

        for assessment in candidate.assessments:
            req = req_by_id.get(assessment.requirement_id)
            name = req.name if req else assessment.requirement_id
            priority = req.priority if req else "unknown"
            symbol = {
                "matched": "✓",
                "uncertain": "?",
                "not_matched": "✗",
            }[assessment.status]
            print(f"{symbol} [{priority}] {name}: {assessment.status}")
            if assessment.compound_check:
                check = assessment.compound_check
                print(f"    Compound verification: {check.operator}/{check.outcome}: {check.explanation}")
                for component in check.components:
                    ids = [e.segment_id for e in component.evidence]
                    print(f"      {component.name}: {component.status} | source IDs={ids} | {component.reason}")
            if assessment.experience_check:
                check = assessment.experience_check
                print(f"    Experience verification: {check.outcome}; JD minimum={check.minimum_years}y")
                print(f"    Basis: {check.explanation}")
                for claim in check.claims:
                    print(f"      {claim.segment_id}: {claim.lower_years}-{claim.upper_years}y "
                          f"[{claim.scope}, {claim.tone}] {claim.quote}")
            if assessment.qualification_check:
                check = assessment.qualification_check
                print(f"    Qualification verification: {check.kind}/{check.outcome}; external authenticity not checked")
                print(f"    Basis: {check.explanation}")
                for claim in check.claims:
                    print(f"      {claim.segment_id}: [{claim.state}] {claim.quote}")
            if assessment.evidence:
                print(f"    Resume evidence: {assessment.evidence}")
            if assessment.matched_term:
                print(f"    Matched term: {assessment.matched_term}")

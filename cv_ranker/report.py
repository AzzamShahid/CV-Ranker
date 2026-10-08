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
        print(f"[{item.requirement_id}] {item.priority.upper():9} {item.name}")
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
            if assessment.evidence:
                print(f"    Resume evidence: {assessment.evidence}")
            if assessment.matched_term:
                print(f"    Matched term: {assessment.matched_term}")

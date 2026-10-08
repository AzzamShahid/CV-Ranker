from cv_ranker.schemas import RequirementAssessment, ValidatedRequirement
from cv_ranker.scoring import assign_ranks, score_candidate


def requirement(i: int, name: str, priority: str = "required") -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id=f"R{i:03d}",
        name=name,
        priority=priority,
        jd_evidence=name,
    )


def assessment(i: int, status: str, evidence: str | None = None) -> RequirementAssessment:
    return RequirementAssessment(
        requirement_id=f"R{i:03d}",
        status=status,
        evidence=evidence,
    )


def test_required_score_is_deterministic_and_preferred_is_separate():
    requirements = [
        requirement(1, "Python"),
        requirement(2, "Docker"),
        requirement(3, "AWS", "preferred"),
    ]
    result = score_candidate(
        candidate_name="A.txt",
        requirements=requirements,
        assessments=[
            assessment(1, "matched", "Python"),
            assessment(2, "not_matched"),
            assessment(3, "matched", "AWS"),
        ],
        evaluation_mode="llm_assessed",
        errors=[],
    )
    assert result.primary_score == 50.0
    assert result.required_score == 50.0
    assert result.preferred_score == 100.0


def test_uncertain_gets_zero_credit():
    requirements = [requirement(1, "Python"), requirement(2, "Docker")]
    result = score_candidate(
        candidate_name="A.txt",
        requirements=requirements,
        assessments=[assessment(1, "matched", "Python"), assessment(2, "uncertain", "Learning Docker")],
        evaluation_mode="llm_assessed",
        errors=[],
    )
    assert result.primary_score == 50.0
    assert result.matched_primary == 1


def test_preferred_only_jd_still_has_primary_score():
    requirements = [requirement(1, "AWS", "preferred")]
    result = score_candidate(
        candidate_name="A.txt",
        requirements=requirements,
        assessments=[assessment(1, "matched", "AWS")],
        evaluation_mode="llm_assessed",
        errors=[],
    )
    assert result.primary_score == 100.0
    assert result.required_score is None
    assert result.preferred_score == 100.0
    assert "preferred-only" in result.score_basis


def test_ranking_is_deterministic_on_ties():
    requirements = [requirement(1, "Python")]
    a = score_candidate(
        candidate_name="B.txt",
        requirements=requirements,
        assessments=[assessment(1, "matched", "Python")],
        evaluation_mode="llm_assessed",
        errors=[],
    )
    b = score_candidate(
        candidate_name="A.txt",
        requirements=requirements,
        assessments=[assessment(1, "matched", "Python")],
        evaluation_mode="llm_assessed",
        errors=[],
    )
    ranked = assign_ranks([a, b])
    assert [item.candidate_name for item in ranked] == ["A.txt", "B.txt"]

from cv_ranker.fallback import fallback_assessment, fallback_requirements
from cv_ranker.schemas import ValidatedRequirement


def req(name: str) -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id="R001",
        name=name,
        priority="required",
        jd_evidence=name,
    )


def test_fallback_exact_positive():
    result = fallback_assessment(req("Python"), "Built APIs using Python.")
    assert result.status == "matched"


def test_fallback_negation_is_not_match():
    result = fallback_assessment(req("Redis"), "No professional experience with Redis.")
    assert result.status == "not_matched"


def test_fallback_learning_is_uncertain():
    result = fallback_assessment(req("Kubernetes"), "Currently learning Kubernetes.")
    assert result.status == "uncertain"


def test_structural_requirement_fallback():
    jd = """Required Skills:\nPython\nDocker\n\nPreferred Skills:\nAWS\n"""
    result = fallback_requirements(jd, [], 20)
    assert [(r.name, r.priority) for r in result] == [
        ("Python", "required"),
        ("Docker", "required"),
        ("AWS", "preferred"),
    ]

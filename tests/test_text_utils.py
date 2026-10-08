from cv_ranker.text_utils import (
    classify_evidence_tone,
    classify_requirement_tone,
    evidence_exists,
    phrase_present,
)


def test_evidence_normalizes_whitespace_and_hyphen_linebreak():
    source = "Project manage-\nment and payroll processing"
    assert evidence_exists("Project management and payroll processing", source)


def test_negation_detection():
    assert classify_evidence_tone("No professional experience with Redis.") == "negated"


def test_have_not_used_detection():
    assert classify_requirement_tone("I have not used Docker.", "Docker") == "negated"


def test_never_worked_on_detection():
    assert classify_requirement_tone("Never worked on Docker projects.", "Docker") == "negated"


def test_colon_none_detection():
    assert classify_requirement_tone("Docker: none", "Docker") == "negated"


def test_uncertainty_detection():
    assert classify_evidence_tone("Currently learning Kubernetes through personal practice.") == "uncertain"


def test_phrase_matching_handles_pdf_hyphen_linebreak():
    assert phrase_present("Project management", "Project manage-\nment experience")

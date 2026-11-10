"""Non-scoring quality checks for real-world Phase 7G misclassifications."""
from cv_ranker.semantic.relationship_consistency import relationship_consistency_flags


def inspect(req, rel, passages, cap=None):
    original = {f"S{i:03d}": (text, section) for i, (text, section) in enumerate(passages, 1)}
    cites = [(sid, text) for sid, (text, section) in original.items()]
    return relationship_consistency_flags(
        requirement_name=req, capability_description=cap or req,
        relationship=rel, citations=cites, original_sources=original,
    )


def test_actual_python_work_labeled_transferable_is_flagged_not_upgraded():
    assert inspect("Python", "transferable", [("Built REST services with Python.", "experience")]) == [
        "possible_direct_mislabeled_transferable"]


def test_actual_postgres_work_labeled_transferable_is_flagged():
    assert inspect("PostgreSQL", "transferable", [("Maintained PostgreSQL databases.", "experience")]) == [
        "possible_direct_mislabeled_transferable"]


def test_only_skill_listing_cannot_prove_transferability():
    assert inspect("FastAPI", "transferable", [("FastAPI", "skills")]) == [
        "transferable_label_based_only_on_skills_listing"]


def test_direct_skill_listing_is_separately_flagged_as_evidence_depth():
    assert inspect("Node.js", "direct", [("Node.js", "skills")]) == [
        "direct_claim_supported_only_by_skills_listing"]


def test_unseen_different_technology_is_not_auto_labeled_direct():
    assert inspect("FastAPI", "transferable", [("Developed APIs in Flask.", "experience")]) == []


def test_composite_capability_not_equated_with_frozen_parent():
    assert inspect("Build APIs with validation", "transferable",
                   [("Built APIs with a different stack.", "experience")], cap="API development") == []


def test_literal_match_is_token_bounded_and_case_insensitive():
    assert inspect("Git", "transferable", [("Worked on GitHub repositories.", "experience")]) == []
    assert inspect("Git", "transferable", [("Used GIT for version control.", "experience")]) == [
        "possible_direct_mislabeled_transferable"]


def test_negative_labels_not_misreported_as_positive():
    assert inspect("Redis", "not_evidenced", [("No experience with Redis.", "experience")]) == []
    assert inspect("Kubernetes", "related_only", [("Learning Kubernetes.", "experience")]) == []


def test_missing_citation_is_not_accepted_as_evidence():
    assert relationship_consistency_flags(requirement_name="Python", capability_description="Python",
        relationship="transferable", citations=[("S999", "Python")], original_sources={}) == []


def test_named_skill_with_different_tool_experience_is_not_confirmed_used():
    assert inspect("FastAPI", "transferable", [
        ("FastAPI", "skills"),
        ("Developed REST APIs using Django.", "experience"),
    ]) == ["named_skill_only_in_listing_other_citations_do_not_show_its_use"]

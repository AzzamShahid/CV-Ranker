"""Regression checks for real 603-test live-run review blind spots."""
from __future__ import annotations

import pytest

from cv_ranker.semantic.relationship_consistency import relationship_consistency_flags
from scripts.phase7g_relationship_audit import audit_reports


def flags(req, rel, passages, cites=()):
    original = {f"S{i:03d}": (text, section)
                for i, (text, section) in enumerate(passages, 1)}
    return relationship_consistency_flags(
        requirement_name=req, capability_description=req,
        relationship=rel, citations=list(cites),
        original_sources=original, retrieved_sources=original,
    )


@pytest.mark.parametrize("req,text", [
    ("Docker", "Containerized backend applications using Docker."),
    ("PostgreSQL", "Created and maintained PostgreSQL databases."),
    ("Python", "Developed REST APIs using Python."),
    ("PostgreSQL", "Maintained PostgreSQL databases."),
])
def test_live_nonpositive_work_missed_is_flagged(req, text):
    assert flags(req, "related_only", [(text, "experience")]) == [
        "possible_named_work_overlooked_by_nonpositive_label"
    ]


@pytest.mark.parametrize("req,text", [
    ("Redis", "No professional experience with Redis."),
    ("Django", "Currently learning Django."),
    ("Kubernetes", "Interested in learning Kubernetes."),
    ("Docker", "Basic exposure to Docker through a university project."),
    ("Python", "Without having used Python, I studied tutorials."),
])
def test_negation_learning_exposure_are_not_automatic_work_flags(req, text):
    assert flags(req, "related_only", [(text, "experience")]) == []


def test_named_skill_only_in_listing_with_different_project_is_flagged():
    passages = [("FastAPI", "skills"),
                ("Developed REST APIs using Python and Django.", "experience")]
    assert flags("FastAPI", "direct", passages, cites=[("S001", "FastAPI"),
        ("S002", "Developed REST APIs using Python and Django.")]) == [
            "direct_named_skill_only_in_listing_other_work_does_not_show_its_use"
        ]


def test_named_skill_listing_not_evidenced_requires_review_not_automatic_credit():
    assert flags("Node.js", "not_evidenced", [("Node.js", "skills")]) == [
        "named_skill_listing_present_but_reported_not_evidenced"
    ]


def test_other_requirement_and_github_substring_do_not_pass():
    assert flags("Git", "related_only", [("Maintained GitHub repositories.", "experience")]) == []
    assert relationship_consistency_flags(
        requirement_name="Docker", capability_description="Build CI/CD",
        relationship="related_only", citations=[], original_sources={"S1": ("Used Docker.", "experience")},
        retrieved_sources={"S1": ("Used Docker.", "experience")},
    ) == []


def test_modified_retrieval_text_cannot_be_considered_grounded():
    assert relationship_consistency_flags(
        requirement_name="Docker", capability_description="Docker",
        relationship="related_only", citations=[],
        original_sources={"S1": ("No Docker experience.", "experience")},
        retrieved_sources={"S1": ("Used Docker to build containers.", "experience")},
    ) == []


def test_uncited_related_only_is_checked_in_audit_reports():
    retrieval = {"schema_version": 2, "scoring_unchanged": True,
        "requirements": [{"requirement_id": "R1", "name": "PostgreSQL"}],
        "capability_search_plan": {"capabilities": [{"capability_id": "R1-C01",
            "parent_requirement_id": "R1", "description": "PostgreSQL"}]},
        "candidates": [{"candidate_id": "test-id", "candidate_name": "test.txt",
            "direct_primary_score": 25.0, "ranking_position": 1,
            "hits_by_requirement": {"R1": [{"segment_id": "S1", "section": "experience",
                "original_text": "Created and maintained PostgreSQL databases."}]}}]}
    transferability = {"mode": "qwen_transferability_shadow_not_scoring",
        "scoring_unchanged": True, "candidates": [{"candidate_id": "test-id",
            "candidate_name": "test.txt", "original_primary_score": 25.0,
            "original_rank": 1, "status": "completed_provisional", "assessments": [{
                "requirement_id": "R1", "capability_id": "R1-C01",
                "relationship": "related_only", "citation_audit": "not_cited", "citations": []}]}]}
    output = audit_reports(transferability, retrieval)
    assert output["flag_count"] == 1
    assert output["candidates"][0]["flagged_proposals"][0]["requirement_id"] == "R1"
    assert output["ranking_unchanged"] is True
    assert output["independent_semantic_verification"] is False

"""Not Found retains explainable CV checkpoints without creating credit."""

from cv_ranker.schemas import (EvidenceCitation, RequirementAssessment,
                               RequirementConstraint, ValidatedRequirement)
from cv_ranker.segments import ResumeSegment
from cv_ranker.unified import _retain_negative_review_checkpoints


def requirement(name, *, jd=None):
    return ValidatedRequirement(
        requirement_id="R001", name=name, jd_evidence=jd or name,
        priority="preferred", constraint=RequirementConstraint(
            kind="skill", operator="single", origin="source_rules"))


def missing():
    return RequirementAssessment(
        requirement_id="R001", status="not_matched",
        unified_status="Not Found", reason="No accepted evidence for the JD.")


def test_not_found_keeps_an_explicit_original_denial_for_reviewer():
    source = ResumeSegment("S014", "skills", "Never used Cloud Run.")
    audited = _retain_negative_review_checkpoints(
        requirement("Cloud Run"), missing(), {"S014": source}, ["S014"])
    assert audited.unified_status == "Not Found"
    assert audited.status == "not_matched"
    assert audited.evidence_ids == ["S014"]
    assert audited.evidence_segments[0].text == source.text
    assert audited.reason == "No accepted evidence for the JD."
    assert audited.review_checkpoint_origin == "retrieval"


def test_not_found_keeps_a_retrieved_related_passage_when_model_returns_empty():
    source = ResumeSegment("S028", "projects", "Built an independently completed workflow.")
    audited = _retain_negative_review_checkpoints(
        requirement("Inventory management"), missing(), {"S028": source}, ["S028"])
    assert audited.status == "not_matched"
    assert audited.evidence_ids == ["S028"]
    assert audited.evidence_segments[0].section == "projects"
    assert audited.reason == "No accepted evidence for the JD."
    assert audited.review_checkpoint_origin == "retrieval"


def test_copied_jd_or_non_candidate_source_never_appears_as_reviewed_evidence():
    copied = ResumeSegment("S010", "non_candidate", "Cloud Run")
    audited = _retain_negative_review_checkpoints(
        requirement("Cloud Run"), missing(), {"S010": copied}, ["S010"])
    assert audited.evidence_ids == []
    assert audited.evidence_segments == []


def test_actual_model_citation_is_retained_without_replacing_its_reason():
    source = ResumeSegment("S010", "skills", "Not familiar with Cloud Run")
    cited = missing().model_copy(update={
        "evidence_ids": ["S010"],
        "evidence_segments": [EvidenceCitation(
            segment_id="S010", section="skills", text=source.text)],
    })
    assert _retain_negative_review_checkpoints(
        requirement("Cloud Run"), cited, {"S010": source}, ["S010"]) == cited


def test_explicit_professional_requirement_does_not_get_skills_list_credit():
    source = ResumeSegment("S010", "skills", "Google Cloud")
    audited = _retain_negative_review_checkpoints(
        requirement("Google Cloud", jd="Professional experience using Google Cloud"),
        missing(), {"S010": source}, ["S010"])
    assert audited.unified_status == "Not Found"
    assert audited.evidence_ids == ["S010"]
    assert audited.reason == "No accepted evidence for the JD."
    assert audited.review_checkpoint_origin == "retrieval"

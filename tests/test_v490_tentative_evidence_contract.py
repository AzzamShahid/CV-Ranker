"""A tentative CV claim is a valid non-scoring judgment, not a broken citation."""
from pathlib import Path

from cv_ranker.assessor import (_unanchored_semantic_tone, _validate_rows)
from cv_ranker.documents import extract_text
from cv_ranker.schemas import (LLMAssessmentItem, LLMCandidateAssessmentResponse,
                               ValidatedRequirement)
from cv_ranker.segments import ResumeSegment, segment_resume
from cv_ranker.text_utils import classify_requirement_tone


def requirement(name="Warehouse scheduling"):
    return ValidatedRequirement(requirement_id="R009", name=name,
                                priority="required", jd_evidence=name)


def check(status, text, section="education", name="Warehouse scheduling"):
    req = requirement(name)
    segment = ResumeSegment(segment_id="S001", section=section, text=text)
    model = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R009", status=status, evidence_ids=["S001"],
        reason="The cited candidate statement only demonstrates limited exposure.")])
    valid, invalid, notices, _ = _validate_rows(
        response=model, requirements=[req], resume_text=segment.text,
        segments=[segment])
    return valid, invalid, notices


def test_tutorials_and_exploration_do_not_generate_invalid_citation_retries():
    statements = [
        "Currently exploring shipping and warehouse scheduling tutorials, without completed projects.",
        "Exploring warehouse scheduling with practice exercises in spare time.",
        "Currently experimenting with a warehouse scheduling simulator in coursework.",
    ]
    for statement in statements:
        assert _unanchored_semantic_tone(statement) == "uncertain", statement
        assert classify_requirement_tone(statement, "Warehouse scheduling") == "uncertain", statement
        valid, invalid, notices = check("matched", statement)
        assert not invalid, notices
        assert valid["R009"].status == "uncertain"


def test_nonpositive_tentative_judgment_accepts_documented_exploration():
    # 'Uncertain' is not a scored match. A *genuine* limited-exposure claim
    # may occur in education rather than a completed-work section.
    valid, invalid, notices = check(
        "uncertain", "Currently exploring warehouse scheduling tutorials after class.")
    assert not invalid, notices
    assert valid["R009"].status == "uncertain"


def test_unrelated_degree_label_cannot_be_promoted_to_direct_capability():
    _, invalid, notices = check(
        "matched", "Bachelor of Arts in Studio Photography, awarded 2024.")
    assert invalid == {"R009"}
    assert any("no qualifying capability" in notice for notice in notices)


def test_actual_sample_pdf_limited_exploration_is_reviewable_not_unverified():
    # This fixture is one negative control; no applicant or tool is hardcoded
    # in matching code. The same test above works for unrelated departments.
    pdf = (Path(__file__).resolve().parents[1] / "sample_data" /
           "applied_ai_documents" / "pdf" / "09_amal_cloud_integrations.pdf")
    source = next(item for item in segment_resume(extract_text(pdf))
                  if "LangChain tutorials" in item.text)
    req = requirement("LangChain")
    response = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R009", status="matched", evidence_ids=[source.segment_id],
        reason="The applicant explicitly reports exploration in tutorials.")])
    valid, invalid, notices, _ = _validate_rows(
        response=response, requirements=[req], resume_text=source.text,
        segments=[source])
    assert not invalid, notices
    assert valid["R009"].status == "uncertain"
    assert valid["R009"].evidence_ids == [source.segment_id]


def test_explicit_performed_work_is_not_downgraded_as_learning_only():
    valid, invalid, notices = check(
        "matched", "Implemented warehouse scheduling for 60 delivery routes.",
        section="experience")
    assert not invalid, notices
    assert valid["R009"].status == "matched"


def test_separate_positive_skill_claim_is_not_erased_by_learning_more():
    req = requirement("Warehouse scheduling")
    segments = [
        ResumeSegment("S001", "skills", "Warehouse scheduling"),
        ResumeSegment("S002", "education", "Currently exploring warehouse scheduling tutorials"),
    ]
    model = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R009", status="matched", evidence_ids=["S001", "S002"],
        reason="The candidate independently lists the requested operational skill.")])
    valid, invalid, notices, _ = _validate_rows(
        response=model, requirements=[req], resume_text="\n".join(s.text for s in segments),
        segments=segments)
    assert not invalid, notices
    assert valid["R009"].status == "matched"


def test_positive_claim_and_explicit_denial_remain_uncertain():
    req = requirement("Warehouse scheduling")
    segments = [
        ResumeSegment("S001", "skills", "Warehouse scheduling"),
        ResumeSegment("S002", "experience", "Never used warehouse scheduling in practice."),
    ]
    model = LLMCandidateAssessmentResponse(assessments=[LLMAssessmentItem(
        requirement_id="R009", status="matched", evidence_ids=["S001", "S002"],
        reason="The resume contains a positive and a negative statement.")])
    valid, invalid, notices, _ = _validate_rows(
        response=model, requirements=[req], resume_text="\n".join(s.text for s in segments),
        segments=segments)
    assert not invalid, notices
    assert valid["R009"].status == "uncertain"

import pytest

from cv_ranker.assessor import assess_resume
from cv_ranker.config import Settings
from cv_ranker.fallback import fallback_assessment, structural_hints
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.schemas import (
    CandidateAssessmentResponse,
    JDRequirement,
    JDValidationResponse,
    RequirementAssessment,
    ValidatedRequirement,
    YakeCandidate,
)


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def invoke_structured(self, **kwargs):
        return self.response


def req(name: str, rid: str = "R001") -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id=rid,
        name=name,
        priority="required",
        jd_evidence=name,
    )


def test_empty_llm_result_uses_visible_structural_fallback_when_jd_is_explicit():
    jd = "Required Skills:\nPython\nDocker\n"
    response = JDValidationResponse(requirements=[])
    requirements, mode, warnings = validate_jd_requirements(
        jd_text=jd,
        candidates=[YakeCandidate(keyword="Python", score=0.01)],
        settings=Settings(),
        llm=FakeLLM(response),
    )
    assert mode == "fallback_structural_after_llm"
    assert [r.name for r in requirements] == ["Python", "Docker"]
    assert any("structural fallback" in warning for warning in warnings)


def test_structural_fallback_does_not_split_commas():
    jd = (
        "Required Qualifications:\n"
        "Bachelor's degree in Computer Science, IT, or related field\n"
    )
    hints = structural_hints(jd)
    assert len(hints) == 1
    assert hints[0].name == "Bachelor's degree in Computer Science, IT, or related field"


def test_real_but_unrelated_jd_evidence_is_rejected_then_structural_fallback_is_visible():
    jd = "We are a global company.\nRequired Skills:\nDocker\n"
    response = JDValidationResponse(
        requirements=[
            JDRequirement(
                name="Python",
                priority="required",
                evidence="We are a global company.",
            )
        ]
    )
    requirements, mode, warnings = validate_jd_requirements(
        jd_text=jd,
        candidates=[],
        settings=Settings(),
        llm=FakeLLM(response),
    )
    assert mode == "fallback_structural_after_llm"
    assert [r.name for r in requirements] == ["Docker"]
    assert warnings


def test_structural_priority_can_correct_same_llm_requirement_only():
    jd = "Required Skills:\nPython\nDocker\n"
    response = JDValidationResponse(
        requirements=[JDRequirement(name="Python", priority="unknown", evidence="Python")]
    )
    requirements, mode, _ = validate_jd_requirements(
        jd_text=jd,
        candidates=[],
        settings=Settings(),
        llm=FakeLLM(response),
    )
    assert mode == "llm_validated"
    assert [item.name for item in requirements] == ["Python"]
    assert requirements[0].priority == "required"


def test_jd_ids_are_assigned_by_python_deterministically():
    jd = "Required Skills:\nPython\nDocker\n"
    response = JDValidationResponse(
        requirements=[
            JDRequirement(name="Python", priority="required", evidence="Python"),
            JDRequirement(name="Docker", priority="required", evidence="Docker"),
        ]
    )
    requirements, _, _ = validate_jd_requirements(
        jd_text=jd,
        candidates=[],
        settings=Settings(),
        llm=FakeLLM(response),
    )
    assert [item.requirement_id for item in requirements] == ["R001", "R002"]


def test_max_requirement_cap_prioritizes_required():
    jd = "Preferred Skills:\nAWS\nRequired Skills:\nPython\nDocker\n"
    response = JDValidationResponse(
        requirements=[
            JDRequirement(name="AWS", priority="preferred", evidence="AWS"),
            JDRequirement(name="Python", priority="required", evidence="Python"),
            JDRequirement(name="Docker", priority="required", evidence="Docker"),
        ]
    )
    requirements, _, _ = validate_jd_requirements(
        jd_text=jd,
        candidates=[],
        settings=Settings(max_requirements=2),
        llm=FakeLLM(response),
    )
    assert [item.name for item in requirements] == ["Python", "Docker"]


def test_fallback_does_not_match_java_inside_javascript():
    assert fallback_assessment(req("Java"), "Experienced with JavaScript.").status == "not_matched"


def test_fallback_does_not_match_sql_inside_nosql():
    assert fallback_assessment(req("SQL"), "Worked with NoSQL databases.").status == "not_matched"


def test_fallback_does_not_match_c_inside_cpp_or_csharp():
    assert fallback_assessment(req("C"), "Experienced in C++ development.").status == "not_matched"
    assert fallback_assessment(req("C"), "Experienced in C# development.").status == "not_matched"


def test_short_go_in_ordinary_prose_is_not_match():
    assert fallback_assessment(req("Go"), "I go to client sites weekly.").status == "not_matched"


def test_short_go_with_programming_context_is_match():
    assert fallback_assessment(req("Go"), "Experienced with Go programming language.").status == "matched"


def test_negation_i_have_not_used_is_not_match():
    result = fallback_assessment(req("Docker"), "I have not used Docker in production.")
    assert result.status == "not_matched"


def test_negation_never_worked_on_is_not_match():
    result = fallback_assessment(req("Docker"), "Never worked on Docker projects.")
    assert result.status == "not_matched"


def test_negation_colon_none_is_not_match():
    result = fallback_assessment(req("Docker"), "Docker: none")
    assert result.status == "not_matched"


def test_unrelated_negation_does_not_downgrade_positive_python():
    result = fallback_assessment(req("Python"), "Python expert; no experience with Redis.")
    assert result.status == "matched"


def test_structural_section_stops_before_responsibilities():
    jd = "Required Skills:\nPython\nDocker\nResponsibilities\nBuild APIs\n"
    assert [(x.name, x.priority) for x in structural_hints(jd)] == [
        ("Python", "required"),
        ("Docker", "required"),
    ]


def test_structural_parser_preserves_numeric_requirement():
    jd = "Required Skills:\n5+ years of backend experience\n"
    assert structural_hints(jd)[0].name == "5+ years of backend experience"


def test_structural_parser_preserves_dotnet():
    jd = "Required Skills:\n.NET\n"
    assert structural_hints(jd)[0].name == ".NET"


def test_settings_accepts_larger_ui_ranges():
    settings = Settings(yake_top_k=200, max_requirements=100)
    assert settings.yake_top_k == 200
    assert settings.max_requirements == 100


def test_settings_rejects_invalid_yake_count():
    with pytest.raises(ValueError):
        Settings(yake_top_k=0)


def test_assessor_does_not_need_requirement_name_in_output_schema():
    response = CandidateAssessmentResponse(
        assessments=[
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence="Built APIs using Python.",
            )
        ]
    )
    items, mode, _ = assess_resume(
        resume_text="Built APIs using Python.",
        requirements=[req("Python")],
        llm=FakeLLM(response),
    )
    assert mode == "llm_assessed"
    assert items[0].status == "matched"

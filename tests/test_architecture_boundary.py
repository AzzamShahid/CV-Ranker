from pathlib import Path

import pytest

from cv_ranker.assessor import assess_resume
from cv_ranker.config import Settings
from cv_ranker.documents import extract_text
from cv_ranker.fallback import fallback_requirements, structural_hints
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.schemas import (
    JDRequirement,
    JDValidationResponse,
    LLMAssessmentItem,
    LLMCandidateAssessmentResponse,
    ValidatedRequirement,
    YakeCandidate,
)
from cv_ranker.segments import segment_resume


def req(name: str, rid: str = "R001", priority: str = "required") -> ValidatedRequirement:
    return ValidatedRequirement(requirement_id=rid, name=name, priority=priority, jd_evidence=name)


class OneShotLLM:
    def __init__(self, response):
        self.response = response
        self.settings = Settings(assessment_batch_size=20)
        self.calls = 0

    def invoke_structured(self, **kwargs):
        self.calls += 1
        return self.response


class JDLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def invoke_structured(self, **kwargs):
        self.calls += 1
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def test_qwen_semantic_paraphrase_is_not_reproved_lexically_by_python():
    resume = "Projects:\nBuilt a source-first AI pipeline that converts user intake into structured facts and ranks support pathways.\n"
    seg = segment_resume(resume)[0]
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(
            requirement_id="R001",
            status="matched",
            evidence_ids=[seg.segment_id],
            matched_term="source-first AI pipeline",
        )
    ])
    out, mode, warnings = assess_resume(
        resume_text=resume,
        requirements=[req("AI application development")],
        llm=OneShotLLM(response),
    )
    assert mode == "llm_assessed"
    assert out[0].status == "matched"
    assert out[0].matched_term == "source-first AI pipeline"
    assert out[0].evidence_ids == [seg.segment_id]
    assert not warnings


def test_direct_guard_does_not_award_skill_from_job_title_only():
    resume = "Experience:\nMachine Learning Engineer\n"
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="not_matched", evidence_ids=[])
    ])
    out, mode, _ = assess_resume(
        resume_text=resume,
        requirements=[req("Machine Learning")],
        llm=OneShotLLM(response),
    )
    assert out[0].status == "not_matched"
    assert mode == "llm_assessed"


def test_direct_guard_does_not_award_skill_from_degree_only():
    resume = "Education:\nBachelor of Science in Machine Learning\n"
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="not_matched", evidence_ids=[])
    ])
    out, _, _ = assess_resume(
        resume_text=resume,
        requirements=[req("Machine Learning")],
        llm=OneShotLLM(response),
    )
    assert out[0].status == "not_matched"


def test_all_caps_skills_are_evidence_not_headings():
    segs = segment_resume("SKILLS:\nAWS\nGCP\nNLP\nPYTHON\nDocker\n")
    joined = " ".join(s.text for s in segs)
    assert all(token in joined for token in ["AWS", "GCP", "NLP", "PYTHON", "Docker"])
    assert all(s.section == "skills" for s in segs)


def test_yake_never_becomes_final_requirement_engine():
    jd = "We are hiring a backend engineer to build internal business applications. Great culture and flexible hours."
    yake = [
        YakeCandidate(keyword="backend engineer", score=0.01),
        YakeCandidate(keyword="flexible hours", score=0.02),
    ]
    assert fallback_requirements(jd, yake, 30) == []


def test_arbitrary_jd_semantic_rename_is_frozen_to_source_wording():
    llm = JDLLM(JDValidationResponse(requirements=[
        JDRequirement(name="Kubernetes", priority="required", evidence="Python")
    ]))
    requirements, mode, warnings = validate_jd_requirements(
        jd_text="Required Skills:\nPython\n",
        candidates=[],
        settings=Settings(),
        llm=llm,
    )
    assert mode == "llm_validated"
    assert [r.name for r in requirements] == ["Python"]
    assert requirements[0].jd_evidence == "Python"
    assert not warnings


def test_rest_api_plural_duplicate_has_one_denominator_item():
    llm = JDLLM(JDValidationResponse(requirements=[
        JDRequirement(name="REST API", priority="required", evidence="REST APIs"),
        JDRequirement(name="REST APIs", priority="required", evidence="REST APIs"),
    ]))
    requirements, _, _ = validate_jd_requirements(
        jd_text="Required Skills:\nREST APIs\n",
        candidates=[],
        settings=Settings(),
        llm=llm,
    )
    assert len(requirements) == 1
    assert requirements[0].name == "REST APIs"


@pytest.mark.parametrize("source", ["TensorFlow/PyTorch", "TensorFlow and/or PyTorch", "TensorFlow or PyTorch"])
def test_compact_or_forms_remain_one_requirement(source):
    llm = JDLLM(JDValidationResponse(requirements=[
        JDRequirement(name=source, priority="required", evidence=source)
    ]))
    requirements, _, _ = validate_jd_requirements(
        jd_text=f"Required Skills:\n{source}\n",
        candidates=[],
        settings=Settings(),
        llm=llm,
    )
    assert len(requirements) == 1
    assert requirements[0].name == "TensorFlow or PyTorch"


def test_structural_fallback_skips_obvious_benefit_and_action_lines():
    jd = "Required Skills:\nPython\nBuild internal APIs\nCompetitive salary\n"
    assert [h.name for h in structural_hints(jd)] == ["Python"]


def test_dynamic_batch_planner_shrinks_when_context_does_not_fit():
    class ContextLLM:
        def __init__(self):
            self.settings = Settings(assessment_batch_size=8)
            self.calls = []

        def prompt_fits(self, system_prompt, user_prompt):
            # Permit at most two requirement rows per call.
            count = sum(1 for line in user_prompt.splitlines() if line.startswith("R") and " | " in line)
            return count <= 2

        def invoke_structured(self, **kwargs):
            ids = [line.split(" | ", 1)[0] for line in kwargs["user_prompt"].splitlines() if line.startswith("R") and " | " in line]
            self.calls.append(ids)
            return LLMCandidateAssessmentResponse(assessments=[
                LLMAssessmentItem(requirement_id=rid, status="not_matched", evidence_ids=[])
                for rid in ids
            ])

    requirements = [req(f"Skill {i}", f"R{i:03d}") for i in range(1, 6)]
    llm = ContextLLM()
    out, mode, warnings = assess_resume(resume_text="Nothing relevant here.", requirements=requirements, llm=llm)
    assert [len(call) for call in llm.calls] == [2, 2, 1]
    assert len(out) == 5 and mode == "llm_assessed"
    assert any("context-planned" in w for w in warnings)


def test_docx_extraction_preserves_paragraph_table_paragraph_order(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "ordered.docx"
    doc = docx.Document()
    doc.add_paragraph("Summary first")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Skills"
    table.cell(0, 1).text = "Python"
    doc.add_paragraph("Experience last")
    doc.save(path)

    text = extract_text(path)
    assert text.index("Summary first") < text.index("Skills | Python") < text.index("Experience last")

from cv_ranker.assessor import assess_resume
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
from cv_ranker.segments import segment_resume


NAQVI_LIKE = """PROFESSIONAL SUMMARY
Computer Science graduate focused on applied AI/ML, LLM/NLP systems, medical AI, and full-stack AI products. Built
several systems. Experienced with Python, ML/DL, NLP, LLM integrations, medical
imaging, forecasting, and production-oriented AI workflows.
TECHNICAL SKILLS
Programming: Python, C++, Java, JavaScript/TypeScript, Dart
AI/ML: TensorFlow, PyTorch, Scikit-learn, Pandas, NumPy, CNNs, NLP, time-series forecasting, medical imaging, model
evaluation
LLM/AI Tools: Gemini API, LangChain, LangGraph, CrewAI
PROFESSIONAL EXPERIENCE
Machine Learning Intern (Advanced) | ARCH Technologies | May 2025 - July 2025
"""


def req(rid, name):
    return ValidatedRequirement(requirement_id=rid, name=name, priority="required", jd_evidence=name)


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.settings = type("S", (), {"assessment_batch_size": 20})()
    def invoke_structured(self, **kwargs):
        return self.response


def test_segments_merge_pdf_wrapped_skill_rows():
    segs = segment_resume(NAQVI_LIKE)
    texts = [s.text for s in segs]
    assert any("LLM integrations, medical imaging" in t for t in texts)
    assert any("TensorFlow, PyTorch" in t and "model evaluation" in t for t in texts)


def test_segment_ids_accept_short_obvious_evidence_without_quote_copying():
    segs = segment_resume(NAQVI_LIKE)
    python_id = next(s.segment_id for s in segs if s.text.startswith("Programming: Python"))
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="matched", evidence_ids=[python_id])
    ])
    out, mode, _ = assess_resume(resume_text=NAQVI_LIKE, requirements=[req("R001", "Python")], llm=FakeLLM(response))
    assert out[0].status == "matched"
    assert out[0].evidence.startswith("Programming: Python")
    assert mode == "llm_assessed"


def test_direct_source_guard_recovers_only_literal_or_explicit_or_evidence():
    requirements = [
        req("R001", "Python"),
        req("R002", "Machine Learning"),
        req("R003", "Deep Learning"),
        req("R004", "TensorFlow or PyTorch"),
        req("R005", "Natural Language Processing"),
        req("R006", "LLM integrations"),
        req("R007", "LangChain"),
        req("R008", "Model evaluation"),
        req("R009", "AI application development"),
    ]
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id=r.requirement_id, status="not_matched", evidence_ids=[])
        for r in requirements
    ])
    out, mode, warnings = assess_resume(resume_text=NAQVI_LIKE, requirements=requirements, llm=FakeLLM(response))
    statuses = {a.requirement_id: a.status for a in out}
    # Python has no semantic alias dictionary. ML/DL/NLP need Qwen semantic judgment.
    assert statuses["R001"] == "matched"
    assert statuses["R002"] == "not_matched"  # title-only "Machine Learning Intern" is not auto-credit
    assert statuses["R003"] == "not_matched"
    assert statuses["R004"] == "matched"
    assert statuses["R005"] == "not_matched"
    assert statuses["R006"] == "matched"
    assert statuses["R007"] == "matched"
    assert statuses["R008"] == "matched"
    assert statuses["R009"] == "not_matched"
    assert mode == "mixed"
    assert any("direct source guard corrected" in w for w in warnings)


def test_learning_direct_alias_is_not_upgraded_to_match():
    text = "Skills I am currently learning:\nKubernetes\n"
    response = LLMCandidateAssessmentResponse(assessments=[
        LLMAssessmentItem(requirement_id="R001", status="not_matched", evidence_ids=[])
    ])
    out, _, _ = assess_resume(resume_text=text, requirements=[req("R001", "Kubernetes")], llm=FakeLLM(response))
    assert out[0].status == "uncertain"

from cv_ranker.assessor import SYSTEM_PROMPT, assess_resume
from cv_ranker.llm import LLMError
from cv_ranker.schemas import (
    CandidateAssessmentResponse,
    LLMAssessmentItem,
    LLMCandidateAssessmentResponse,
    RequirementAssessment,
    ValidatedRequirement,
)


class QueueLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def invoke_structured(self, **kwargs):
        self.calls += 1
        if not self.responses:
            raise AssertionError("Unexpected extra LLM call")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def req(name: str, rid: str = "R001") -> ValidatedRequirement:
    return ValidatedRequirement(
        requirement_id=rid,
        name=name,
        priority="required",
        jd_evidence=name,
    )


def response(*items: RequirementAssessment) -> CandidateAssessmentResponse:
    return CandidateAssessmentResponse(assessments=list(items))


def test_semantic_match_is_qwen_owned_and_python_only_checks_cited_term():
    resume = "Experienced with Python, ML/DL, NLP, LLM integrations."
    llm = QueueLLM(
        LLMCandidateAssessmentResponse(assessments=[
            LLMAssessmentItem(
                requirement_id="R001",
                status="matched",
                evidence_ids=["S001"],
                matched_term="NLP",
            )
        ])
    )
    items, mode, warnings = assess_resume(
        resume_text=resume,
        requirements=[req("Natural Language Processing")],
        llm=llm,
    )
    assert mode == "llm_assessed"
    assert items[0].status == "matched"
    assert items[0].matched_term == "NLP"
    assert "NLP" in items[0].evidence
    assert not warnings


def test_missing_positive_evidence_gets_one_corrective_retry():
    llm = QueueLLM(
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence=None,
            )
        ),
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence="Built APIs using Python and FastAPI.",
            )
        ),
    )
    items, mode, warnings = assess_resume(
        resume_text="Built APIs using Python and FastAPI.",
        requirements=[req("Python")],
        llm=llm,
    )
    assert llm.calls == 2
    assert mode == "llm_assessed"
    assert items[0].status == "matched"
    assert items[0].evidence == "Built APIs using Python and FastAPI."
    assert any("corrective retry" in warning for warning in warnings)


def test_invalid_evidence_after_correction_receives_no_credit():
    llm = QueueLLM(
        response(RequirementAssessment(requirement_id="R001", status="matched", evidence=None)),
        response(RequirementAssessment(requirement_id="R001", status="matched", evidence=None)),
    )
    items, mode, warnings = assess_resume(
        resume_text="Candidate profile contains no Python evidence.",
        requirements=[req("Python")],
        llm=llm,
    )
    assert llm.calls == 2
    assert mode == "llm_assessed"
    assert items[0].status == "not_matched"
    assert items[0].evidence is None
    assert any("no credit awarded" in warning for warning in warnings)


def test_hallucinated_evidence_is_retried_and_not_trusted():
    llm = QueueLLM(
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence="Used Docker in production.",
            )
        ),
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="not_matched",
                evidence=None,
            )
        ),
    )
    items, _, _ = assess_resume(
        resume_text="Used Git for source control.",
        requirements=[req("Docker")],
        llm=llm,
    )
    assert items[0].status == "not_matched"


def test_learning_context_cannot_remain_matched():
    text = "Currently learning Kubernetes through personal projects."
    llm = QueueLLM(
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence=text,
            )
        )
    )
    items, _, _ = assess_resume(
        resume_text=text,
        requirements=[req("Kubernetes")],
        llm=llm,
    )
    assert items[0].status == "uncertain"


def test_negated_context_cannot_remain_matched():
    text = "I have not used Docker in a professional project."
    llm = QueueLLM(
        response(
            RequirementAssessment(
                requirement_id="R001",
                status="matched",
                evidence=text,
            )
        )
    )
    items, _, _ = assess_resume(
        resume_text=text,
        requirements=[req("Docker")],
        llm=llm,
    )
    assert items[0].status == "not_matched"


def test_main_llm_failure_uses_conservative_technical_fallback():
    llm = QueueLLM(LLMError("timeout"))
    items, mode, warnings = assess_resume(
        resume_text="Built services using Python.",
        requirements=[req("Python")],
        llm=llm,
    )
    assert mode == "fallback_exact"
    assert items[0].status == "matched"
    assert warnings


def test_duplicate_id_is_retried_not_silently_accepted():
    llm = QueueLLM(
        response(
            RequirementAssessment(requirement_id="R001", status="matched", evidence="Python"),
            RequirementAssessment(requirement_id="R001", status="matched", evidence="Python"),
        ),
        response(
            RequirementAssessment(requirement_id="R001", status="matched", evidence="Python"),
        ),
    )
    items, _, warnings = assess_resume(
        resume_text="Python",
        requirements=[req("Python")],
        llm=llm,
    )
    assert items[0].status == "matched"
    assert any("corrective retry" in warning for warning in warnings)


def test_prompt_explicitly_rejects_transferable_technology_credit():
    # The runtime policy is domain-independent, not a list of pairs chosen for
    # one synthetic benchmark. Semantic abbreviations still belong to Qwen.
    assert "DIFFERENT item" in SYSTEM_PROMPT
    assert "Do not give transferable credit" in SYSTEM_PROMPT
    assert "abbreviations" in SYSTEM_PROMPT


def test_prompt_forbids_llm_scoring():
    assert "Do not calculate scores" in SYSTEM_PROMPT

"""Focused retry regression tests: model owns every acronym equivalence decision."""
from cv_ranker.assessor import assess_resume, _has_orthographic_acronym_lead
from cv_ranker.config import Settings
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
from cv_ranker.segments import segment_resume


def req(name, idx=1):
    return ValidatedRequirement(requirement_id=f"R{idx:03d}", name=name, priority="required", jd_evidence=name)


def row(rid, status, sid=None, term=None):
    return LLMAssessmentItem(requirement_id=rid, status=status,
                             evidence_ids=[sid] if sid else [], matched_term=term)


def answer(*items):
    return LLMCandidateAssessmentResponse(assessments=list(items))


class Replies:
    def __init__(self, *replies, focused=True):
        self.responses = list(replies)
        self.calls = []
        self.settings = Settings(second_look_unmatched=True, focused_abbreviation_retry=focused)

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls.append((system_prompt, user_prompt))
        assert self.responses, f"Unexpected Qwen request after {len(self.calls)} calls"
        return self.responses.pop(0)


def test_nlp_invalid_grouped_match_gets_focused_citation_repair():
    llm = Replies(
        answer(row("R001", "not_matched")),
        answer(row("R001", "matched", "S001")),  # missing required matched_term
        answer(row("R001", "matched", "S001", "NLP")),
    )
    res, mode, warnings = assess_resume(
        resume_text="Skills:\nNLP\n", requirements=[req("Natural Language Processing")], llm=llm,
    )
    assert res[0].status == "matched" and res[0].matched_term == "NLP"
    assert res[0].evidence_ids == ["S001"]
    assert len(llm.calls) == 3 and mode == "llm_assessed"
    assert llm.calls[-1][1].startswith("SECOND LOOK FOCUSED ABBREVIATION")
    assert any("focused Qwen abbreviation match accepted" in w for w in warnings)


def test_gcp_initial_negative_gets_focused_llm_review_not_python_alias():
    llm = Replies(
        answer(row("R001", "not_matched")),
        answer(row("R001", "not_matched")),
        answer(row("R001", "matched", "S001", "GCP")),
    )
    res, _, _ = assess_resume(
        resume_text="Skills:\nGCP\n", requirements=[req("Google Cloud")], llm=llm,
    )
    assert res[0].status == "matched" and res[0].matched_term == "GCP"
    assert len(llm.calls) == 3


def test_orthographic_hint_alone_does_not_award_skill_match():
    llm = Replies(
        answer(row("R001", "not_matched")),
        answer(row("R001", "not_matched")),
        answer(row("R001", "not_matched")),
    )
    res, _, _ = assess_resume(
        resume_text="Skills:\nGCP\n", requirements=[req("Google Cloud")], llm=llm,
    )
    assert res[0].status == "not_matched" and len(llm.calls) == 3


def test_focused_fake_source_term_rejected_and_original_negative_retained():
    llm = Replies(
        answer(row("R001", "not_matched")),
        answer(row("R001", "not_matched")),
        answer(row("R001", "matched", "S001", "AWS")),
    )
    res, _, warnings = assess_resume(
        resume_text="Skills:\nGCP\n", requirements=[req("Google Cloud")], llm=llm,
    )
    assert res[0].status == "not_matched"
    assert any("matched_term was not present" in w for w in warnings)


def test_no_focused_attempt_when_switch_is_off():
    llm = Replies(answer(row("R001", "not_matched")), answer(row("R001", "not_matched")), focused=False)
    res, _, _ = assess_resume(resume_text="Skills:\nNLP\n", requirements=[req("Natural Language Processing")], llm=llm)
    assert res[0].status == "not_matched" and len(llm.calls) == 2


def test_no_spurious_second_look_for_unrelated_frameworks():
    llm = Replies(answer(row("R001", "not_matched")), focused=True)
    res, _, _ = assess_resume(resume_text="Experience:\nBuilt services with FastAPI.\n",
                              requirements=[req("Django")], llm=llm)
    assert res[0].status == "not_matched" and len(llm.calls) == 1


def test_orthographic_pattern_is_only_a_lead():
    segments = segment_resume("Skills:\nGCP\n")
    assert _has_orthographic_acronym_lead(req("Google Cloud"), segments)
    assert not _has_orthographic_acronym_lead(req("Django"), segments)


def test_focused_calls_are_capped_at_two_acronyms_per_batch():
    reqs = [req("Natural Language Processing", 1), req("Google Cloud", 2), req("Human Resources", 3)]
    llm = Replies(
        answer(*(row(r.requirement_id, "not_matched") for r in reqs)),
        answer(*(row(r.requirement_id, "not_matched") for r in reqs)),
        answer(row("R001", "not_matched")),
        answer(row("R002", "not_matched")),
    )
    res, _, warnings = assess_resume(
        resume_text="Skills:\nNLP\nGCP\nHR\n", requirements=reqs, llm=llm,
    )
    assert len(llm.calls) == 4
    assert [r.status for r in res] == ["not_matched"]*3
    assert any("limited to 2 of 3" in w for w in warnings)


def test_benchmark_traces_focused_call_as_second_look():
    from evaluation.trace import RecordingLLM
    backend = Replies(
        answer(row("R001", "not_matched")),
        answer(row("R001", "not_matched")),
        answer(row("R001", "matched", "S001", "NLP")),
    )
    recorder = RecordingLLM(backend)
    res, _, _ = assess_resume(
        resume_text="Skills:\nNLP\n", requirements=[req("Natural Language Processing")], llm=recorder,
    )
    assert res[0].status == "matched"
    assert recorder.observations()["R001"]["second_look"] is True
    assert recorder.observations()["R001"]["attempts"] == 3

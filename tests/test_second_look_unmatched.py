"""Selective second-look regressions; model owns semantics, Python never awards aliases."""
from cv_ranker.assessor import _unmatched_source_leads, assess_resume
from cv_ranker.config import Settings
from cv_ranker.schemas import LLMAssessmentItem, LLMCandidateAssessmentResponse, ValidatedRequirement
from cv_ranker.segments import segment_resume


class ControlledLLM:
    def __init__(self, *replies, enabled=True):
        self.replies = iter(replies)
        self.settings = Settings(second_look_unmatched=enabled, focused_abbreviation_retry=False)
        self.calls = []

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls.append((system_prompt, user_prompt))
        return next(self.replies)


def row(rid, status, sid=None, term=None):
    return LLMAssessmentItem(
        requirement_id=rid, status=status,
        evidence_ids=[sid] if sid else [], matched_term=term,
    )


def reply(*rows):
    return LLMCandidateAssessmentResponse(assessments=list(rows))


def run(requirements, resume, *replies, enabled=True):
    llm = ControlledLLM(*replies, enabled=enabled)
    reqs = [ValidatedRequirement(requirement_id=f'R{i:03d}', name=name, priority='required', jd_evidence=name)
            for i, name in enumerate(requirements, 1)]
    results, mode, warnings = assess_resume(resume_text=resume, requirements=reqs, llm=llm)
    return results, mode, warnings, llm


def test_nlp_and_gcp_falsenegatives_are_reconsidered_together_without_python_aliases():
    resume = 'Skills:\nNLP\nGCP\n'
    items, mode, warnings, llm = run(
        ['Natural Language Processing', 'Google Cloud'], resume,
        reply(row('R001', 'not_matched'), row('R002', 'not_matched')),
        reply(row('R001', 'matched', 'S001', 'NLP'), row('R002', 'matched', 'S002', 'GCP')),
    )
    assert [i.status for i in items] == ['matched', 'matched']
    assert [i.matched_term for i in items] == ['NLP', 'GCP']
    assert len(llm.calls) == 2 and mode == 'llm_assessed'
    assert 'not automatic matches' in llm.calls[1][1]
    assert any('Second look requested for 2' in w for w in warnings)


def test_paraphrase_reconsidered_with_full_original_source_evidence():
    resume = ('Summary:\nPython developer building applied AI products. '
              'Developed a source-first AI intake application for support workflows.\n')
    items, _, _, llm = run(
        ['AI application development'], resume,
        reply(row('R001', 'not_matched')),
        reply(row('R001', 'matched', 'S001')),
    )
    assert items[0].status == 'matched'
    assert items[0].evidence_segments[0].text.endswith('support workflows.')
    assert len(llm.calls) == 2


def test_years_claim_is_rechecked_but_qwen_must_approve_it():
    resume = 'Summary:\nPython developer with 5 years of professional experience.\n'
    items, _, _, llm = run(
        ['3+ years of Python experience'], resume,
        reply(row('R001', 'not_matched')),
        reply(row('R001', 'matched', 'S001')),
    )
    assert items[0].status == 'matched' and len(llm.calls) == 2


def test_django_must_not_be_rechecked_using_postgresql_or_fastapi():
    resume = ('Experience:\nBuilt internal APIs with FastAPI.\n'
              'Maintained PostgreSQL databases for production applications.\n')
    items, _, warnings, llm = run(
        ['Django', 'Redis'], resume,
        reply(row('R001', 'not_matched'), row('R002', 'not_matched')),
    )
    assert [i.status for i in items] == ['not_matched', 'not_matched']
    assert len(llm.calls) == 1 and not any('Second look' in w for w in warnings)


def test_negative_only_source_is_never_second_look_positive_lead():
    resume = 'Experience:\nNo professional experience with Docker.\n'
    leads = _unmatched_source_leads(
        ValidatedRequirement(requirement_id='R001', name='Docker', priority='required', jd_evidence='Docker'),
        segment_resume(resume),
    )
    assert leads == []


def test_title_or_degree_is_not_false_negative_trigger_for_proficiency():
    resume = 'Machine Learning Engineer\nEducation:\nBachelor of Science in Machine Learning\n'
    items, _, _, llm = run(['Machine Learning'], resume, reply(row('R001', 'not_matched')))
    assert items[0].status == 'not_matched' and len(llm.calls) == 1


def test_unverified_acronym_or_unrelated_term_cannot_be_auto_awarded():
    resume = 'Skills:\nGCP\n'
    items, _, warnings, llm = run(
        ['Google Cloud'], resume,
        reply(row('R001', 'not_matched')),
        reply(row('R001', 'matched', 'S001', 'AWS')),
    )
    assert items[0].status == 'not_matched'
    assert any('matched_term was not present' in w for w in warnings)
    assert len(llm.calls) == 2


def test_explicitly_negative_second_look_cannot_invent_credit():
    resume = 'Skills:\nNLP\n'
    items, _, _, llm = run(
        ['Natural Language Processing'], resume,
        reply(row('R001', 'not_matched')),
        reply(row('R001', 'not_matched')),
    )
    assert items[0].status == 'not_matched' and len(llm.calls) == 2


def test_second_look_can_be_disabled_for_cost_control():
    resume = 'Skills:\nNLP\n'
    items, _, _, llm = run(
        ['Natural Language Processing'], resume,
        reply(row('R001', 'not_matched')), enabled=False,
    )
    assert items[0].status == 'not_matched' and len(llm.calls) == 1


def test_two_lexical_clues_do_not_prove_a_match_without_qwen():
    resume = 'Summary:\nUsed AI application templates in a course.\n'
    items, _, _, llm = run(
        ['AI application development'], resume,
        reply(row('R001', 'not_matched')),
        reply(row('R001', 'not_matched')),
    )
    assert items[0].status == 'not_matched'
    assert len(llm.calls) == 2


def test_benchmark_trace_labels_second_look_separately_from_source_correction():
    from evaluation.trace import RecordingLLM
    from evaluation.evaluate_benchmark import RowResult, _attach_raw_observation, _measurement_quality
    backend = ControlledLLM(reply(row('R001', 'not_matched')), reply(row('R001', 'matched', 'S001', 'NLP')))
    recorder = RecordingLLM(backend)
    recorder.invoke_structured(system_prompt='You evaluate one resume', user_prompt='initial', schema=LLMCandidateAssessmentResponse)
    recorder.invoke_structured(system_prompt='You are correcting invalid rows', user_prompt='SECOND LOOK AT POSSIBLE FALSE NEGATIVES', schema=LLMCandidateAssessmentResponse)
    obs = recorder.observations()['R001']
    assert obs['second_look'] is True
    actual = RowResult('scenario','R001','Natural Language Processing','abbreviation', 'matched', 'matched', 'llm_assessed', ['S001'], 'NLP', 'NLP', True)
    enriched = _attach_raw_observation(actual, obs)
    assert enriched.decision_path == 'llm_second_look_agreed_with_final'
    quality = _measurement_quality([enriched], 'assessment')
    assert quality['llm_second_look_rows'] == ['scenario/R001']
    assert quality['llm_correction_rows'] == []

"""Seven independent audit regressions for the three-verdict supervisor workflow.

All candidate records are fictional.  Model stand-ins verify software behavior,
not production language-model quality.  Each test exercises a real owner of the
behavior under investigation, rather than mocking that owner.
"""
import json

from cv_ranker.compound_validation import apply_compound_checks
from cv_ranker.condition_review import review_compound_uncertainty
from cv_ranker.schemas import RequirementAssessment, EvidenceCitation, ValidatedRequirement
from cv_ranker.pipeline import reconcile_final_assessments, CVRanker
from cv_ranker.segments import segment_resume, ResumeSegment
from cv_ranker.config import Settings
from cv_ranker.llm import LLMError
from tests.test_v4970_supervisor_three_verdict_e2e import (
    JD, SOURCES, _approved, SyntheticLLM, StubEngine
)


def _queued(requirements, text=SOURCES['found']):
    initial = [RequirementAssessment(requirement_id=req.requirement_id,
                status='matched', unified_status='Found', reason='Preliminary assessment')
               for req in requirements]
    result, _, _ = apply_compound_checks(requirements=requirements,
                                         assessments=initial,resume_text=text)
    assert all(x.compound_check.outcome == 'needs_review' for x in result)
    return result


def _model(settings=None):
    return SyntheticLLM(settings or Settings())


def test_DA01_rate_limit_resume_can_retry_eligible_review(tmp_path):
    req = _approved(JD).requirements[0]
    class RateLimit(_model().__class__):
        def invoke_structured(self, **kw):
            self.http_attempts += 1
            raise LLMError('HTTP 429 rate limit')
    error_model = RateLimit(Settings())
    ledger=tmp_path/'operations.sqlite'
    rows, first = review_compound_uncertainty(requirements=[req],assessments=_queued([req]),
                   resume_text=SOURCES['found'],llm=error_model,ledger_path=ledger)
    assert first.attempted == 1
    assert rows[0].current_decision.failure.code == 'provider_rate_limit'
    later = _model()
    done, second = review_compound_uncertainty(requirements=[req],assessments=rows,
                   resume_text=SOURCES['found'],llm=later,ledger_path=ledger)
    assert second.attempted == 1
    assert done[0].current_decision.verdict == 'Found'
    assert later.http_attempts == 1


def test_DA02_committed_ledger_result_recovers_without_cached_report(tmp_path):
    req = _approved(JD).requirements[0]
    ledger=tmp_path/'operations.sqlite'
    first, stats = review_compound_uncertainty(requirements=[req],assessments=_queued([req]),
                   resume_text=SOURCES['found'],llm=_model(),ledger_path=ledger)
    assert stats.resolved == 1
    no_remote = _model()
    restored, stats = review_compound_uncertainty(requirements=[req],assessments=_queued([req]),
                   resume_text=SOURCES['found'],llm=no_remote,ledger_path=ledger)
    assert restored[0].current_decision.verdict == 'Found'
    assert no_remote.http_attempts == 0


def test_DA03_legacy_supervisor_dispatches_independent_compound_review(tmp_path,monkeypatch):
    from cv_ranker.schemas import RequirementAssessment
    def legacy_assess(*,requirements,**kwargs):
        return [RequirementAssessment(requirement_id=r.requirement_id,
                    status='matched',unified_status='Found',reason='Initial proposal')
                for r in requirements], 'llm_assessed', []
    monkeypatch.setattr('cv_ranker.pipeline.assess_resume',legacy_assess)
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM',SyntheticLLM)
    jd=tmp_path/'jd.txt'; jd.write_text(JD)
    cv=tmp_path/'cv.txt'; cv.write_text(SOURCES['found'])
    ranker=CVRanker(Settings(),use_llm=True,unified=False,embedding_cache_path=tmp_path/'cache.db')
    result=ranker.run(jd,[cv],approved_jd=_approved(JD))
    assert result.candidates[0].assessments[0].current_decision.verdict == 'Found'
    assert ranker.llm.http_attempts == 1


def test_DA04_seven_eligible_rows_complete_across_two_batches(tmp_path):
    base=_approved(JD).requirements[0]
    reqs=[base.model_copy(update={'requirement_id':f'R{x:03}'}) for x in range(1,8)]
    class Multibatch(SyntheticLLM):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            data=json.loads(user_prompt)
            result=[]
            for item in data['requirements']:
                single = dict(data)
                single['requirements']=[{'requirement_id':'R001'}]
                model_result=super().invoke_structured(system_prompt=system_prompt,
                       user_prompt=json.dumps(single),schema=schema)
                verdict=model_result.assessments[0].model_dump()
                verdict['requirement_id']=item['requirement_id']
                result.append(verdict)
            return schema.model_validate({'assessments':result})
    model=Multibatch(Settings())
    completed,stats=review_compound_uncertainty(requirements=reqs,assessments=_queued(reqs),
               resume_text=SOURCES['found'],llm=model,max_items=6,ledger_path=tmp_path/'operations.sqlite')
    assert stats.resolved == 7
    assert all(r.current_decision and r.current_decision.verdict=='Found' for r in completed)
    assert len(model.calls) == 7   # six rows in one call, last in another


def test_DA05_semantic_disagreement_is_not_structural_response_failure(tmp_path):
    from tests.test_v4917_frozen_skill_scope import (
        req, FlatEncoder, PersistentlyWrongProvider)
    from cv_ranker.unified import UnifiedEvidenceEngine
    provider=PersistentlyWrongProvider()
    original=ResumeSegment('S011','skills','GCP Cloud Run, BigQuery, Docker')
    with UnifiedEvidenceEngine(provider.settings,provider,encoder=FlatEncoder(),
             top_k=4,cache_path=tmp_path/'semantic.sqlite') as engine:
        result, stats=engine.assess([req('Google Cloud')],[original],original.text,candidate_id='fake')
    assert result[0].current_decision.failure is None or result[0].current_decision.failure.code != 'response_schema_invalid'


def test_DA06_transferable_provenance_checked_against_original_ledger():
    req=ValidatedRequirement(requirement_id='R001',name='Infrastructure automation with Terraform',
                             jd_evidence='Infrastructure automation with Terraform',priority='required')
    foreign=EvidenceCitation(segment_id='S001',section='experience',text='Built Pulumi automation pipelines.')
    row=RequirementAssessment(requirement_id='R001',status='not_matched',
        unified_status='Transferable',assessment_state='verified',reason='Related automation',
        evidence_ids=['S001'],evidence_segments=[foreign])
    actual=[ResumeSegment('S001','experience','Handled reception scheduling.')]
    final=reconcile_final_assessments(requirements=[req],assessments=[row],source_segments=actual)
    assert final[0].current_decision.verdict is None
    assert final[0].current_decision.failure.code=='source_identity_invalid'


def test_DA07_truthful_contextual_quotes_allowed_for_not_found():
    req=_approved(JD).requirements[0]
    original=SOURCES['not_found']
    class ContextualNegative(SyntheticLLM):
        def invoke_structured(self, *,system_prompt,user_prompt,schema):
            self.http_attempts += 1
            data=json.loads(user_prompt)
            source=next(s for s in data['sources'] if s['section']=='experience')
            sid=source['id']
            return schema.model_validate({'assessments':[{'requirement_id':'R001',
                'decision':'not_found','source_ids':[sid],
                'facets':[{'jd_exact_span':part,'jd_start':JD.index(part),
                     'jd_end':JD.index(part)+len(part),'relation':'missing',
                     'source_ids':[sid],'proof_quotes':[{'source_id':sid,'quote':'Processed customer payments'}],
                     'explanation':'Original retail activity examined, does not show the requested duties.'}
                    for part in ('Operate conveyor','document dispatch logs')],
                'missing_parts':['Operate conveyor','document dispatch logs'],
                'reason':'Retail payment duties do not establish either mandatory conveyor duty.'}]})
    result,stats=review_compound_uncertainty(requirements=[req],assessments=_queued([req],original),
                       resume_text=original,llm=ContextualNegative(Settings()),correction_budget=0)
    assert stats.resolved == 1
    assert result[0].current_decision.verdict == 'Not Found'
    assert result[0].evidence_ids


def test_DA01_supervisor_resume_preserves_failure_and_retries_429(tmp_path,monkeypatch):
    from cv_ranker.schemas import RankingReport
    from cv_ranker.eligibility import jd_source_sha256
    class Rejected(SyntheticLLM):
        def invoke_structured(self, **kw):
            self.http_attempts += 1
            raise LLMError('HTTP 429 rate limit')
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM',Rejected)
    jd=tmp_path/'jd.txt';jd.write_text(JD)
    cv=tmp_path/'cv.txt';cv.write_text(SOURCES['found'])
    first=CVRanker(Settings(),unified=True,embedding_cache_path=tmp_path/'cache.sqlite')
    prior=first.run(jd,[cv],approved_jd=_approved(JD))
    assert prior.candidates[0].assessments[0].current_decision.failure.code=='provider_rate_limit'
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM',SyntheticLLM)
    later=CVRanker(Settings(),unified=True,embedding_cache_path=tmp_path/'cache.sqlite')
    restored=later.run(jd,[cv],resume_report=RankingReport.model_validate_json(prior.model_dump_json()),
                      resume_candidates={first.source_keys[str(cv)]:prior.candidates[0]})
    assert later.llm.http_attempts==1
    assert restored.candidates[0].primary_score==100.0
    assert restored.candidates[0].assessments[0].current_decision.verdict=='Found'


def test_DA02_supervisor_replays_committed_review_without_in_memory_report(tmp_path,monkeypatch):
    monkeypatch.setattr('cv_ranker.unified.UnifiedEvidenceEngine', StubEngine)
    monkeypatch.setattr('cv_ranker.pipeline.StructuredLLM',SyntheticLLM)
    jd=tmp_path/'jd.txt';jd.write_text(JD)
    cv=tmp_path/'cv.txt';cv.write_text(SOURCES['found'])
    first=CVRanker(Settings(),unified=True,embedding_cache_path=tmp_path/'cache.sqlite')
    prior=first.run(jd,[cv],approved_jd=_approved(JD))
    assert first.llm.http_attempts==1
    later=CVRanker(Settings(),unified=True,embedding_cache_path=tmp_path/'cache.sqlite')
    restored=later.run(jd,[cv],approved_jd=_approved(JD))
    assert later.llm.http_attempts==0
    assert restored.candidates[0].assessments[0].current_decision.verdict=='Found'

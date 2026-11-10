"""Regressions from 12-candidate live 2026-10-20 transferability diagnostics."""
import hashlib
import json
from pathlib import Path

from cv_ranker.schemas import CandidateResult, RankingReport, ValidatedRequirement
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.segments import segment_resume
from cv_ranker.semantic.decomposition import JDSearchPlan, SearchCapability
from cv_ranker.semantic.transferability import (
    _validate_compact_response, _needs_transfer_second_look, _prompt,
    CompactCapabilityProposal, CompactTransferabilityResponse,
    AuditedCapability, assess_transferability_shadow,
)


def _cap():
    return SearchCapability(parent_requirement_id='R1', capability_id='R1',
        description='LangChain', source_quote='LangChain', origin='explicit',
        provenance='source_preserved', requires_human_review=False)


def _req():
    jd = 'REQUIRED SKILLS\nLangChain'
    r = ValidatedRequirement(requirement_id='R1', name='LangChain',
            priority='required', jd_evidence='LangChain')
    return r.model_copy(update={'constraint':classify_requirement(r,jd)})


def _resp(rel,ids):
    return CompactTransferabilityResponse(capabilities=[CompactCapabilityProposal(
        capability_id='R1', relationship=rel, source_ids=ids,
        explanation='Comparative evidence; not direct framework usage.')])


def test_valid_repeated_citations_and_overlarge_list_are_normalized():
    sources = {f'S{i:03}': f'Built an API component in project {i}.' for i in range(1, 6)}
    sections = {k:'experience' for k in sources}
    # A source is only accepted if it appeared in retrieved, audited sources.
    result,warnings = _validate_compact_response('R1',[_cap()], sources,
        _resp('transferable',['S001','S001','S002','S003','S004','S005']),
        requirement_name='LangChain',source_sections=sections)
    assert not warnings
    assert [c.segment_id for c in result[0].citations] == ['S001','S002','S003']
    assert result[0].citation_audit == 'source_validated'
    assert result[0].independent_semantic_verification is False


def test_repaired_excess_preserves_demonstrated_work_before_skills():
    sources = {'S001':'LangChain', 'S002':'Candidate job title',
               'S003':'Integrated retrieval through a custom framework.',
               'S004':'Deployed workflow API integrations.'}
    sections = {'S001':'skills','S002':'inferred_skills','S003':'experience','S004':'experience'}
    result,_ = _validate_compact_response('R1',[_cap()],sources,
        _resp('transferable',['S001','S002','S003','S004']),
        requirement_name='LangChain',source_sections=sections)
    ids = {c.segment_id for c in result[0].citations}
    assert ids == {'S001','S003','S004'}


def test_foreign_source_is_not_accepted_in_recovery_mode():
    result,warnings = _validate_compact_response('R1',[_cap()],
        {'S001':'Built a custom backend.'},_resp('transferable',['S999']),
        requirement_name='LangChain',recover_invalid=True)
    assert result[0].relationship == 'uncertain'
    assert result[0].citation_audit == 'audit_failed'
    assert warnings


def test_one_bad_row_does_not_erase_other_row():
    from pydantic import ValidationError
    c1=_cap()
    c2=c1.model_copy(update={'capability_id':'R1-C01','description':'API integration'})
    response = CompactTransferabilityResponse(capabilities=[
        CompactCapabilityProposal(capability_id='R1', relationship='uncertain',source_ids=[],explanation='Not certain'),
        CompactCapabilityProposal(capability_id='R1-C01', relationship='transferable',source_ids=['S999'],explanation='Bad ID')])
    result,warnings=_validate_compact_response('R1',[c1,c2], {'S001':'Built APIs'},response,recover_invalid=True)
    assert result[0].relationship == 'uncertain' and result[0].citation_audit == 'not_cited'
    assert result[1].citation_audit == 'audit_failed'
    assert warnings


def test_missed_capability_stays_uncertain_not_invented():
    c1=_cap()
    c2=c1.model_copy(update={'capability_id':'R1-C01'})
    result,warnings = _validate_compact_response('R1',[c1,c2],{'S001':'Built workflow.'},
                                                _resp('direct',['S001']),recover_invalid=True)
    assert [r.relationship for r in result] == ['direct','uncertain']
    assert result[1].citation_audit == 'audit_failed'
    assert warnings


def test_second_look_only_when_named_gap_and_performed_work():
    previous = [AuditedCapability(requirement_id='R1',capability_id='R1',
        relationship='uncertain',citations=[],explanation='Ambiguous',citation_audit='not_cited')]
    sources={'S001':'Has not used LangChain professionally.',
             'S002':'Implemented retrieval and conditional orchestration using a custom tool.'}
    sections={'S001':'experience','S002':'experience'}
    assert _needs_transfer_second_look(_req(),previous,sources,sections)
    assert not _needs_transfer_second_look(_req(),previous,
        {'S001':'Has not used LangChain professionally.'},{'S001':'experience'})
    assert not _needs_transfer_second_look(_req(),previous,
        {'S001':'LangChain', 'S002':'Studying workflow systems'},
        {'S001':'skills','S002':'education'})
    direct=[previous[0].model_copy(update={'relationship':'direct','citations':[]})]
    assert not _needs_transfer_second_look(_req(),direct,sources,sections)


def test_model_prompt_contains_sections_and_no_hardcoded_skill_substitution():
    raw=json.loads(_prompt(_req(),[_cap()],{'S001':'Created workflow.'},{'S001':'experience'}))
    assert raw['retrieved_cv_sources'][0]['source_section']=='experience'
    assert raw['frozen_requirement']['name']=='LangChain'


def test_integration_second_look_proposes_but_does_not_change_score(tmp_path):
    cv=tmp_path/'candidate.txt'
    cv.write_text('Experience:\nHas not used LangChain professionally.\n'
                  'Implemented retrieval pipelines with a different framework.\n',encoding='utf8')
    segments=segment_resume(cv.read_text(encoding='utf8'))
    evidence=[x for x in segments if 'LangChain' in x.text or 'Implemented' in x.text]
    assert len(evidence)>=2
    candidate=CandidateResult(candidate_name=cv.name,candidate_source=str(cv),
                              primary_score=20.,evaluation_mode='fallback_exact',rank=1)
    report=RankingReport(job_description_source='jd',jd_validation_mode='test',
                         yake_candidates=[],requirements=[_req()],candidates=[candidate])
    cid=hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    retrieval={'schema_version':2,'mode':'semantic_shadow_read_only','scoring_unchanged':True,
        'decomposition_enabled':True,'capability_search_plan':JDSearchPlan(
            complete=True,parent_count=1,capabilities=[_cap()],warnings=[]).model_dump(),
        'candidates':[{'candidate_id':cid,'candidate_name':cv.name,'direct_primary_score':20.,
         'ranking_position':1,'hits_by_requirement':{'R1':[
             {'segment_id':x.segment_id,'candidate_id':cid,'original_text':x.text,'section':x.section}
             for x in evidence]}}]}
    before=report.model_dump()
    class Fake:
        supports_compact_transferability=True
        calls=0
        def prompt_fits(self,*_):return True
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls+=1
            data=json.loads(user_prompt)
            if self.calls==1:
                return _resp('uncertain',[])
            assert 'review_focus' in data
            assert data['retrieved_cv_sources'][0]['source_section']=='experience'
            positive=next(x.segment_id for x in evidence if 'Implemented' in x.text)
            return _resp('transferable',[positive,positive])
    fake=Fake()
    output=assess_transferability_shadow(report,retrieval,fake)
    assert fake.calls==2
    assert output.complete
    item=output.candidates[0].assessments[0]
    assert item.relationship=='transferable'
    assert [c.exact_quote for c in item.citations]==['Implemented retrieval pipelines with a different framework.']
    assert item.independent_semantic_verification is False
    assert report.model_dump()==before
    assert output.candidates[0].original_primary_score==20.


def test_second_look_negative_keeps_uncertain_but_flags_manual_review(tmp_path):
    cv=tmp_path/'candidate.txt'
    cv.write_text('Experience:\nNo direct experience with LangChain.\nBuilt a custom workflow.\n')
    evidence=[x for x in segment_resume(cv.read_text()) if 'LangChain' in x.text or 'Built' in x.text]
    c=CandidateResult(candidate_name=cv.name,candidate_source=str(cv),primary_score=0.,evaluation_mode='fallback_exact',rank=1)
    report=RankingReport(job_description_source='jd',jd_validation_mode='test',yake_candidates=[],requirements=[_req()],candidates=[c])
    cid=hashlib.sha256(str(cv.resolve()).encode()).hexdigest()[:24]
    r={'schema_version':2,'mode':'semantic_shadow_read_only','scoring_unchanged':True,'decomposition_enabled':True,
       'capability_search_plan':JDSearchPlan(complete=True,parent_count=1,capabilities=[_cap()],warnings=[]).model_dump(),
       'candidates':[{'candidate_id':cid,'candidate_name':cv.name,'ranking_position':1,'direct_primary_score':0.,
       'hits_by_requirement':{'R1':[{'segment_id':x.segment_id,'candidate_id':cid,'section':x.section,'original_text':x.text} for x in evidence]}}]}
    class Fake:
        supports_compact_transferability=True
        calls=0
        def prompt_fits(self,*_):return True
        def invoke_structured(self,**_):
            self.calls+=1
            return _resp('uncertain',[])
    fake=Fake()
    out=assess_transferability_shadow(report,r,fake)
    assert fake.calls==2
    assert out.complete
    row=out.candidates[0].assessments[0]
    assert row.relationship=='uncertain'
    assert row.functional_review_candidate
    assert out.candidates[0].original_primary_score == 0.0

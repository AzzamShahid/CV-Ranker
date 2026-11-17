"""Real conditional request construction with fictional inputs; no paid provider calls."""
import json
from types import SimpleNamespace

from cv_ranker import prompt_fragments as pf
from cv_ranker.config import Settings
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.schemas import JDValidationResponse


def test_p1_jd_targeted_correction_keeps_valid_sibling_and_uses_one_objective():
    class Fake:
        def __init__(self): self.calls=[]
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls.append((system_prompt,user_prompt))
            if len(self.calls)==1:
                return schema.model_validate({'requirements':[
                    {'name':'Python','priority':'required','evidence':'Python'},
                    {'name':'Invented certificate','priority':'required','evidence':'A sentence not in JD'}]})
            return schema.model_validate({'requirements':[{'name':'SQL','priority':'required','evidence':'SQL'}]})
    model=Fake()
    rows,mode,warnings=validate_jd_requirements(jd_text='Required Skills:\nPython\nSQL',
        candidates=[],settings=Settings(),llm=model)
    assert len(model.calls)==2
    assert pf.JD_TARGETED_CORRECTION_OBJECTIVE in model.calls[1][1]
    assert pf.JD_FULL_REPLACEMENT_CORRECTION_OBJECTIVE not in model.calls[1][1]
    assert {r.name for r in rows}=={'Python','SQL'}
    assert mode in {'llm_validated','fallback_structural_after_llm'}


def test_p1_jd_full_replacement_only_for_empty_initial_output():
    class Fake:
        def __init__(self): self.calls=[]
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls.append((system_prompt,user_prompt))
            if len(self.calls)==1:return schema.model_validate({'requirements':[]})
            return schema.model_validate({'requirements':[{'name':'Python','priority':'required','evidence':'Python'}]})
    fake=Fake()
    rows,mode,_=validate_jd_requirements(jd_text='Required Skills:\nPython',
        candidates=[],settings=Settings(),llm=fake)
    assert len(fake.calls)==2
    assert pf.JD_FULL_REPLACEMENT_CORRECTION_OBJECTIVE in fake.calls[1][1]
    assert pf.JD_TARGETED_CORRECTION_OBJECTIVE not in fake.calls[1][1]
    assert len(rows)==1 and rows[0].name=='Python'


def test_p1_doctor_both_calls_send_exact_diagnostic_pair(monkeypatch):
    import doctor
    from cv_ranker import llm
    records=[]
    class Fake:
        def __init__(self,settings): pass
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            records.append((system_prompt,user_prompt,schema))
            return schema.model_validate({'ok':True,'message':'structured output works'})
    monkeypatch.setattr(llm,'StructuredLLM',Fake)
    assert doctor.check_structured_output(Settings())
    assert doctor.check_openrouter_structured_output(Settings())
    assert len(records)==2
    for system,user,_ in records:
        assert system==pf.DOCTOR_SYSTEM_PROMPT
        assert user==pf.DOCTOR_USER_PROMPT


def test_p1_compound_correction_request_is_schema_specific():
    from cv_ranker.condition_review import review_compound_uncertainty
    from cv_ranker.llm import ModelStructuredResponseError
    from tests.test_v4970_supervisor_three_verdict_e2e import JD,SOURCES,_approved,SyntheticLLM
    from tests.test_v4971_deep_audit import _queued
    class Fake(SyntheticLLM):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls.append(json.loads(user_prompt))
            self.http_attempts+=1
            if self.http_attempts==1:
                raise ModelStructuredResponseError('synthetic malformed response')
            # Parent reads this same schema and valid original source.
            self.http_attempts-=1
            return super().invoke_structured(system_prompt=system_prompt,user_prompt=user_prompt,schema=schema)
    fake=Fake(Settings())
    req=_approved(JD).requirements[0]
    result,stats=review_compound_uncertainty(requirements=[req],assessments=_queued([req]),
        resume_text=SOURCES['found'],llm=fake,correction_budget=1)
    assert fake.http_attempts==2
    assert len(fake.calls)>=2
    assert any(p.get('correction_request')==pf.COMPOUND_MALFORMED_RESPONSE_CORRECTION
               for p in fake.calls[1:])
    assert result[0].current_decision.verdict=='Found'


def test_p1_legacy_second_look_builder_retains_valid_json_payload():
    from cv_ranker.assessor import _build_user_prompt
    from cv_ranker.schemas import ValidatedRequirement
    from cv_ranker.segments import ResumeSegment
    from cv_ranker.assessor import SYSTEM_PROMPT
    r=ValidatedRequirement(requirement_id='R001',name='Warehouse dispatch',priority='required',jd_evidence='Warehouse dispatch')
    original=_build_user_prompt([r],[ResumeSegment('S001','experience','Delivered stock to loading bay.')])
    body=json.loads(original[original.index('{'):])
    assert body['frozen_requirements'][0]['requirement_id']=='R001'
    assert 'S001'==body['untrusted_original_cv_segments'][0]['segment_id']
    assert 'pf.LEGACY_UNMATCHED_SECOND_LOOK' in __import__('inspect').getsource(__import__('cv_ranker.assessor',fromlist=['assess_resume']))

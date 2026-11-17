"""Emit complete fictional pre-provider request examples, with real schemas.

Never use applicant records here: only the built-in development fixture file.
No model/HTTP calls are made.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(1,str(ROOT/'scripts'))
from prompt_first_pair_worker import construct


def main():
    cases=json.loads((ROOT/'evaluation/prompt_first/development_cases.json').read_text())['cases']
    examples=[]
    for stage in ('primary','independent','compound','jd'):
        item=next(x for x in cases if x['stage']==stage)
        system,user,schema,source_ids=construct(item)
        examples.append({'case_id':item['case_id'],'stage':stage,
                         'synthetic_only':True,
                         'system_prompt':system,'user_message_exact':user,
                         'response_schema':schema.model_json_schema(),
                         'source_ids':source_ids,
                         'system_sha256':hashlib.sha256(system.encode()).hexdigest(),
                         'user_sha256':hashlib.sha256(user.encode()).hexdigest()})
    # Non-decision builders are separate from the wording-only paired arms:
    # their input packets intentionally changed to source-safe JSON in v54.
    from cv_ranker.schemas import (ValidatedRequirement,RequirementConstraint,
                                   LLMTypeResponse,LLMCandidateAssessmentResponse)
    from cv_ranker.segments import ResumeSegment
    from cv_ranker.requirement_typing import enrich_ambiguous_types,TYPE_SYSTEM_PROMPT
    from cv_ranker.semantic.decomposition import _prompt as decomposition_prompt, SYSTEM_PROMPT as DECOMP_PROMPT, DecompositionResponse
    from cv_ranker.assessor import _build_user_prompt,SYSTEM_PROMPT as LEGACY_PROMPT
    from cv_ranker.ui.final_decisions import _judge_requirement, _JUDGE_PROMPT, CompactFocusedJudgment
    req=ValidatedRequirement(requirement_id='R001',name='Organize service records',
                             jd_evidence='Organize service records',priority='required')
    req_type=req.model_copy(update={'constraint':RequirementConstraint(
                     kind='other',source_line_numbers=[1],origin='manual_review_pending')})
    class TypingCapture:
        saved=None
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.saved=(system_prompt,user_prompt,schema)
            return schema.model_validate({'requirements':[{'requirement_id':'R001','kind':'responsibility'}]})
    cp=TypingCapture()
    enrich_ambiguous_types([req_type],cp)
    typ_sys,typ_user,typ_schema=cp.saved
    packets=[('jd_typing',typ_sys,typ_user,typ_schema),
             ('retrieval_decomposition',DECOMP_PROMPT,decomposition_prompt([req]),DecompositionResponse),
             ('legacy_assessment',LEGACY_PROMPT,_build_user_prompt([req],[
                  ResumeSegment('S001','experience','Organized service records for the support desk.')]),
                  LLMCandidateAssessmentResponse)]
    class JudgeCapture:
        prefer_flat_focused_judgment=True
        saved=None
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.saved=(system_prompt,user_prompt,schema)
            return CompactFocusedJudgment(result='not_evidenced',
                     explanation='Only partial records are documented; scope needs review.',source_ids=[])
    jc=JudgeCapture()
    _judge_requirement(jc,req,None,[],{'S001':ResumeSegment('S001','experience',
                   'Organized service records for the support desk.')})
    if jc.saved is None:raise RuntimeError('Focused synthetic request not captured')
    judge_sys,judge_user,judge_schema=jc.saved
    packets.append(('optional_focused_ui',judge_sys,judge_user,judge_schema))
    for name,sysmsg,user,schema in packets:
        examples.append({'case_id':name,'stage':name,'synthetic_only':True,
                         'system_prompt':sysmsg,'user_message_exact':user,
                         'response_schema':schema.model_json_schema(),
                         'system_sha256':hashlib.sha256(sysmsg.encode()).hexdigest(),
                         'user_sha256':hashlib.sha256(user.encode()).hexdigest(),
                         'capture_kind':'deterministic pre-provider builder or intercepted call'})
    destination=ROOT/'docs/V4968_FICTIONAL_PRE_PROVIDER_PACKETS.json'
    destination.write_text(json.dumps({'examples':examples,
          'note':'Source-bound synthetic request packets; no real provider call or model output.'},
          indent=2,ensure_ascii=False)+'\n')
    print('written',len(examples),'synthetic packets')
if __name__=='__main__':main()

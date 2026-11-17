"""Isolated, source-authenticated prompt experiment worker.

The harness runs each arm in its *own subprocess* rooted in that source tree.
Packet mode makes no provider calls. Local/cloud mode needs explicit CLI opt-in
at the parent runner; only fictional development fixtures are allowed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

# The supervisor runner passes a manifest-verified source root. In the fresh
# worker process only THAT tree may provide cv_ranker imports.
PROJECT_ROOT: Path | None = None

def sha(data: str | bytes) -> str:
    b = data.encode('utf-8') if isinstance(data,str) else data
    return hashlib.sha256(b).hexdigest()


def construct(case: dict[str,Any]):
    from cv_ranker.requirement_typing import classify_requirement
    from cv_ranker.schemas import (ValidatedRequirement, EvidenceCitation,
                                   RequirementAssessment, CompoundCheck, DecisionTransition)
    from cv_ranker.segments import ResumeSegment
    from cv_ranker.unified import (_payload, UNIFIED_PROMPT,
                                   FINAL_ADJUDICATION_PROMPT,
                                   _keyed_response_schema, _independent_response_schema)
    from cv_ranker.condition_review import ConditionReviewResponse, review_compound_uncertainty
    from cv_ranker.jd import SYSTEM_PROMPT as JD_SYSTEM, _user_prompt
    from cv_ranker.schemas import JDValidationResponse
    from cv_ranker.config import Settings
    from cv_ranker.llm import estimate_tokens
    case_stage = case['stage']
    if case_stage == 'jd':
        prompt=_user_prompt(case['jd'],[])
        return JD_SYSTEM,prompt,JDValidationResponse,[]
    req = ValidatedRequirement(requirement_id='R001',name=case['jd'],
                               jd_evidence=case['jd'],priority='required')
    req.constraint=classify_requirement(req,case['jd'])
    sources=[ResumeSegment(s['id'],s['section'],s['text']) for s in case['sources']]
    ids=[s.segment_id for s in sources]
    if len(ids)!=len(set(ids)):
        raise ValueError('Fixture S IDs must be unique per candidate')
    hits={req.requirement_id:ids}
    mapping={s.segment_id:s for s in sources}
    if case_stage in ('primary','independent'):
        prompt=_payload([req],mapping,hits,len(ids))
        if case_stage=='primary':
            return UNIFIED_PROMPT,prompt,_keyed_response_schema(('R001',),strict_relation=True),ids
        return FINAL_ADJUDICATION_PROMPT,prompt,_independent_response_schema(('R001',)),ids
    if case_stage=='compound':
        class Capture:
            settings=Settings(llm_provider='ollama')
            saved=None
            def prompt_fits(self,system_prompt,user_prompt):return True
            def invoke_structured(self,*,system_prompt,user_prompt,schema):
                self.saved=(system_prompt,user_prompt,schema)
                raise RuntimeError('Captured pre-provider boundary; no network call')
        capture=Capture()
        candidate='Experience\n'+'\n'.join(s['text'] for s in case['sources'])
        # Keep true original segment identifiers from the serializer, not a
        # convenience renumbering from the hand-labeled fixture.
        from cv_ranker.segments import segment_resume
        originals=segment_resume(candidate)
        proof=[EvidenceCitation(segment_id=s.segment_id, section=s.section,text=s.text)
               for s in originals if any(item['text'] in s.text for item in case['sources'])]
        if not proof:raise ValueError('Synthetic review evidence never entered original segmenter')
        row=RequirementAssessment(requirement_id='R001', status='uncertain',
            unified_status='Unverified',assessment_state='unverified',
            evidence_ids=[s.segment_id for s in proof],evidence_segments=proof,
            compound_check=CompoundCheck(operator=req.constraint.operator,
                outcome='needs_review',explanation='Synthetic grammatical ambiguity'),
            decision_trace=[DecisionTransition(stage='compound_validator',
                from_status='Found',to_status='Unverified',
                reason_code='jd_syntax_needs_review',evidence_ids=[s.segment_id for s in proof])])
        review_compound_uncertainty(requirements=[req],assessments=[row],
                                   resume_text=candidate,llm=capture,ledger_path=None)
        if capture.saved is None:
            raise ValueError('Compound synthetic capture did not reach provider boundary')
        system,user,schema = capture.saved
        return system,user,schema,[s.segment_id for s in originals]
    raise ValueError('Unknown stage')


def main() -> int:
    request=json.loads(sys.stdin.read())
    root=Path(request['expected_root']).resolve()
    if not (root/'cv_ranker/build_manifest.json').is_file():
        raise RuntimeError('No authenticated source root')
    sys.path.insert(0,str(root))
    case=request['case']
    system,user,schema,ids=construct(case)
    from cv_ranker.llm import estimate_tokens
    stats={'case_id':case['case_id'],'stage':case['stage'],
           'project_root':str(root),
           'schema_name':schema.__name__,
           'schema_sha256':sha(json.dumps(schema.model_json_schema(),sort_keys=True)),
           'system_sha256':sha(system),'user_sha256':sha(user),
           'prompt_tokens_estimate':estimate_tokens(system)+estimate_tokens(user)+300,
           'system_chars':len(system), 'user_chars':len(user),
           'candidate_source_ids':ids,
           'candidate_source_count':len(ids),
           'model_calls':0, 'response':None,'error_code':None,
           'elapsed_seconds':0,'usage':None,'mode':request['mode']}
    if request['mode']=='packet':
        print(json.dumps(stats,ensure_ascii=False));return 0
    from cv_ranker.config import Settings
    from cv_ranker.llm import StructuredLLM, OpenRouterStructuredLLM
    provider=request['mode']
    settings=Settings(llm_provider=provider, llm_retries=0,
                      openrouter_max_requests_per_run=request.get('request_ceiling',1))
    begin=time.monotonic()
    try:
        client=(StructuredLLM(settings) if provider=='ollama' else OpenRouterStructuredLLM(settings))
        result=client.invoke_structured(system_prompt=system,user_prompt=user,schema=schema)
        stats['model_calls']=getattr(client,'logical_calls',1)
        stats['response']=result.model_dump(mode='json')
        stats['usage']=getattr(client,'token_usage',None)
    except Exception as exc:
        stats['error_code']=type(exc).__name__  # never echo private provider data
        stats['model_calls']=getattr(locals().get('client'),'logical_calls',0)
    stats['elapsed_seconds']=round(time.monotonic()-begin,4)
    print(json.dumps(stats,ensure_ascii=False,default=str))
    return 0

if __name__=='__main__':raise SystemExit(main())

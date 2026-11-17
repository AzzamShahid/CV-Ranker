"""One isolated process per source tree, no implicit model calls.

This runner itself lives in the candidate tools directory. It ONLY imports
cv_ranker from the explicit manifest-verified root supplied by its parent.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import time

def sha(text:str):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def main():
    request=json.loads(sys.stdin.read())
    root=Path(request['expected_root']).resolve()
    sys.path.insert(0,str(root))
    sys.path.insert(1,str(Path(__file__).resolve().parent))
    import cv_ranker
    from prompt_first_pair_worker import construct
    from cv_ranker.llm import estimate_tokens
    assert Path(cv_ranker.__file__).resolve().is_relative_to(root/'cv_ranker'), 'Wrong imported source tree'
    provider=request['mode']
    client=None
    error_on_setup=None
    if provider!='packet':
        try:
            from cv_ranker.config import Settings
            from cv_ranker.llm import StructuredLLM,OpenRouterStructuredLLM
            settings=Settings(llm_provider=provider,llm_retries=0,
                              openrouter_max_requests_per_run=request.get('request_ceiling',1))
            client=(StructuredLLM(settings) if provider=='ollama' else OpenRouterStructuredLLM(settings))
        except Exception as exc:
            error_on_setup=type(exc).__name__
    records=[]
    total_attempted=0
    ceiling=int(request.get('request_ceiling',1))
    for case in request['cases']:
        sys_prompt,user_prompt,schema,ids=construct(case)
        schema_hash=sha(json.dumps(schema.model_json_schema(),sort_keys=True))
        rec={'case_id':case['case_id'],'stage':case['stage'],'project_root':str(root),
             'schema_name':schema.__name__,'schema_sha256':schema_hash,
             'system_sha256':sha(sys_prompt),'user_sha256':sha(user_prompt),
             'prompt_tokens_estimate':estimate_tokens(sys_prompt)+estimate_tokens(user_prompt)+300,
             'system_chars':len(sys_prompt),'user_chars':len(user_prompt),
             'candidate_source_ids':ids,'candidate_source_count':len(ids),
             'model_calls':0,'provider_http_attempts':0,'response':None,'error_code':error_on_setup,
             'elapsed_seconds':0,'usage':None,'mode':provider}
        if request.get('emit_synthetic_packet'):
            rec['synthetic_packet']={'system_prompt':sys_prompt,'user_prompt':user_prompt,
                                     'schema':schema.model_json_schema()}
        if provider!='packet' and client is not None:
            if total_attempted >= ceiling:
                rec['error_code']='REQUEST_CEILING_REACHED'
                records.append(rec)
                continue
            total_attempted+=1
            start=time.monotonic()
            before=getattr(client,'logical_calls',0)
            http_before=getattr(client,'http_attempts',0)
            try:
                result=client.invoke_structured(system_prompt=sys_prompt,user_prompt=user_prompt,schema=schema)
                rec['response']=result.model_dump(mode='json')
                rec['usage']=getattr(client,'token_usage',None)
            except Exception as exc:
                rec['error_code']=type(exc).__name__
            rec['elapsed_seconds']=round(time.monotonic()-start,4)
            rec['model_calls']=getattr(client,'logical_calls',0)-before
            rec['provider_http_attempts']=getattr(client,'http_attempts',0)-http_before
        records.append(rec)
    print(json.dumps({'project_root':str(root),'items':records},ensure_ascii=False,default=str))
    return 0
if __name__=='__main__':raise SystemExit(main())

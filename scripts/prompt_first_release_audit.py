"""Generate an exact 13-prompt/16-builder release ledger from two source roots.

No CVs, model calls, or private runtime data. Hashes source expressions, not
proof of model quality. Caller coverage reports source inspection honestly.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path

CALLER_ROUTES={
 'jd.py:_user_prompt':'jd.SYSTEM_PROMPT / jd.CORRECTION_PROMPT',
 'jd.py:validate_jd_requirements':'jd.SYSTEM_PROMPT / jd.CORRECTION_PROMPT → JDValidationResponse',
 'requirement_typing.py:enrich_ambiguous_types':'requirement_typing.TYPE_SYSTEM_PROMPT → LLMTypeResponse',
 'assessor.py:_build_user_prompt':'assessor.SYSTEM_PROMPT / assessor.CORRECTION_PROMPT',
 'assessor.py:_correct_invalid_rows':'assessor.CORRECTION_PROMPT → LLMCandidateAssessmentResponse',
 'assessor.py:_focused_abbreviation_recheck':'assessor.CORRECTION_PROMPT → LLMCandidateAssessmentResponse',
 'unified.py:_payload':'unified.UNIFIED_PROMPT / FINAL_ADJUDICATION_PROMPT',
 'unified.py:_correction_payload':'unified.UNIFIED_PROMPT → dynamic ID keyed schema',
 'unified.py:plan_evidence_batches':'unified.UNIFIED_PROMPT → bounded grouped packet',
 'unified.py:_independently_adjudicate':'unified.FINAL_ADJUDICATION_PROMPT → independent ID-keyed schema',
 'semantic/decomposition.py:create_shadow_search_plan':'semantic/decomposition.SYSTEM_PROMPT → JDSearchPlan',
 'semantic/transferability.py:assess_transferability_shadow':'semantic/transferability.SYSTEM_PROMPT → TransferabilityResponse',
 'semantic/transferability.py:_assess_single_compact':'semantic/transferability.COMPACT_SYSTEM_PROMPT → CompactTransferabilityResponse',
 'semantic/transferability.py:_assess_compact_jobs':'semantic/transferability.BATCH_SYSTEM_PROMPT → CompactBatchResponse',
 'ui/final_decisions.py:_judge_requirement':'ui/final_decisions._JUDGE_PROMPT → FocusedJudgment',
 'condition_review.py:review_compound_uncertainty':'condition_review.REVIEW_PROMPT → ConditionReviewResponse',
}
REASON={
 'unified.py:UNIFIED_PROMPT':('change','Explicit selected-source incompleteness, actor, duties, material scope, wrong-source reasoning; no wire/schema change'),
 'unified.py:FINAL_ADJUDICATION_PROMPT':('change','Independent check can reverse unsupported positive as well as missed equivalent; previous model rationale is not source proof'),
 'condition_review.py:REVIEW_PROMPT':('change','Correct schema field names, exact quotes/offsets and approved all_of/any_of leaf coverage'),
 'jd.py:SYSTEM_PROMPT':('change','Inherited Required/Preferred heading and source-grounded narrative coverage'),
 'jd.py:CORRECTION_PROMPT':('change','Target only rejected/omitted JD clauses; preserve valid siblings and source denominator'),
 'requirement_typing.py:TYPE_SYSTEM_PROMPT':('change','Distinguish candidate professional tenure from operational duration and skills from completed duty'),
 'assessor.py:SYSTEM_PROMPT':('retain','Existing legacy gate has extensive positive/negative tests; no isolated first prompt defect established'),
 'assessor.py:CORRECTION_PROMPT':('retain','Bounded repair schema retained; no external A/B evidence to justify risk'),
 'semantic/decomposition.py:SYSTEM_PROMPT':('retain','Retrieval prompts can change evidence inputs; needs separate end-to-end experiment'),
 'semantic/transferability.py:SYSTEM_PROMPT':('retain','Existing source-bound transfer relation and ownership contract protected'),
 'semantic/transferability.py:COMPACT_SYSTEM_PROMPT':('retain','Compact capabilities schema is versioned and protected by regression tests'),
 'semantic/transferability.py:BATCH_SYSTEM_PROMPT':('retain','Separate requirements/capabilities wrapper; preserve multi-row schema'),
 'ui/final_decisions.py:_JUDGE_PROMPT':('retain','Optional Streamlit judge not live-UI tested in current environment; defer language edit'),
}

def inventory(root:Path):
    import runpy
    # Avoid importing a different cv_ranker version into this generator.
    script=root/'scripts/prompt_inventory.py'
    env=runpy.run_path(str(script))
    return env['inventory']()

def prompt_text(root:Path, filename:str,name:str):
    text=(root/'cv_ranker'/filename).read_text(encoding='utf-8')
    for item in ast.parse(text).body:
        if isinstance(item,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in item.targets):
            try:return ast.literal_eval(item.value)
            except (TypeError,ValueError):return None
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    old,new=a.baseline.resolve(),a.candidate.resolve()
    x,y=inventory(old),inventory(new)
    assert len(x['prompt_definitions'])==len(y['prompt_definitions'])==13
    assert len(x['builders_to_review'])==len(y['builders_to_review'])==16
    o={(z['path'],z['name']):z for z in x['prompt_definitions']}
    inventory_rows=[]
    for i in y['prompt_definitions']:
        key=(i['path'],i['name']);before=o[key]
        relative=i['path'].removeprefix('cv_ranker/')
        mode,reason=REASON[f'{relative}:{i["name"]}']
        changed=before['assignment_sha256'] != i['assignment_sha256']
        assert changed==(mode=='change'),f'Unaccounted prompt change: {key}'
        prev=prompt_text(old,relative,i['name'])
        after=prompt_text(new,relative,i['name'])
        inventory_rows.append({'prompt':f'{relative}:{i["name"]}',
           'status':'experimental_wording_changed' if changed else 'retained',
           'diagnosis_or_reason':reason,
           'baseline_source_expression_sha256':before['assignment_sha256'],
           'candidate_source_expression_sha256':i['assignment_sha256'],
           'baseline_assignment_bytes':before['assignment_bytes'],
           'candidate_assignment_bytes':i['assignment_bytes'],
           'baseline_prompt_characters':len(prev) if prev is not None else None,
           'candidate_prompt_characters':len(after) if after is not None else None,
           'response_schema':'unchanged by this release',
           'real_model_quality':'unmeasured; requires paired local/cloud calls and independent labels'})
    callers=[]
    for b in y['builders_to_review']:
        key=b['path'].removeprefix('cv_ranker/')+':'+b['name']
        assert key in CALLER_ROUTES,key
        callers.append({'builder':key,'source_line':b['line'],
                        'route_and_response':CALLER_ROUTES[key],
                        'coverage':'source/callsite inventoried; eight fictional source packets; other callsites inventoried but not all end-to-end executed',
                        'schema_change':('source JSON input packet replaces text delimiters'
                            if key in {'requirement_typing.py:enrich_ambiguous_types',
                                       'semantic/decomposition.py:create_shadow_search_plan'}
                            else 'none in this release')})
    output={'baseline_source':str(old),'candidate_source':str(new),
       'old_prompts':13,'new_prompts':13,'changed':sum(x['status'].startswith('experimental') for x in inventory_rows),
       'retained':sum(x['status']=='retained' for x in inventory_rows),
       'prompt_ledger':inventory_rows,'builder_coverage':callers,
       'test_level':'deterministic source and packet contract; live quality not measured'}
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'V4968_PROMPT_AND_BUILDER_LEDGER.json').write_text(json.dumps(output,indent=2)+'\n')
    print('prompts',len(inventory_rows),'changed',output['changed'],'builders',len(callers))

if __name__=='__main__':main()

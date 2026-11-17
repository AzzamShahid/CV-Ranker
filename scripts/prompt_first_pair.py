"""Paired prompt experiment with unchanged source packets and schema.

Packet mode is safe and default (NO MODEL CALLS). Live model mode requires an
explicit opt-in. Compare the release baseline and candidate on the same
fictional JD/CV excerpts. A contract packet comparison is not accuracy.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def hashfile(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(root:Path):
    root=root.resolve()
    manifest=json.loads((root/'cv_ranker/build_manifest.json').read_text())
    for name,expected in manifest['files'].items():
        filename=(root/name).resolve()
        if not filename.is_relative_to(root) or not filename.is_file():
            raise ValueError('Invalid manifest file location')
        if hashfile(filename)!=expected:
            raise ValueError(f'Source identity mismatch: {name}')
    return manifest['build_id'],manifest['assessment_protocol_version'],hashfile(root/'cv_ranker/build_manifest.json')


def child_batch(root:Path,cases:list[dict],mode:str,ceiling:int,emit_packet:bool=False):
    process=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve().parent/'prompt_first_pair_batch_worker.py')],
        input=json.dumps({'expected_root':str(root),'cases':cases,'mode':mode,
                          'request_ceiling':ceiling,'emit_synthetic_packet':emit_packet}),
        text=True,capture_output=True,cwd=root,timeout=180)
    if process.returncode!=0:
        # No provider error text or synthetic resume is printed in failures.
        raise RuntimeError(f'Isolated arm failed before producing paired measurements (exit {process.returncode})')
    try:
        result=json.loads(process.stdout)
        if result['project_root']!=str(root):raise ValueError('wrong root')
        rows=result['items']
        if len(rows)!=len(cases):raise ValueError('missing case')
        return rows
    except (ValueError,KeyError,TypeError) as exc:
        raise RuntimeError('Arm omitted records or returned invalid JSON') from exc


def decision(item:dict)->str|None:
    response=item.get('response')
    if not response:return None
    if item['stage']=='jd':
        return f'jd_{len(response.get("requirements",[]))}_requirements'
    if item['stage']=='compound':
        rows=response.get('assessments',[])
        return rows[0]['decision'] if len(rows)==1 else 'invalid_count'
    row=response.get('R001')
    return row.get('decision') if isinstance(row,dict) else 'invalid_shape'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',required=True,type=Path)
    p.add_argument('--candidate',required=True,type=Path)
    p.add_argument('--cases',type=Path,default=Path(__file__).resolve().parents[1]/'evaluation/prompt_first/development_cases.json')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['packet','ollama','openrouter'],default='packet')
    p.add_argument('--authorize-local',action='store_true')
    p.add_argument('--authorize-external-fictitious-data',action='store_true')
    p.add_argument('--request-ceiling',type=int,default=1)
    args=p.parse_args(argv)
    left,right=args.baseline.resolve(),args.candidate.resolve()
    if left==right:raise SystemExit('Refusing to compare the same project tree')
    if args.mode=='ollama' and not args.authorize_local:
        raise SystemExit('Local inference requires explicit --authorize-local')
    if args.mode=='openrouter' and not args.authorize_external_fictitious_data:
        raise SystemExit('Cloud inference needs explicit --authorize-external-fictitious-data')
    if args.request_ceiling<1:raise SystemExit('request ceiling must be positive')
    lhs=identity(left);rhs=identity(right)
    if lhs==rhs:raise SystemExit('Identical baseline and candidate source identities')
    corpus=json.loads(args.cases.read_text(encoding='utf-8'))
    if not corpus.get('synthetic_only'):
        raise SystemExit('Paired runner is restricted to designated fictional fixtures')
    cases=corpus['cases']
    if len({x['case_id'] for x in cases})!=len(cases):raise SystemExit('Duplicate case IDs')
    rows=[]
    left_results=child_batch(left,cases,args.mode,args.request_ceiling)
    right_results=child_batch(right,cases,args.mode,args.request_ceiling)
    for case,a,b in zip(cases,left_results,right_results):
        if (a['user_sha256'],a['schema_sha256'])!=(b['user_sha256'],b['schema_sha256']):
            raise RuntimeError(f'Packet or schema changed across arms: {case["case_id"]}; isolate builder changes separately')
        if a['project_root']==b['project_root']:raise RuntimeError('Same imported runtime root')
        ad,bd=decision(a),decision(b)
        expected=case['expected']
        rows.append({'case_id':case['case_id'],'stage':case['stage'],
                     'expected_independent_development_label':expected,
                     'source_packet_sha256':a['user_sha256'],
                     'schema_sha256':a['schema_sha256'],
                     'baseline':a,'candidate':b,
                     'baseline_correct':ad==expected if ad is not None else None,
                     'candidate_correct':bd==expected if bd is not None else None})
    measured=[r for r in rows if r['baseline_correct'] is not None and r['candidate_correct'] is not None]
    counts=Counter(('right' if r['baseline_correct'] else 'wrong')+'→'+('right' if r['candidate_correct'] else 'wrong') for r in measured)
    results={'experiment':'prompt_first_paired_v1','measurement_level':(
                'packet_and_schema_only_no_model_accuracy' if args.mode=='packet' else
                'live_model_unadjudicated_development_fixture'),
             'provider_mode':args.mode,
             'baseline':{'build_id':lhs[0],'protocol':lhs[1],'manifest_sha256':lhs[2]},
             'candidate':{'build_id':rhs[0],'protocol':rhs[1],'manifest_sha256':rhs[2]},
             'fictional_fixture_sha256':hashfile(args.cases),
             'case_count':len(rows),'cases':rows,
             'paired_correctness':dict(counts),
             'total_logical_calls':{k:sum(row[k]['model_calls'] for row in rows)
                                    for k in ('baseline','candidate')},
             'actual_provider_spend':'unknown, no claimed dollar measurement',
             'independent_holdout_status':'not_supplied'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Verified paired source/schema:',len(rows),'cases; mode:',args.mode)
    print('Baseline',lhs[0],'; candidate',rhs[0])
    print('Accuracy measurements:',len(measured),'(none in packet mode)')
    print('Output',args.output)
    return 0

if __name__=='__main__':raise SystemExit(main())

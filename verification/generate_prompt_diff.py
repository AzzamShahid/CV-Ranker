"""Read-only prompt/contract compare with an explicitly supplied old root."""
from __future__ import annotations
import argparse, ast, hashlib, json, runpy
from pathlib import Path


def index(root:Path,PROMPTS,BUILDERS):
    # Use the successor inventory for both source trees; historical inventory
    # omitted the condition-review prompt/caller even though the code had it.
    data={}
    for path,keys in PROMPTS.items():
        file=root/'cv_ranker'/path
        tree=ast.parse(file.read_text())
        for node in tree.body:
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t,ast.Name) and t.id in keys:
                        data[f'{path}:{t.id}']=hashlib.sha256(ast.get_source_segment(file.read_text(),node).encode()).hexdigest()
    functions={}
    for path,keys in BUILDERS.items():
        file=root/'cv_ranker'/path
        tree=ast.parse(file.read_text())
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in keys:
                functions[f'{path}:{node.name}']=hashlib.sha256(ast.get_source_segment(file.read_text(),node).encode()).hexdigest()
    return data,functions


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    specs=runpy.run_path(str(args.candidate/'scripts'/'prompt_inventory.py'))
    first,first_builders=index(args.baseline,specs['PROMPTS'],specs['BUILDERS'])
    later,later_builders=index(args.candidate,specs['PROMPTS'],specs['BUILDERS'])
    rows=[{'symbol':x,'v51_sha256':first.get(x),'v52_sha256':later.get(x),
           'status':'changed' if first.get(x)!=later.get(x) else 'unchanged'}
          for x in later]
    builders=[{'symbol':x,'v51_sha256':first_builders.get(x),'v52_sha256':later_builders.get(x),
           'status':'changed' if first_builders.get(x)!=later_builders.get(x) else 'unchanged'}
          for x in later_builders]
    out={'type':'source-expression prompt diff only, not live A/B accuracy',
         'baseline':'v51','candidate':'v52','runtime_prompt_count':len(rows),
         'builder_function_count':len(builders),'prompts':rows,'builders':builders}
    args.output.write_text(json.dumps(out,indent=2)+'\n')
    print('prompts',len(rows),'changed',sum(x['status']=='changed' for x in rows),
          'builders',len(builders),'changed',sum(x['status']=='changed' for x in builders))

if __name__=='__main__':main()

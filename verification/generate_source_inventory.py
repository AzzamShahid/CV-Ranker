"""Inventory and syntax audit; never confuse parse success with full behavior QA."""
from __future__ import annotations
import ast,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'__pycache__','.pytest_cache','.venv','outputs'}
DEST=ROOT/'verification'/'V4966_SOURCE_INVENTORY.json'


def category(path:str)->str:
    if path.startswith('cv_ranker/'):return 'production_source'
    if path.startswith('tests/'):return 'tests'
    if path.startswith('docs/'):return 'documentation'
    if path.startswith('scripts/') or path.startswith('evaluation/') or path.startswith('verification/'):
        return 'verification_or_utilities'
    if path.endswith(('.md','.rst')):return 'documentation'
    if path.startswith(('.streamlit/','.github/')):return 'deployment_or_ci'
    if path.endswith(('.txt','.toml','.ini','.yaml','.yml','.json','.cmd','.env.example')):return 'config_or_data'
    return 'assets_or_other'


def main():
    entries=[]
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or any(x in EXCLUDE for x in path.parts) or path==DEST:
            continue
        rel=path.relative_to(ROOT).as_posix()
        data=path.read_bytes()
        item={'path':rel,'category':category(rel),'bytes':len(data),
              'sha256':hashlib.sha256(data).hexdigest(),'audit_depth':'inventory_only'}
        if path.suffix=='.py':
            try:
                tree=ast.parse(data.decode('utf-8'), filename=rel)
                item['syntax']='passed';item['function_defs']=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree))
                item['imports']=sum(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree))
                item['audit_depth']='syntax_and_module_structure; individual behavior not exhaustively executed'
            except (SyntaxError,UnicodeDecodeError) as exc:
                item['syntax']='ERROR:'+type(exc).__name__
        entries.append(item)
    counts=dict(Counter(e['category'] for e in entries))
    failures=[e['path'] for e in entries if e.get('syntax','passed').startswith('ERROR')]
    out={'build':'v4.9.66/v52','root':'CV_Ranker_Supervisor_Edition',
         'scope':'archive and Python parse inventory; NOT line-by-line forensic verification',
         'file_count_excluding_own_output':len(entries),'by_category':counts,
         'python_syntax_errors':failures,'entries':entries}
    DEST.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('inventory',len(entries),'by category',counts,'syntax_errors',len(failures))
    return bool(failures)
if __name__=='__main__':raise SystemExit(main())

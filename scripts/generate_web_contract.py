"""Offline OpenAPI-to-TypeScript DTO contract generator / CI drift guard.

No external npm generator required for the local release. This translates the
JSON Schema subset emitted by FastAPI/Pydantic and preserves schema metadata.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def ts_type(schema):
    if isinstance(schema,bool):return 'unknown' if schema else 'never'
    if '$ref' in schema:
        return 'TextileHRApi.'+schema['$ref'].rsplit('/',1)[-1]
    for operator in ('anyOf','oneOf'):
        if operator in schema:
            return ' | '.join(ts_type(x) for x in schema[operator])
    if 'enum' in schema:
        return ' | '.join(json.dumps(x,ensure_ascii=False) for x in schema['enum'])
    if 'const' in schema:
        return json.dumps(schema['const'],ensure_ascii=False)
    kind=schema.get('type')
    if isinstance(kind,list):return ' | '.join(ts_type({**schema,'type':t}) for t in kind)
    if kind=='string':return 'string'
    if kind=='number' or kind=='integer':return 'number'
    if kind=='boolean':return 'boolean'
    if kind=='null':return 'null'
    if kind=='array':return '('+ts_type(schema.get('items',{}))+')[]'
    if kind=='object':
        props=schema.get('properties') or {}
        if props:
            required=set(schema.get('required',[]))
            return '{'+' '.join(json.dumps(name)+((': ' if name in required else '?: '))+ts_type(value)+';' for name,value in props.items())+' }'
        return 'Record<string,'+ts_type(schema.get('additionalProperties',{}))+ '>'
    return 'unknown'


def generate():
    import sys
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    from backend.api import create_app
    # An OpenAPI schema query is non-generating and does not instantiate a model.
    from backend.storage import Store
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        schema=create_app(Store(Path(directory)),serve_frontend=False).openapi()
    services=schema.get('components',{}).get('schemas',{})
    lines=['/* AUTO-GENERATED: python scripts/generate_web_contract.py',
           ' * Source of truth: backend.api.create_app().openapi(). Do not hand-edit.',
           ' * This ambient namespace also supports the offline React TypeScript build.',
           ' */','declare namespace TextileHRApi {']
    for name,component in sorted(services.items()):
        desc=component.get('description','')
        if desc:lines.append('  /** '+desc[:240].replace('*/','')+' */')
        props=component.get('properties',{})
        if props:
            lines.append('  interface '+name+' {')
            required=set(component.get('required',[]))
            for key,val in props.items():
                if val.get('description'):lines.append('    /** '+val['description'][:150].replace('*/','')+' */')
                lines.append('    '+json.dumps(key)+('' if key in required else '?')+': '+ts_type(val)+';')
            lines.append('  }')
        else:lines.append('  type '+name+' = '+ts_type(component)+';')
    lines.append('  type HttpMethod = "get" | "post" | "put" | "patch" | "delete";')
    paths=[]
    for path,methods in sorted(schema['paths'].items()):
        for method,details in sorted(methods.items()):
            if method not in ('get','post','put','patch','delete'):continue
            paths.append((path,method,details.get('operationId',''),details.get('responses',{})))
    lines.append('  type ApiPath = '+' | '.join(json.dumps(p) for p in sorted(schema['paths']))+';')
    lines.append('  interface Operations {')
    for path,method,operation,responses in paths:
        success=next((v for k,v in responses.items() if str(k).startswith('2')),{})
        content=success.get('content',{}).get('application/json',{}).get('schema',{})
        response=ts_type(content)
        # The operation id is exported so change detection covers handlers
        lines.append('    '+json.dumps(operation)+': { method:'+json.dumps(method)+'; path:'+json.dumps(path)+'; response:'+response+' };')
    lines.extend(['  }','}',''])
    return schema,'\n'.join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    schema,typescript=generate()
    dest=ROOT/'frontend'/'src'/'api.generated.d.ts'
    spec=ROOT/'backend'/'openapi.generated.json'
    json_text=json.dumps(schema,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not dest.is_file() or dest.read_text()!=typescript or spec.read_text()!=json_text:
            raise SystemExit('OpenAPI/client drift. Re-run python scripts/generate_web_contract.py')
        print('OpenAPI and client DTOs match the API')
    else:
        dest.write_text(typescript)
        spec.write_text(json_text)
        print(f'Generated {len(schema["paths"])} API paths, {len(schema["components"]["schemas"])} DTOs')


if __name__=='__main__':main()

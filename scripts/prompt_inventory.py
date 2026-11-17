"""Produce a reproducible map of the thirteen runtime system prompt definitions.

This is source inspection, not evidence those prompts produced good decisions.
Run in the clean project directory; no network calls or private data.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "jd.py": ["SYSTEM_PROMPT", "CORRECTION_PROMPT"],
    "requirement_typing.py": ["TYPE_SYSTEM_PROMPT"],
    "unified.py": ["UNIFIED_PROMPT", "FINAL_ADJUDICATION_PROMPT"],
    "assessor.py": ["SYSTEM_PROMPT", "CORRECTION_PROMPT"],
    "semantic/decomposition.py": ["SYSTEM_PROMPT"],
    "semantic/transferability.py": ["SYSTEM_PROMPT", "COMPACT_SYSTEM_PROMPT", "BATCH_SYSTEM_PROMPT"],
    "ui/final_decisions.py": ["_JUDGE_PROMPT"],
    "condition_review.py": ["REVIEW_PROMPT"],
}
BUILDERS = {
    "jd.py": ["_user_prompt", "validate_jd_requirements"],
    "requirement_typing.py": ["enrich_ambiguous_types"],
    "assessor.py": ["_build_user_prompt", "_correct_invalid_rows", "_focused_abbreviation_recheck"],
    "unified.py": ["_payload", "_correction_payload", "plan_evidence_batches", "_independently_adjudicate"],
    "semantic/decomposition.py": ["create_shadow_search_plan"],
    "semantic/transferability.py": ["assess_transferability_shadow", "_assess_single_compact", "_assess_compact_jobs"],
    "ui/final_decisions.py": ["_judge_requirement"],
    "condition_review.py": ["review_compound_uncertainty"],
}


def inventory():
    rows=[]
    for relative, names in PROMPTS.items():
        content=(ROOT/'cv_ranker'/relative).read_text(encoding='utf-8')
        parsed=ast.parse(content)
        located={}
        for item in parsed.body:
            if isinstance(item, (ast.Assign,ast.AnnAssign)):
                targets = item.targets if isinstance(item,ast.Assign) else [item.target]
                for target in targets:
                    if isinstance(target, ast.Name): located[target.id]=item
        for name in names:
            obj=located.get(name)
            if obj is None:
                raise RuntimeError(f"Prompt definition not present: {relative}:{name}")
            exact=ast.get_source_segment(content,obj)
            rows.append({'path':'cv_ranker/'+relative,'name':name,'line':obj.lineno,
                         'assignment_sha256':hashlib.sha256(exact.encode()).hexdigest(),
                         'assignment_bytes':len(exact.encode())})
    builders=[]
    for relative,names in BUILDERS.items():
        content=(ROOT/'cv_ranker'/relative).read_text(encoding='utf-8')
        parsed=ast.parse(content)
        located={item.name:item for item in parsed.body if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef))}
        for name in names:
            obj=located.get(name)
            if obj:
                builders.append({'path':'cv_ranker/'+relative,'name':name,'line':obj.lineno})
            else:
                builders.append({'path':'cv_ranker/'+relative,'name':name,'status':'not_found_in_current_checkout'})
    return {'prompt_definitions':rows,'builders_to_review':builders,
            'scope':'source-level inventory, not a call count or quality benchmark'}

if __name__=='__main__':
    print(json.dumps(inventory(),indent=2))

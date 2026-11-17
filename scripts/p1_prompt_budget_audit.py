"""Offline P1 size and fictional request audit (not a model tokenizer or live evaluation).

Usage: python scripts/p1_prompt_budget_audit.py [output_file]
Only synthetic prompts, schemas and source excerpts are serialized. Never read .env.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cv_ranker.config import Settings
from cv_ranker.llm import estimate_tokens
from cv_ranker.jd import _user_prompt
from cv_ranker.assessor import _build_user_prompt
from cv_ranker.semantic.decomposition import _prompt as decomposition_prompt
from cv_ranker.segments import ResumeSegment
from cv_ranker.schemas import ValidatedRequirement, JDValidationResponse, LLMTypeResponse, LLMLiveThreeVerdictResponse
from cv_ranker.unified import _keyed_response_schema, _independent_response_schema
from cv_ranker.condition_review import ConditionReviewResponse
from cv_ranker.semantic.transferability import TransferabilityResponse,CompactTransferabilityResponse,CompactBatchResponse
from cv_ranker.semantic.decomposition import DecompositionResponse
from cv_ranker.ui.final_decisions import FocusedJudgment, CompactFocusedJudgment

PROMPTS = {
    "JD extraction": ("cv_ranker.jd", "SYSTEM_PROMPT", JDValidationResponse),
    "JD correction": ("cv_ranker.jd", "CORRECTION_PROMPT", JDValidationResponse),
    "Requirement typing": ("cv_ranker.requirement_typing", "TYPE_SYSTEM_PROMPT", LLMTypeResponse),
    "Unified primary": ("cv_ranker.unified", "UNIFIED_PROMPT", _keyed_response_schema(('R001',),strict_relation=True)),
    "Unified independent": ("cv_ranker.unified", "FINAL_ADJUDICATION_PROMPT", _independent_response_schema(('R001',))),
    "Legacy initial": ("cv_ranker.assessor", "SYSTEM_PROMPT", LLMLiveThreeVerdictResponse),
    "Legacy correction": ("cv_ranker.assessor", "CORRECTION_PROMPT", LLMLiveThreeVerdictResponse),
    "Compound review": ("cv_ranker.condition_review", "REVIEW_PROMPT", ConditionReviewResponse),
    "Search decomposition": ("cv_ranker.semantic.decomposition", "SYSTEM_PROMPT", DecompositionResponse),
    "Shadow full": ("cv_ranker.semantic.transferability", "SYSTEM_PROMPT", TransferabilityResponse),
    "Shadow compact": ("cv_ranker.semantic.transferability", "COMPACT_SYSTEM_PROMPT", CompactTransferabilityResponse),
    "Shadow batch": ("cv_ranker.semantic.transferability", "BATCH_SYSTEM_PROMPT", CompactBatchResponse),
    "Focused judge full": ("cv_ranker.ui.final_decisions", "_JUDGE_PROMPT", FocusedJudgment),
    "Focused judge compact suffix": ("cv_ranker.ui.final_decisions", "_JUDGE_PROMPT", CompactFocusedJudgment),
}

REQ = ValidatedRequirement(requirement_id='R001',name='Operate conveyor and document dispatch logs',
                           priority='required',jd_evidence='Operate conveyor and document dispatch logs')
SOURCE = ResumeSegment('S001','experience','Operated conveyor and documented dispatch logs for three months.')
JD = 'Required responsibilities:\nOperate conveyor and document dispatch logs'


def user_packet(stage):
    from cv_ranker import prompt_fragments as pf
    if stage.startswith('JD'): return _user_prompt(JD,[])
    if stage.startswith('Legacy'): return _build_user_prompt([REQ],[SOURCE])
    if stage == 'Search decomposition': return decomposition_prompt([REQ])
    if stage == 'Requirement typing':
        return pf.TYPING_USER_MESSAGE_PREFIX+'\n'+json.dumps({'requirements':[{'requirement_id':'R001','exact_jd_quote':REQ.jd_evidence}]})
    return json.dumps({
        'frozen_requirement':{'requirement_id':'R001','jd_quote':REQ.jd_evidence,'priority':'required'},
        'exact_cv_segments':[{'segment_id':'S001','section':'experience','text':SOURCE.text}],
        'illustrative_only':True},ensure_ascii=False)


def audit():
    local=Settings(llm_provider='ollama')
    cloud=Settings(llm_provider='openrouter',openrouter_api_key='synthetic-never-used')
    rows=[]
    sample={}
    for stage,(mod,name,schema) in PROMPTS.items():
        system=getattr(importlib.import_module(mod),name)
        if stage == 'Focused judge compact suffix':
            from cv_ranker import prompt_fragments as pf
            system+='\n'+pf.UI_COMPACT_SUFFIX
        user=user_packet(stage)
        schema_json=json.dumps(schema.model_json_schema(),sort_keys=True,ensure_ascii=False)
        size=estimate_tokens(system)+estimate_tokens(user)+estimate_tokens(schema_json)
        sample[stage]={'system_text':system,'user_text':user,'schema_name':schema.__name__,
            'schema':schema.model_json_schema()}
        rows.append({'stage':stage,'system_chars':len(system),'user_chars':len(user),
            'schema_chars':len(schema_json),'estimated_input_and_schema_tokens':size,
            'local_reserved_output_tokens':local.ollama_num_predict,
            'local_input_ceiling_tokens':local.ollama_num_ctx-local.ollama_num_predict,
            'local_remaining_for_real_source_tokens':local.ollama_num_ctx-local.ollama_num_predict-size,
            'cloud_reserved_output_tokens':cloud.openrouter_output_tokens,
            'cloud_input_ceiling_tokens':cloud.openrouter_context_tokens-cloud.openrouter_output_tokens,
            'cloud_remaining_for_real_source_tokens':cloud.openrouter_context_tokens-cloud.openrouter_output_tokens-size})
    return {'model_tokenization':'approximate estimate_tokens(len(text)/3.5), not model tokenizer',
            'packet_type':'fictional minimum; actual application calls must evaluate full source and budgets',
            'local_context':local.ollama_num_ctx,'cloud_context':cloud.openrouter_context_tokens,
            'summary':rows,'fictional_rendered_packets':sample}


if __name__=='__main__':
    destination=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/P1_FICTIONAL_PROMPT_BUDGET_AUDIT.json'
    destination.write_text(json.dumps(audit(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {destination} with {len(PROMPTS)} schema-specific fictional packets')
    for row in audit()['summary']:
        print(row['stage'],row['estimated_input_and_schema_tokens'],row['local_remaining_for_real_source_tokens'])

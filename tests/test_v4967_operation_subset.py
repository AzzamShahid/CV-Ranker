"""v53 per-operation dispatch correctness; all inputs are fictional."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from cv_ranker.operation_ledger import LocalOperationLedger
from cv_ranker.condition_review import review_compound_uncertainty,semantic_review_signature
from cv_ranker.config import Settings
from cv_ranker.schemas import (ValidatedRequirement, RequirementConstraint,
    RequirementAssessment, CompoundCheck, DecisionTransition, EvidenceCitation)
from cv_ranker.segments import segment_resume


def sig(s): return hashlib.sha256(s.encode()).hexdigest()


def make_rows(n=3):
    jd='Inspect fictional stock and document inventory adjustments.'
    cv='Experience\nInspected stock and documented inventory adjustments.'
    seg=next(s for s in segment_resume(cv) if 'Inspected stock' in s.text)
    rows=[]; reqs=[]
    for k in range(1,n+1):
        rid=f'R{k:03d}'
        req=ValidatedRequirement(requirement_id=rid,name=jd,jd_evidence=jd,priority='required')
        req.constraint=RequirementConstraint(kind='responsibility',operator='complex')
        reqs.append(req)
        rows.append(RequirementAssessment(requirement_id=rid,status='uncertain',
            unified_status='Unverified',assessment_state='unverified',
            evidence_ids=[seg.segment_id],evidence_segments=[EvidenceCitation(
                segment_id=seg.segment_id,section=seg.section,text=seg.text)],
            compound_check=CompoundCheck(operator='complex',outcome='needs_review'),
            decision_trace=[DecisionTransition(stage='compound_review',from_status='Found',
                to_status='Unverified',reason_code='jd_syntax_needs_review',
                evidence_ids=[seg.segment_id])]))
    return reqs,rows,cv


class Stub:
    settings=Settings()
    def __init__(self, *, omit=None):
        self.calls=0;self.outgoing=[];self.omit=omit
    def prompt_fits(self,*args):return True
    def invoke_structured(self, *, system_prompt,user_prompt,schema):
        self.calls+=1
        d=json.loads(user_prompt)
        self.outgoing.append([r['requirement_id'] for r in d['requirements']])
        rows=[{'requirement_id':r['requirement_id'], 'decision':'uncertain',
               'facets':[],'source_ids':[],'missing_parts':[],
               'reason':'Unresolved source-grounding ambiguity in synthetic report.'}
               for r in d['requirements'] if r['requirement_id']!=self.omit]
        return schema.model_validate({'assessments':rows})


def test_claim_each_completed_a_allows_fresh_b_without_overwriting_a(tmp_path):
    a,b=sig('a'),sig('b');path=tmp_path/'ledger.sqlite'
    with LocalOperationLedger(path) as ledger:
        assert ledger.claim_each([a]) == {a:'claimed_new'}
        ledger.finish_each({a:('validated_result',sig('trusted checkpoint'))})
        assert ledger.claim_each([a,b]) == {a:'validated_result',b:'claimed_new'}
        assert ledger.result_reference(a)==('validated_result',sig('trusted checkpoint'))
        assert ledger.result_reference(b)==('claimed_unknown_delivery',None)


def test_copied_legacy_v52_table_upgrades_without_erasing_status(tmp_path):
    file=tmp_path/'legacy.db';key=sig('old complete')
    conn=sqlite3.connect(file)
    conn.execute('CREATE TABLE operations(signature TEXT PRIMARY KEY,state TEXT NOT NULL,attempted_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT)')
    conn.execute('INSERT INTO operations(signature,state) VALUES (?,?)',(key,'validated_result'))
    conn.commit();conn.close()
    with LocalOperationLedger(file) as ledger:
        assert ledger.claim_each([key,sig('new')])[key]=='validated_result'
        assert ledger.state(sig('new'))=='claimed_unknown_delivery'
        assert ledger.result_reference(key)==('validated_result',None)


def test_overlapping_claims_give_at_most_one_owner_and_two_sibling_progress(tmp_path):
    path=tmp_path/'concurrent.db';a,b,c=map(sig,'abc')
    def worker(ids):
        with LocalOperationLedger(path) as ledger:
            return ledger.claim_each(ids)
    with ThreadPoolExecutor(max_workers=2) as pool:
        x,y=list(pool.map(worker,([a,b],[b,c])))
    assert sum(row[b]=='claimed_new' for row in [x,y])==1
    assert x[a]=='claimed_new' and y[c]=='claimed_new'
    with LocalOperationLedger(path) as ledger:
        assert all(ledger.state(key)=='claimed_unknown_delivery' for key in (a,b,c))


def test_batch_with_old_a_only_dispatches_b_and_marks_b(tmp_path):
    reqs,rows,cv=make_rows(2);m=Stub();path=tmp_path/'ledger.db'
    sa=semantic_review_signature(reqs[0],cv,m)
    sb=semantic_review_signature(reqs[1],cv,m)
    with LocalOperationLedger(path) as ledger:
        ledger.claim_each([sa]);ledger.finish_each({sa:('validated_result',sig('old checkpoint'))})
    result,stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
        resume_text=cv,llm=m,ledger_path=path,correction_budget=0)
    assert m.calls==stats.attempted==1 and m.outgoing==[['R002']]
    assert result[0].condition_review_attempt_signature is None
    assert result[1].condition_review_attempt_signature==sb
    with LocalOperationLedger(path) as ledger:
        assert ledger.state(sa)=='validated_result'
        assert ledger.state(sb)=='invalid_response'


def test_unknown_delivery_a_does_not_block_b_after_real_process_restart(tmp_path):
    reqs,rows,cv=make_rows(2);m=Stub();path=tmp_path/'ledger.db'
    a=semantic_review_signature(reqs[0],cv,m)
    code=('import sys;from cv_ranker.operation_ledger import LocalOperationLedger;'
          'l=LocalOperationLedger(sys.argv[1]);l.claim_each([sys.argv[2]]);'
          'l.finish_each({sys.argv[2]:("provider_unknown_delivery",None)});l.close()')
    subprocess.run([sys.executable,'-c',code,str(path),a],check=True)
    result,stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
        resume_text=cv,llm=m,ledger_path=path,correction_budget=0)
    assert stats.attempted==1 and m.outgoing==[['R002']]
    assert result[0].condition_review_attempt_signature is None
    with LocalOperationLedger(path) as ledger:
        assert ledger.state(a)=='provider_unknown_delivery'


def test_batch_limit_skips_blocked_and_dispatches_two_fresh_siblings(tmp_path):
    reqs,rows,cv=make_rows(4);m=Stub();path=tmp_path/'ledger.db'
    a=semantic_review_signature(reqs[0],cv,m);b=semantic_review_signature(reqs[1],cv,m)
    with LocalOperationLedger(path) as ledger:
        ledger.claim_each([a,b]);ledger.finish_each({a:('validated_result',None),b:('invalid_response',None)})
    reviewed,stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
        resume_text=cv,llm=m,ledger_path=path,max_items=2,correction_budget=0)
    assert stats.attempted==1 and m.outgoing==[['R003','R004']]
    assert not reviewed[0].condition_review_attempt_signature
    assert not reviewed[1].condition_review_attempt_signature
    assert reviewed[2].condition_review_attempt_signature
    assert reviewed[3].condition_review_attempt_signature


def test_malformed_sibling_does_not_erase_existing_verified_a(tmp_path):
    reqs,rows,cv=make_rows(3);m=Stub(omit='R003');path=tmp_path/'ledger.db'
    a=semantic_review_signature(reqs[0],cv,m)
    with LocalOperationLedger(path) as ledger:
        ledger.claim_each([a]);ledger.finish_each({a:('validated_result',sig('prior verified'))})
    result,stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
        resume_text=cv,llm=m,ledger_path=path,correction_budget=0)
    assert stats.attempted==1 and m.outgoing==[['R002','R003']]
    assert result[0].condition_review_attempt_signature is None
    assert stats.pending==3
    with LocalOperationLedger(path) as ledger:
        assert ledger.state(a)=='validated_result'
        assert ledger.state(semantic_review_signature(reqs[1],cv,m))=='invalid_response'
        assert ledger.state(semantic_review_signature(reqs[2],cv,m))=='invalid_response'


def test_validated_sibling_can_commit_when_other_model_row_missing(tmp_path):
    """Distinct rows in one response are processed individually."""
    reqs,rows,cv=make_rows(2);path=tmp_path/'ledger.db'
    class PartialValid(Stub):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls+=1
            packet=json.loads(user_prompt)
            self.outgoing.append([r['requirement_id'] for r in packet['requirements']])
            sid=next(x['id'] for x in packet['sources'] if 'Inspected stock' in x['text'])
            return schema.model_validate({'assessments':[{
                'requirement_id':'R001','decision':'found','source_ids':[sid],
                'missing_parts':[],
                'facets':[
                    {'jd_exact_span':'Inspect fictional stock','relation':'satisfied','source_ids':[sid],
                     'explanation':'Candidate completed an inspection of the fictional stock.'},
                    {'jd_exact_span':'document inventory adjustments.','relation':'satisfied','source_ids':[sid],
                     'explanation':'Candidate documented inventory stock adjustments.'}],
                'reason':'Both required source tasks were completed.'}]})
    m=PartialValid()
    result,stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
                                             resume_text=cv,llm=m,ledger_path=path,correction_budget=0)
    assert stats.attempted==1 and stats.resolved==1
    assert result[0].unified_status=='Found'
    assert result[1].assessment_state=='unverified'
    with LocalOperationLedger(path) as ledger:
        a,b=(semantic_review_signature(req,cv,m) for req in reqs)
        assert ledger.state(a)=='validated_result' and ledger.result_reference(a)[1]
        assert ledger.state(b)=='invalid_response'


def test_changed_schema_or_provider_parameters_changes_semantic_signature():
    reqs,rows,cv=make_rows(1)
    a=Stub();sa=semantic_review_signature(reqs[0],cv,a)
    b=Stub();b.settings=Settings(ollama_num_ctx=16384)
    sb=semantic_review_signature(reqs[0],cv,b)
    assert sa!=sb
    assert sa==semantic_review_signature(reqs[0],cv,a)


def test_malformed_json_row_does_not_erase_independently_valid_sibling(tmp_path):
    reqs,rows,cv=make_rows(2);path=tmp_path/'ledger.db'
    class PartiallyMalformed(Stub):
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls+=1
            self.outgoing.append([x['requirement_id'] for x in json.loads(user_prompt)['requirements']])
            sid=next(x['id'] for x in json.loads(user_prompt)['sources'] if 'Inspected stock' in x['text'])
            return {'assessments':[
                {'requirement_id':'R001','decision':'found','source_ids':[sid],
                 'missing_parts':[], 'facets':[
                   {'jd_exact_span':'Inspect fictional stock','relation':'satisfied','source_ids':[sid],
                    'explanation':'Inspected stock originally documented by this candidate.'},
                   {'jd_exact_span':'document inventory adjustments.','relation':'satisfied',
                    'source_ids':[sid],'explanation':'Documented genuine inventory changes.'}],
                 'reason':'Both original JD actions documented in original candidate records.'},
                {'requirement_id':'R002','decision':'not_a_schema_decision',
                 'source_ids':[sid], 'facets':[], 'reason':'unusable malformed item'}]}
    m=PartiallyMalformed()
    checked, stats=review_compound_uncertainty(requirements=reqs,assessments=rows,
            resume_text=cv,llm=m,ledger_path=path,correction_budget=0)
    assert stats.resolved==1 and stats.attempted==1
    assert checked[0].unified_status=='Found'
    assert checked[1].unified_status=='Unverified'
    assert any('failed the condition-review response schema' in x for x in stats.notices)

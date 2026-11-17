"""Read-only differential probes. Synthetic inputs and no cloud/model calls.

Executed in independent processes with PYTHONPATH pointed at baseline or
candidate. No import reload; print module source path and SHA to prove roots.
"""
from __future__ import annotations
import hashlib,json,os,platform,sys,tempfile
from pathlib import Path
from cv_ranker import weighted_scoring
from cv_ranker.schemas import (ValidatedRequirement,RequirementAssessment,RankingReport,
    RequirementConstraint,CompoundCheck,DecisionTransition,EvidenceCitation)
from cv_ranker.scoring import score_candidate
from cv_ranker.weighted_scoring import (ScoreWeights,weighted_candidate,provisional_score_bounds,
    rebalance_requirement_share,even_requirement_shares)
from cv_ranker.semantic.cache import SQLiteVectorCache
from cv_ranker.pipeline import CVRanker
from cv_ranker.config import Settings
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.schemas import JDReviewDraft
from cv_ranker.segments import segment_resume
from cv_ranker.condition_review import review_compound_uncertainty
import cv_ranker.build_info as identity


def req(i,p='required'):
 return ValidatedRequirement(requirement_id=i,name='Do fictional task '+i,
    jd_evidence='Do fictional task '+i, priority=p)


def result(items,vals):
 candidate=score_candidate(candidate_name='Synthetic',requirements=items,
    assessments=vals,evaluation_mode='llm_assessed',errors=[])
 report=RankingReport(job_description_source='fictional',jd_validation_mode='manual',
    requirements=items,candidates=[candidate],yake_candidates=[])
 return report,candidate



def _mixed_operation_probe():
    """Only fictional sources. A completed A must not block fresh B."""
    try:
        from cv_ranker.operation_ledger import LocalOperationLedger
    except ImportError:
        return {"legacy_without_operation_ledger": True}
    from cv_ranker.condition_review import semantic_review_signature
    from cv_ranker.schemas import RequirementConstraint
    from cv_ranker.config import Settings
    from cv_ranker.segments import segment_resume
    from cv_ranker.schemas import EvidenceCitation, CompoundCheck, DecisionTransition
    jd='Inspect stock movements and document inventory adjustments.'
    cv='Experience\nInspected stock movements and documented inventory adjustments.'
    rows=[];requirements=[]
    for rid in ('R001','R002'):
        req=ValidatedRequirement(requirement_id=rid,name=jd,jd_evidence=jd,priority='required')
        req.constraint=RequirementConstraint(kind='responsibility',operator='complex')
        requirements.append(req)
        cited=next(x for x in segment_resume(cv) if 'Inspected stock' in x.text)
        rows.append(RequirementAssessment(requirement_id=rid,status='uncertain',
            unified_status='Unverified',assessment_state='unverified',
            evidence_ids=[cited.segment_id],evidence_segments=[EvidenceCitation(
                segment_id=cited.segment_id,section=cited.section,text=cited.text)],
            compound_check=CompoundCheck(operator='complex',outcome='needs_review'),
            decision_trace=[DecisionTransition(stage='compound_review',from_status='Found',
                to_status='Unverified',reason_code='jd_syntax_needs_review',
                evidence_ids=[cited.segment_id])]))
    class Stub:
        settings=Settings()
        calls=0
        outgoing=[]
        def prompt_fits(self,*a):return True
        def invoke_structured(self,*,system_prompt,user_prompt,schema):
            self.calls+=1
            packet=json.loads(user_prompt)
            self.outgoing=[i['requirement_id'] for i in packet['requirements']]
            return schema.model_validate({'assessments':[
                {'requirement_id':rid,'decision':'uncertain','facets':[],
                 'source_ids':[], 'missing_parts':[],
                 'reason':'No source-grounded final conclusion was established.'}
                for rid in self.outgoing]})
    stub=Stub()
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/'local_ops.sqlite'
        signature_a=semantic_review_signature(requirements[0],cv,stub)
        signature_b=semantic_review_signature(requirements[1],cv,stub)
        with LocalOperationLedger(db) as ledger:
            ledger.claim_many([signature_a])
            ledger.finish_many([signature_a],'validated_result')
        output,stats=review_compound_uncertainty(requirements=requirements,
            assessments=rows,resume_text=cv,llm=stub,ledger_path=db)
        with LocalOperationLedger(db) as ledger:
            b_state=ledger.state(signature_b)
        return {'calls':stub.calls,'outgoing':stub.outgoing,
            'A_marked_attempted':bool(output[0].condition_review_attempt_signature),
            'B_marked_attempted':bool(output[1].condition_review_attempt_signature),
            'B_state':b_state,'reported_attempts':stats.attempted}

def check():
 x={}
 r=[req('R001'),req('R002','preferred')]
 c=[RequirementAssessment(requirement_id='R001',status='matched',unified_status='Found'),
    RequirementAssessment(requirement_id='R002',status='uncertain',unified_status='Unverified',assessment_state='unverified')]
 report,candidate=result(r,c)
 w=ScoreWeights(0,0,100,jd_allocation_mode='weighted_split',required_share=90)
 main=weighted_candidate(report,candidate,w)['score']
 floor=provisional_score_bounds(report,candidate,w)['verified_floor']
 x['RECENT-001']={'main_floor':main,'reported_bounds_floor':floor,'consistent':main==floor}
 r2=[req('R001','unknown'),req('R002','preferred')]
 report2,candidate2=result(r2,c)
 try:
  sc=weighted_candidate(report2,candidate2,w)
  x['RECENT-002']={'score':sc['score'],'original_priority':sc['requirement_contributions'][0]['priority'],'crash':False}
 except Exception as e:
  x['RECENT-002']={'crash':type(e).__name__}
 from cv_ranker.semantic.embedding import EmbeddingError
 with tempfile.TemporaryDirectory() as t:
  with SQLiteVectorCache(Path(t)/'vectors.sqlite') as cache:
   cache._conn.execute('INSERT INTO embeddings VALUES(?,?,?)',('malformed',2,'not bytes'))
   cache._conn.commit()
   try:cache.get('malformed'); outcome='ACCEPTED_BAD_VALUE'
   except Exception as e:outcome=type(e).__name__
  x['RECENT-003']={'result':outcome}
 shares=even_requirement_shares(r)
 outcomes={}
 for z in (-.001,100.001):
  try:rebalance_requirement_share(r,shares,'R001',z);outcomes[str(z)]='ACCEPTED'
  except Exception as e:outcomes[str(z)]=type(e).__name__
 x['RECENT-004']=outcomes
 # Semantics review, old and new schema share the same approved mandatory/group fields.
 jd='Use ERP or MES for reporting'
 r=ValidatedRequirement(requirement_id='R001',name=jd,priority='required',jd_evidence=jd)
 r.constraint=RequirementConstraint(kind='responsibility',operator='complex',
          approved_mandatory_parts=['Use','for reporting'],
          approved_alternative_groups=[['ERP','MES']])
 cv='Experience\nUsed ERP for reporting in production.'
 seg=next(s for s in segment_resume(cv) if 'Used ERP' in s.text)
 citation=EvidenceCitation(segment_id=seg.segment_id,section=seg.section,text=seg.text)
 prior=RequirementAssessment(requirement_id='R001',status='uncertain',unified_status='Unverified',
    assessment_state='unverified',compound_check=CompoundCheck(operator='complex',outcome='needs_review'),
    evidence_ids=[seg.segment_id],evidence_segments=[citation],
    decision_trace=[DecisionTransition(stage='compound_review',from_status='Found',
              to_status='Unverified',reason_code='jd_syntax_needs_review',evidence_ids=[seg.segment_id])])
 class Model:
  def prompt_fits(self,*a):return True
  def invoke_structured(self,*,system_prompt,user_prompt,schema):
   return schema.model_validate({'assessments':[{'requirement_id':'R001','decision':'found',
    'source_ids':[seg.segment_id],'missing_parts':['MES'],
    'reason':'ERP reporting is demonstrated and unused MES branch is optional.',
    'facets':[{'jd_exact_span':part,'relation':relation,
      'source_ids':[seg.segment_id] if relation=='satisfied' else [],
      'explanation':'Original source was inspected for this condition.'}
      for part,relation in [('Use','satisfied'),('ERP','satisfied'),('MES','missing'),('for reporting','satisfied')]]}]})
 rows,stats=review_compound_uncertainty(requirements=[r],assessments=[prior],resume_text=cv,llm=Model())
 # Explicit reviewer annotations must not be bypassed by the gerund / lexical helper.
 from cv_ranker.compound_validation import apply_compound_checks
 review_jd='Inspect damaged stock and document corrective action.'
 rm=ValidatedRequirement(requirement_id='R001',name=review_jd,priority='required',jd_evidence=review_jd)
 rm.constraint=RequirementConstraint(kind='responsibility',operator='all_of',
     options=['Inspect damaged stock','document corrective action'],
     approved_mandatory_parts=['Inspect damaged stock','document corrective action'])
 completed='Experience\nInspected damaged stock and documented corrective actions.'
 evidence=next(s for s in segment_resume(completed) if 'Inspected damaged' in s.text)
 cited=EvidenceCitation(segment_id=evidence.segment_id,section=evidence.section,text=evidence.text)
 old=RequirementAssessment(requirement_id='R001',status='matched',unified_status='Found',
      evidence_ids=[evidence.segment_id],evidence_segments=[cited])
 checked,_,_=apply_compound_checks(requirements=[rm],assessments=[old],resume_text=completed)
 x['RECENT-005']={'initial_status':old.status,'checked_status':checked[0].status,
      'verified':checked[0].assessment_state=='verified',
      'requires_condition_review':checked[0].compound_check is not None and
        checked[0].compound_check.outcome=='needs_review'}
 x['RECENT-006']={'verdict':rows[0].unified_status,'resolved':stats.resolved}
 x['RECENT-007']={'proof_component_count':len(rows[0].compound_check.components)}
 # Missing slot in resumed batch triggers pre-loop hashing in v51.
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);job=root/'jd.txt';job.write_text('Operate simulated production tools')
  a=root/'good.txt';a.write_text('Experience\nOperated simulated production tools')
  missing=root/'missing.txt'
  rr=req('R001');rr.name='Operate simulated production tools';rr.jd_evidence=rr.name
  approved=JDReviewDraft(jd_sha256=jd_source_sha256(job.read_text()),yake_candidates=[],
     requirements=[rr],jd_validation_mode='manual',approved=True)
  engine=CVRanker(settings=Settings(),use_llm=False)
  try:
   old=engine.run(job,[a],approved_jd=approved)
   final=engine.run(job,[a,missing],resume_report=old,resume_candidates={})
   x['RECENT-008']={'fatal':False,'candidate_count':len(final.candidates),
     'missing_is_failed':any(item.candidate_name=='missing.txt' and item.evaluation_mode=='failed' for item in final.candidates)}
  except Exception as e:x['RECENT-008']={'fatal':type(e).__name__}
 x['NEXT-001']=_mixed_operation_probe()
 return x


if __name__=='__main__':
 f=Path(weighted_scoring.__file__)
 print(json.dumps({'build':identity.BUILD_ID,'protocol':identity.ASSESSMENT_PROTOCOL_VERSION,
  'loaded_module':str(f),'module_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
  'python':sys.version.split()[0],'os':platform.platform(),
  'probes':check()},indent=2,sort_keys=True))

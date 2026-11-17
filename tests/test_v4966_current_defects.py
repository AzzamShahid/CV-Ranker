"""Source-specific v51 → v52 controls (fictional, offline, no cloud calls)."""
from __future__ import annotations
import io, json, math, sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile
import pytest

from cv_ranker.schemas import (ValidatedRequirement, RequirementAssessment, RankingReport,
    RequirementConstraint, JDConditionNode, EvidenceCitation, DecisionTransition, CompoundCheck)
from cv_ranker.scoring import score_candidate
from cv_ranker.weighted_scoring import (ScoreWeights, weighted_candidate, provisional_score_bounds,
    weighted_leaderboard, rebalance_requirement_share, even_requirement_shares)
from cv_ranker.semantic.cache import SQLiteVectorCache
from cv_ranker.semantic.embedding import EmbeddingError
from cv_ranker.jd_expression import evaluate_expression, validate_expression
from cv_ranker.condition_review import review_compound_uncertainty
from cv_ranker.segments import segment_resume
from cv_ranker.source_snapshot import read_candidate_snapshot
from cv_ranker.documents import DocumentError, extract_text
from cv_ranker.report_bundle import complete_results_zip


def requirement(rid, priority='required', evidence=None):
    source=evidence or f'Demonstrate capability {rid}'
    return ValidatedRequirement(requirement_id=rid,name=source,jd_evidence=source,priority=priority)


def report_with(reqs, rows):
    candidate=score_candidate(candidate_name='Fictional.txt',requirements=reqs,
        assessments=rows,evaluation_mode='llm_assessed',errors=[])
    report=RankingReport(job_description_source='f.txt',jd_validation_mode='manual',
        requirements=reqs,candidates=[candidate],yake_candidates=[])
    return report,candidate


def row(rid,status='matched',unverified=False):
    return RequirementAssessment(requirement_id=rid,status='uncertain' if unverified else status,
       unified_status='Unverified' if unverified else 'Found' if status=='matched' else 'Not Found',
       assessment_state='unverified' if unverified else 'verified')


def test_RECENT001_provisional_bounds_share_exact_split_formula_and_do_not_mutate_candidate():
    req=[requirement('R001'),requirement('R002','preferred')]
    report,c=report_with(req,[row('R001'),row('R002',unverified=True)])
    original=c.model_dump()
    for share in (90,10,0,100):
        w=ScoreWeights(0,0,100,jd_allocation_mode='weighted_split',required_share=share)
        primary=weighted_candidate(report,c,w)
        bounds=provisional_score_bounds(report,c,w)
        assert bounds['verified_floor']==primary['score']
        assert bounds['possible_ceiling']==primary['possible_ceiling']
        assert primary['provisional'] and c.model_dump()==original
    assert provisional_score_bounds(report,c,ScoreWeights(0,0,100,jd_allocation_mode='weighted_split',required_share=90))['verified_floor']==90


def test_RECENT001_missing_row_has_provisional_floor_but_no_completed_assessment_is_unavailable():
    req=[requirement('R001'),requirement('R002','preferred')]
    report,c=report_with(req,[row('R001')]) if False else (None,None)
    # Built directly to preserve an intentionally incomplete historical input.
    full,_=report_with(req,[row('R001'),row('R002',unverified=True)])
    partial=full.candidates[0].model_copy(update={'assessments':[row('R001')]})
    original=partial.model_dump()
    w=ScoreWeights(0,0,100)
    assert weighted_candidate(full,partial,w)['possible_ceiling']==100
    assert weighted_candidate(full,partial,w)['score']==50
    assert partial.model_dump()==original
    empty=partial.model_copy(update={'assessments':[],'primary_score':None})
    assert weighted_candidate(full,empty,w)['score'] is None
    assert weighted_leaderboard(full.model_copy(update={'candidates':[empty]}),w)[0]['score_status']=='Unavailable'


def test_RECENT002_unknown_priority_uses_required_group_but_preserves_label():
    req=[requirement('R001','unknown'),requirement('R002','preferred')]
    report,c=report_with(req,[row('R001'),row('R002','not_matched')])
    for share in (90,10,100,0):
        w=ScoreWeights(0,0,100,jd_allocation_mode='weighted_split',required_share=share)
        outcome=weighted_candidate(report,c,w)
        assert outcome['score'] == share
        assert outcome['requirement_contributions'][0]['priority']=='unknown'
        assert sum(x['possible_points'] for x in outcome['requirement_contributions']) == 100


def test_RECENT003_SQLite_malformed_values_are_key_local_typed_corruption(tmp_path):
    with SQLiteVectorCache(tmp_path/'vectors.sqlite') as cache:
        import numpy as np
        cache.put('healthy',np.asarray([3.0,4.0],dtype='float32'))
        malformed=[('text',2,'4 characters'),('short',2,b'123'),
                   ('negative',-1,b'1234'),('zero',0,b''),('huge',999999999,b'1234')]
        for k,d,b in malformed:
            cache._conn.execute('INSERT INTO embeddings VALUES(?,?,?)',(k,d,b))
        cache._conn.commit()
        for k,_,_ in malformed:
            with pytest.raises(EmbeddingError,match='Corrupted'):
                cache.get(k)
        assert cache.get('healthy').shape==(2,)


@pytest.mark.parametrize('value',[-0.001,100.001,-1,101,True,float('nan'),float('inf'),-float('inf'),'50'])
def test_RECENT004_reject_raw_invalid_shares_without_mutation(value):
    req=[requirement('R001'),requirement('R002')]
    shares=even_requirement_shares(req)
    before=dict(shares)
    with pytest.raises(ValueError):
        rebalance_requirement_share(req,shares,'R001',value)
    assert shares==before


def leaf(jd, text, occurrence=0):
    start=0
    for _ in range(occurrence+1):
        start=jd.index(text,start)
        start+=1
    start-=1
    return JDConditionNode(op='leaf',text=text,start=start,end=start+len(text))


def build_review(jd,expr,source):
    r=requirement('R001',evidence=jd)
    validate_expression(expr,jd)
    r.constraint=RequirementConstraint(kind='responsibility',operator='complex',
        approved_expression=expr,evidence_modality='performed_work',requires_review=False)
    cv='Experience\n'+source
    seg=next(s for s in segment_resume(cv) if source in s.text)
    ev=EvidenceCitation(segment_id=seg.segment_id,section=seg.section,text=seg.text)
    prior=RequirementAssessment(requirement_id='R001',status='uncertain',unified_status='Unverified',
        assessment_state='unverified',compound_check=CompoundCheck(operator='complex',outcome='needs_review'),
        evidence_ids=[seg.segment_id],evidence_segments=[ev],
        decision_trace=[DecisionTransition(stage='compound_review',from_status='Found',
                  to_status='Unverified',reason_code='jd_syntax_needs_review',evidence_ids=[seg.segment_id])])
    return r,cv,prior,seg.segment_id


class OneModel:
    def __init__(self,assessment):self.assessment=assessment;self.calls=0
    def prompt_fits(self,*_):return True
    def invoke_structured(self,*,system_prompt,user_prompt,schema):
        self.calls+=1
        return schema.model_validate({'assessments':[self.assessment]})


def model_reply(r,expr,sid,state_by_text,*,missing=(),fake_quote=None):
    facets=[]
    def gather(node):
        if node.op=='leaf':
            state=state_by_text.get(node.text,'missing')
            facets.append({'jd_exact_span':node.text,'jd_start':node.start,'jd_end':node.end,
                'relation':state,'source_ids':[sid] if state=='satisfied' else [],
                'proof_quotes':[{'source_id':sid,'quote':fake_quote or 'applied the documented procedure'}]
                                if state=='satisfied' else [],
                'explanation':'Original candidate passage examined independently.'})
        else:
            for child in node.children:gather(child)
    gather(expr)
    return {'requirement_id':'R001','decision':'found','source_ids':[sid],
        'facets':facets,'missing_parts':list(missing),
        'reason':'Independent review linked the original candidate evidence and employer obligations.'}


def test_RECENT006_unused_or_branch_missing_does_not_veto_satisfied_nested_expression():
    jd='Deploy service A or (service B and audit C)'
    a,b,c=(leaf(jd,x) for x in ('Deploy service A','service B','audit C'))
    expr=JDConditionNode(op='any_of',children=[a,JDConditionNode(op='all_of',children=[b,c])])
    source='I applied the documented procedure while deploying service A.'
    r,cv,prior,sid=build_review(jd,expr,source)
    assessment=model_reply(r,expr,sid,{a.text:'satisfied'},missing=[b.text,c.text],fake_quote='applied the documented procedure')
    reviewed,stats=review_compound_uncertainty(requirements=[r],assessments=[prior],
        resume_text=cv,llm=OneModel(assessment))
    assert stats.resolved==1 and reviewed[0].unified_status=='Found'
    assert len(reviewed[0].compound_check.components)==3
    assert reviewed[0].compound_check.components[1].relation=='missing'
    assert reviewed[0].compound_check.components[0].evidence[0].segment_id==sid
    serialized=RequirementAssessment.model_validate(reviewed[0].model_dump())
    assert serialized.compound_check.components[1].group_role=='alternative'
    assert serialized.compound_check.components[1].jd_start==b.start


def test_RECENT006_missing_mandatory_sibling_denies_direct_and_false_source_quote_denies_proof():
    jd='(Run pipeline A or pipeline B) and record output C'
    a,b,c=(leaf(jd,x) for x in ('Run pipeline A','pipeline B','record output C'))
    expr=JDConditionNode(op='all_of',children=[JDConditionNode(op='any_of',children=[a,b]),c])
    r,cv,prior,sid=build_review(jd,expr,'I applied the documented procedure while running pipeline A.')
    missing=model_reply(r,expr,sid,{a.text:'satisfied'},missing=[b.text,c.text])
    first,stats=review_compound_uncertainty(requirements=[r],assessments=[prior],resume_text=cv,llm=OneModel(missing))
    assert stats.resolved==0 and first[0].unified_status=='Unverified'
    fake=model_reply(r,expr,sid,{a.text:'satisfied',c.text:'satisfied'},
       missing=[b.text],fake_quote='invented CV sentence not present in actual source')
    second,stats=review_compound_uncertainty(requirements=[r],assessments=[prior],resume_text=cv,llm=OneModel(fake))
    assert stats.resolved==0 and second[0].unified_status=='Unverified'


def test_RECENT005_approved_expression_routes_initial_found_to_independent_review():
    from cv_ranker.compound_validation import apply_compound_checks
    jd='Perform audit A and document result B'
    a,b=(leaf(jd,t) for t in ('Perform audit A','document result B'))
    expr=JDConditionNode(op='all_of',children=[a,b])
    r,cv,prior,sid=build_review(jd,expr,'I performed the documented procedure.')
    before=prior.model_copy(update={'status':'matched','unified_status':'Found',
                                    'assessment_state':'verified','compound_check':None,'decision_trace':[]})
    inspected,_,_=apply_compound_checks(requirements=[r],assessments=[before],resume_text=cv)
    assert inspected[0].assessment_state=='unverified'
    assert inspected[0].unified_status is None
    assert inspected[0].current_decision.processing_state == 'pending'
    assert inspected[0].decision_trace[-1].reason_code=='jd_syntax_needs_review'


def test_RECENT008_same_bytes_for_snapshot_and_digest_despite_source_replacement(tmp_path,monkeypatch):
    from cv_ranker.resume import candidate_resume_key
    from cv_ranker import source_snapshot
    source=tmp_path/'resume.txt';old=b'Experience\nOriginal finished duty.';source.write_bytes(old)
    real=source_snapshot.extract_text
    def replacing(path):
        source.write_text('Experience\nDifferent source after snapshot.')
        return real(path)
    monkeypatch.setattr(source_snapshot,'extract_text',replacing)
    text,digest=read_candidate_snapshot(source)
    assert 'Original finished duty' in text
    assert digest==candidate_resume_key(source.name,old)
    assert 'Different source' not in text


def test_RECENT008_unreadable_slot_does_not_abort_healthy_candidates(tmp_path):
    from cv_ranker.pipeline import CVRanker
    from cv_ranker.config import Settings
    from cv_ranker.eligibility import jd_source_sha256
    from cv_ranker.schemas import JDReviewDraft
    jd='Required capability: operate machinery.'
    j=tmp_path/'jd.txt';j.write_text(jd)
    paths=[]
    for n in ('good1.txt','missing.txt','good2.txt'):
        p=tmp_path/n
        if n!='missing.txt':p.write_text('Experience\nI operate machinery and log results.')
        paths.append(p)
    r=requirement('R001',evidence='operate machinery')
    approved=JDReviewDraft(jd_sha256=jd_source_sha256(jd),requirements=[r],
        yake_candidates=[],jd_validation_mode='manual',approved=True)
    ranker=CVRanker(settings=Settings(),use_llm=False)
    report=ranker.run(j,paths,approved_jd=approved)
    assert len(report.candidates)==3
    indexed={c.candidate_name:c for c in report.candidates}
    assert indexed['missing.txt'].evaluation_mode=='failed'
    assert indexed['missing.txt'].primary_score is None
    assert indexed['good1.txt'].evaluation_mode!='failed'
    assert indexed['good2.txt'].evaluation_mode!='failed'

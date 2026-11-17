"""Blinded benchmark schema can validate labels, not manufacture model accuracy."""
from __future__ import annotations
import hashlib,json
import pytest
from evaluation.independent_gold import GoldCase,GoldReview,validate_gold_cases,validate_gold_jsonl


def sha(x):return hashlib.sha256(x.encode()).hexdigest()


def make(n,split='development',different=False):
    return GoldCase(case_id=f'case{n}',job_family='fictional operations',
      document_group=f'docgroup{n}',wording_family=f'wordgroup{n}',
      candidate_sha256=sha(f'candidate{n}'),jd_sha256=sha(f'JD{n}'),
      requirement_id='R001',split=split,
      reviews=[GoldReview(reviewer_id='expert-A',verdict='Found',evidence_ids=['S001'],
                          reason='Source proves exact requirement duty.'),
               GoldReview(reviewer_id='expert-B',verdict='Not Found' if different else 'Found',
                          evidence_ids=['S001'],reason='Independent second reading of the CV.')],
      adjudicated=(GoldReview(reviewer_id='expert-C',verdict='Unverified',
                evidence_ids=[],reason='Human adjudicator found a source ambiguity.')
                  if different else None))


def test_blinded_independently_adjudicated_cases_can_be_counted_without_model():
    rows=[make(1),make(2,'holdout',different=True)]
    result=validate_gold_cases(rows)
    assert result['case_count']==2
    assert result['disagreements_adjudicated']==1
    assert result['model_accuracy'] is None and result['live_provider_metrics'] is None


def test_same_reviewer_and_unblinded_gold_are_rejected():
    item=make(1).model_dump()
    item['reviews'][1]['reviewer_id']='expert-A'
    with pytest.raises(ValueError,match='distinct reviewers'):
        GoldCase.model_validate(item)
    item=make(1).model_dump();item['reviews'][0]['model_result_visible']=True
    with pytest.raises(ValueError,match='blinded'):
        GoldCase.model_validate(item)


def test_disagreement_requires_independent_adjudication():
    item=make(1).model_dump();item['reviews'][1]['verdict']='Not Found'
    with pytest.raises(ValueError,match='Adjudication required'):
        GoldCase.model_validate(item)


def test_holdout_does_not_share_document_candidate_jd_or_word_family():
    a=make(1); b=make(2,'holdout')
    for field in ('document_group','candidate_sha256','jd_sha256','wording_family'):
        changed=b.model_copy(update={field:getattr(a,field)})
        with pytest.raises(ValueError,match='leakage'):
            validate_gold_cases([a,changed])


def test_jsonl_handoff_rejects_missing_review_and_supports_readback(tmp_path):
    path=tmp_path/'gold.jsonl'
    path.write_text(json.dumps(make(1).model_dump())+'\n')
    assert validate_gold_jsonl(path)['case_count']==1
    path.write_text(json.dumps({'case_id':'test-2'})+'\n')
    with pytest.raises(ValueError):validate_gold_jsonl(path)

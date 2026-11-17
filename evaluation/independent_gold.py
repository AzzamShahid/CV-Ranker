"""Offline preflight for independently labeled multi-department JD/CV gold.

This module DOES NOT generate reference labels from model responses. It checks
reviewer independence, split leakage and conflicts before authorized provider
inference. Raw applicant text is not needed by the validator.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GoldReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer_id: str = Field(min_length=2)
    verdict: Literal['Found','Transferable','Not Found','Unverified']
    evidence_ids: list[str] = Field(default_factory=list)
    missing_facets: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=12)
    model_result_visible: bool = False


class GoldCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str = Field(min_length=1)
    job_family: str = Field(min_length=2)
    document_group: str = Field(min_length=2)
    wording_family: str = Field(min_length=2)
    candidate_sha256: str = Field(min_length=64, max_length=64)
    jd_sha256: str = Field(min_length=64, max_length=64)
    requirement_id: str = Field(min_length=2)
    split: Literal['development','tuning','holdout']
    reviews: list[GoldReview] = Field(min_length=2, max_length=2)
    adjudicated: GoldReview | None = None

    @model_validator(mode='after')
    def independent(self):
        if any(r.model_result_visible for r in self.reviews):
            raise ValueError('Reference reviewers must be blinded to model output')
        if self.reviews[0].reviewer_id == self.reviews[1].reviewer_id:
            raise ValueError('Two distinct reviewers are required')
        differing = (self.reviews[0].verdict != self.reviews[1].verdict or
                     set(self.reviews[0].evidence_ids) != set(self.reviews[1].evidence_ids))
        if differing and self.adjudicated is None:
            raise ValueError('Adjudication required when verdicts or evidence disagree')
        if self.adjudicated is not None and self.adjudicated.reviewer_id in {
                self.reviews[0].reviewer_id, self.reviews[1].reviewer_id}:
            raise ValueError('Adjudication must be independently identified')
        return self


def validate_gold_cases(cases: list[GoldCase]) -> dict:
    if not cases:
        raise ValueError('No externally reviewed cases were provided')
    ids=[c.case_id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case_id in labeled data')
    split_by_group=defaultdict(set)
    split_by_candidate=defaultdict(set)
    split_by_jd=defaultdict(set)
    split_by_wording=defaultdict(set)
    for case in cases:
        split_by_group[case.document_group].add(case.split)
        split_by_candidate[case.candidate_sha256].add(case.split)
        split_by_jd[case.jd_sha256].add(case.split)
        split_by_wording[case.wording_family].add(case.split)
    for mapping in (split_by_group,split_by_candidate,split_by_jd,split_by_wording):
        if any(len(splits)>1 for splits in mapping.values()):
            raise ValueError('Document, candidate, JD or wording-family leakage between splits')
    final = [c.adjudicated or c.reviews[0] for c in cases]
    status=Counter(x.verdict for x in final)
    disagreement=sum((c.reviews[0].verdict!=c.reviews[1].verdict or
                      set(c.reviews[0].evidence_ids)!=set(c.reviews[1].evidence_ids))
                      for c in cases)
    return {'status':'independent_labels_format_validated_not_model_accuracy',
            'case_count':len(cases),'disagreements_adjudicated':disagreement,
            'split_counts':dict(Counter(c.split for c in cases)),
            'job_family_counts':dict(Counter(c.job_family for c in cases)),
            'label_counts':dict(status),
            'live_provider_metrics':None,'model_accuracy':None}


def validate_gold_jsonl(path: Path) -> dict:
    cases=[]
    for line_number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():continue
        try:cases.append(GoldCase.model_validate(json.loads(line)))
        except (ValueError,TypeError) as exc:
            raise ValueError(f'Gold dataset record {line_number} invalid: {exc}') from exc
    return validate_gold_cases(cases)

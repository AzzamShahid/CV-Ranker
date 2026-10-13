"""Per-JD, human-approved equivalence declarations. No built-in alias catalogue.

An approval is a reviewer's *policy input*, not a discovered semantic fact.
Every positive match still needs literal, tone-checked source evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import Field, field_validator

from .schemas import EvidenceCitation, RequirementAssessment, StrictModel, ValidatedRequirement
from .segments import ResumeSegment, segment_resume
from .text_utils import classify_requirement_tone, instruction_like_evidence, normalize_whitespace, phrase_present
from .assessor import _is_short_named_requirement, _positive_literal_segment_is_capability_evidence


class AliasApproval(StrictModel):
    requirement: str = Field(min_length=2, max_length=180)
    alias: str = Field(min_length=2, max_length=65)
    approved_by: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=8, max_length=500)

    @field_validator('requirement', 'alias', 'approved_by', 'reason')
    @classmethod
    def no_blank_or_control_text(cls, value: str) -> str:
        cleaned = normalize_whitespace(value)
        if not cleaned or any(ord(ch) < 32 for ch in value):
            raise ValueError('Approval fields cannot be blank or contain control characters')
        return cleaned

    @field_validator('alias')
    @classmethod
    def phrase_only(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+/#_\-]*", value):
            raise ValueError('An approved alias must be a literal short source phrase')
        if len(value.split()) > 5:
            raise ValueError('Approved alias must have at most five words')
        return value


class ApprovalFile(StrictModel):
    schema_version: int = 1
    approvals: list[AliasApproval] = Field(default_factory=list, max_length=50)


def load_approved_aliases(file_path: str | Path | None, requirements: list[ValidatedRequirement]) -> tuple[list[AliasApproval], str | None]:
    """Fail closed for malformed or non-frozen JD approvals."""
    if not file_path:
        return [], None
    raw = Path(file_path).read_bytes()
    if len(raw) > 64 * 1024:
        raise ValueError('Approved-equivalence JSON exceeds 64 KB')
    try:
        doc = ApprovalFile.model_validate(json.loads(raw.decode('utf-8')))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f'Invalid approved-equivalence JSON: {exc}') from exc
    if doc.schema_version != 1:
        raise ValueError('Unsupported approved-equivalence file version')
    frozen = {normalize_whitespace(r.name).casefold(): r.name for r in requirements}
    approved, seen, used_aliases = [], set(), {}
    for item in doc.approvals:
        key = item.requirement.casefold()
        if key not in frozen:
            raise ValueError(f'Approval references a missing/changed JD requirement: {item.requirement!r}')
        # Explicitly disallow quantitative, degree, credential, eligibility,
        # OR-list, or responsibility requirements. Human aliases may identify
        # the SAME short named item, never waive job eligibility constraints.
        if not _is_short_named_requirement(frozen[key]):
            raise ValueError(
                f'Reviewer equivalences are restricted to short named requirements: {item.requirement!r}'
            )
        if item.alias.casefold() == key:
            raise ValueError(f'Approval merely repeats its requirement: {item.requirement!r}')
        pair = (key, item.alias.casefold())
        if pair in seen:
            raise ValueError(f'Duplicate approved equivalence: {item.requirement!r} ↔ {item.alias!r}')
        if item.alias.casefold() in used_aliases and used_aliases[item.alias.casefold()] != key:
            raise ValueError(f'Ambiguous alias {item.alias!r} assigned to multiple JD requirements')
        seen.add(pair)
        used_aliases[item.alias.casefold()] = key
        approved.append(item.model_copy(update={'requirement': frozen[key]}))
    return approved, hashlib.sha256(raw).hexdigest()


def apply_reviewed_aliases(*, requirements: list[ValidatedRequirement], assessments: list[RequirementAssessment],
                           resume_text: str, approvals: list[AliasApproval]) -> tuple[list[RequirementAssessment], list[str], bool]:
    """Change only a negative assessment when a *human-approved* alias has literal CV evidence.

    The source text is not a verifier of semantic equivalence: the reviewer's
    authorization is explicit and the exported report records that reliance.
    Positive+negative contradictory mentions become uncertain (zero credit).
    """
    if not approvals:
        return assessments, [], False
    if len({a.requirement_id for a in assessments}) != len(assessments):
        raise ValueError('Duplicate assessments cannot enter reviewed equivalence evaluation')
    by_requirement: dict[str, list[AliasApproval]] = {}
    for approval in approvals:
        by_requirement.setdefault(approval.requirement.casefold(), []).append(approval)
    segments = segment_resume(resume_text)
    warnings: list[str] = []
    changed = False
    output: list[RequirementAssessment] = []
    by_id = {r.requirement_id: r for r in requirements}
    for result in assessments:
        req = by_id[result.requirement_id]
        if result.status != 'not_matched' or req.name.casefold() not in by_requirement:
            output.append(result)
            continue
        evidence: list[tuple[str, ResumeSegment, AliasApproval]] = []
        # A direct contradiction against the *original* requirement name must
        # not be hidden by an approved alias mentioned positively elsewhere.
        explicit_requirement_negated = any(
            phrase_present(req.name, seg.text)
            and classify_requirement_tone(seg.text, req.name, req.name) == 'negated'
            for seg in segments if not instruction_like_evidence(seg.text)
        )
        for approval in by_requirement[req.name.casefold()]:
            for seg in segments:
                if seg.section not in {'skills', 'experience', 'projects', 'summary'}:
                    continue
                if instruction_like_evidence(seg.text) or not phrase_present(approval.alias, seg.text):
                    continue
                tone = classify_requirement_tone(seg.text, req.name, approval.alias)
                if tone == 'positive' and not _positive_literal_segment_is_capability_evidence(req, seg):
                    continue
                evidence.append((tone, seg, approval))
        positive = [x for x in evidence if x[0] == 'positive']
        negative = [x for x in evidence if x[0] == 'negated']
        uncertain = [x for x in evidence if x[0] == 'uncertain']
        if positive and (negative or explicit_requirement_negated):
            entry = negative[0] if negative else positive[0]
            status = 'uncertain'
        elif positive:
            entry = positive[0]
            status = 'matched'
        elif uncertain:
            entry = uncertain[0]
            status = 'uncertain'
        else:
            output.append(result)
            continue
        _, seg, approval = entry
        output.append(RequirementAssessment(
            requirement_id=req.requirement_id,
            status=status,
            evidence=seg.text,
            matched_term=approval.alias,
            evidence_ids=[seg.segment_id],
            evidence_segments=[EvidenceCitation(segment_id=seg.segment_id, section=seg.section, text=seg.text)],
            reviewed_alias_by=approval.approved_by,
        ))
        changed = True
        warnings.append(
            f'{req.requirement_id}: reviewer-approved alias {approval.alias!r} for {req.name!r} '
            f'(reviewer={approval.approved_by!r}) used from {seg.segment_id}; '
            f'status={status}. This is reviewed equivalence, NOT a Qwen-only semantic match.'
        )
    return output, warnings, changed

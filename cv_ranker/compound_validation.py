"""Phase 7D: conservative source-backed evaluation of *explicit* simple JD AND/OR.

No LLM, synonym mapping, cross-option transfer, or fabricated new criteria.
A compound frozen requirement remains exactly one scoring denominator item.
"""
from __future__ import annotations

import re

from .schemas import (CompoundCheck, CompoundComponent, EvidenceCitation,
                      RequirementAssessment, ValidatedRequirement)
from .segments import segment_resume
from .text_utils import (classify_requirement_tone, instruction_like_evidence,
                         phrase_present, normalize_whitespace)
from .assessor import _positive_literal_segment_is_capability_evidence


SUPPORTED_SECTIONS = {"skills", "inferred_skills", "experience", "projects", "summary", "other"}


def _component(name: str, req: ValidatedRequirement, segments) -> CompoundComponent:
    positive = []
    negative = []
    uncertain = []
    atomic_req = req.model_copy(update={"name": name})
    for seg in segments:
        if seg.section not in SUPPORTED_SECTIONS or instruction_like_evidence(seg.text):
            continue
        if not phrase_present(name, seg.text):
            continue
        tone = classify_requirement_tone(seg.text, name, name)
        cited = EvidenceCitation(segment_id=seg.segment_id, section=seg.section, text=seg.text)
        if tone == "negated":
            negative.append(cited)
        elif tone == "uncertain":
            uncertain.append(cited)
        elif tone == "positive" and _positive_literal_segment_is_capability_evidence(atomic_req, seg):
            positive.append(cited)
    if positive and negative:
        return CompoundComponent(name=name, status="uncertain", evidence=positive[:1]+negative[:1], reason="Contradictory positive and negative source claims")
    if positive:
        return CompoundComponent(name=name, status="matched", evidence=positive[:2], reason="Literal capability claim in CV")
    if uncertain:
        return CompoundComponent(name=name, status="uncertain", evidence=uncertain[:2], reason="Learning-only or qualified evidence")
    if negative:
        return CompoundComponent(name=name, status="not_matched", evidence=negative[:2], reason="Explicit negative claim")
    return CompoundComponent(name=name, status="not_matched", reason="No source-qualified literal evidence")


def evaluate_compound(req: ValidatedRequirement, resume_text: str) -> CompoundCheck | None:
    constraint = req.constraint
    if constraint.operator == "single":
        return None
    if constraint.operator == "complex":
        return CompoundCheck(operator="complex", outcome="needs_review", explanation="Mixed or non-atomic Boolean wording; no precedence or equivalents inferred")
    options = constraint.options
    if (constraint.kind not in {"skill", "other"} or
        not (2 <= len(options) <= 3) or
        any(not 1 <= len(opt.split()) <= 4 or re.search(
            r"\b(?:years?|experience|knowledge|proficiency|qualified|certified|" 
            r"certification|license|degree|must|should|can|ability|using|with|in)\b", opt, re.I
        ) for opt in options) or
        len({normalize_whitespace(opt).casefold() for opt in options}) != len(options)):
        return CompoundCheck(operator=constraint.operator, outcome="needs_review", explanation="Option types or syntax cannot be evaluated safely as standalone skills")
    # Ensure every option really appears in the quoted frozen JD. Fail closed.
    if not all(phrase_present(opt, req.jd_evidence) for opt in options):
        return CompoundCheck(operator=constraint.operator, outcome="needs_review", explanation="Compound alternatives not grounded in frozen JD source")
    segments = segment_resume(resume_text)
    components = [_component(option, req, segments) for option in options]
    statuses = [c.status for c in components]
    if constraint.operator == "all_of":
        outcome = "not_matched" if "not_matched" in statuses else ("uncertain" if "uncertain" in statuses else "matched")
    else:
        outcome = "matched" if "matched" in statuses else ("uncertain" if "uncertain" in statuses else "not_matched")
    return CompoundCheck(operator=constraint.operator, outcome=outcome, components=components,
                         explanation="Evaluated explicit JD alternatives independently using literal source claims; no synonym or transferable-skill credit")


def apply_compound_checks(*, requirements: list[ValidatedRequirement],
                          assessments: list[RequirementAssessment], resume_text: str
                          ) -> tuple[list[RequirementAssessment], list[str], bool]:
    by_id = {r.requirement_id: r for r in requirements}
    result = []
    notes = []
    changed = False
    for item in assessments:
        requirement = by_id[item.requirement_id]
        check = evaluate_compound(requirement, resume_text)
        if check is None:
            result.append(item)
            continue
        status = "uncertain" if check.outcome == "needs_review" else check.outcome
        citations = []
        seen = set()
        for component in check.components:
            for citation in component.evidence:
                if citation.segment_id not in seen:
                    citations.append(citation)
                    seen.add(citation.segment_id)
        # For an uncertain/matched check source data should be visible, but
        # never repeat the original compound claim as proof of each component.
        update = {"status": status, "compound_check": check, "matched_term": None}
        if citations:
            update.update({"evidence_ids": [c.segment_id for c in citations],
                           "evidence_segments": citations,
                           "evidence": " | ".join(c.text for c in citations)})
        else:
            update.update({"evidence_ids": [], "evidence_segments": [], "evidence": None, "matched_term": None})
        new_item = item.model_copy(update=update)
        if new_item.status != item.status:
            changed = True
            notes.append(f"{item.requirement_id}: compound {check.operator}: {item.status} -> {status}; source-verified options, no alias inference")
        result.append(new_item)
    return result, notes, changed

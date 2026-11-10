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
                         phrase_present, normalize_whitespace, non_candidate_requirement_copy)
from .assessor import _positive_literal_segment_is_capability_evidence


SUPPORTED_SECTIONS = {"skills", "inferred_skills", "experience", "projects", "summary", "other"}
# A summary explicitly claiming completed delivery is still a candidate claim;
# summary-only aspirations are excluded by the performed-action guard below.
_WORK_SECTIONS = {"experience", "work_experience", "projects", "summary"}
_COMPLETED_WORK = re.compile(
    r"\b(?:built|developed|designed|delivered|created|implemented|deployed|"
    r"launched|released|shipped|shipping|maintained|operated|integrated|configured|produced|"
    r"automated|managed|trained|evaluated|tested)\b", re.I,
)
_NEGATED_WORK = re.compile(
    r"\b(?:never|not|no|without|haven't|hasn't|didn't|doesn't)\b"
    r".{0,48}\b(?:built|developed|designed|delivered|created|implemented|"
    r"deployed|launched|released|maintained|operated|integrated|configured|"
    r"produced|automated|managed|trained|evaluated|tested)\b", re.I,
)
_ILLUSTRATIVE_SCOPE = re.compile(r"\b(?:including|such as|for example)\b|\be\.g\.", re.I)


def _illustrative_experience(req: ValidatedRequirement,
                             item: RequirementAssessment) -> RequirementAssessment | None:
    """Preserve verified work for broad experience JDs with example alternatives.

    The word 'including' often supplies acceptable examples, NOT a requirement
    to satisfy each comma/or alternative. Keep the frozen JD as one criterion.
    This exception does not apply to numeric tenure, qualifications or skills.
    It grants no direct match from a skills list or an unperformed assertion.
    """
    c = req.constraint
    examples = _ILLUSTRATIVE_SCOPE.search(req.jd_evidence)
    if not (c.kind == "experience" and c.minimum_years is None
            and c.operator == "complex" and examples):
        return None
    # Never override an independently mandatory 'A and B' scope; the only
    # exempt shape is ONE broad work clause followed by an illustrative OR
    # list. Mixed AND/OR beyond that remains review-only and unscored.
    before = req.jd_evidence[:examples.start()]
    after = req.jd_evidence[examples.end():]
    if (re.search(r"\b(?:and|or)\b", before, re.I)
            or re.search(r"\band\b", after, re.I)
            or not re.search(r"\bor\b", after, re.I)):
        return None
    if item.status != "matched":
        # The model has not claimed a match. Keep its citations and uncertainty
        # intact; running a complex Boolean checker cannot improve that claim.
        return item.model_copy(update={
            "review_recommended": item.review_recommended or item.status == "uncertain",
        })
    valid_work = any(
        citation.section in _WORK_SECTIONS
        and _COMPLETED_WORK.search(citation.text)
        and not _NEGATED_WORK.search(citation.text)
        and not instruction_like_evidence(citation.text)
        and not non_candidate_requirement_copy(citation.text)
        for citation in item.evidence_segments
    )
    if valid_work:
        # The main assessor already validated citations and semantic meaning.
        # Preserve the optional HR-review flag, but record this as an accepted
        # illustrated clause in the audit rather than a pipeline failure.
        return item.model_copy(update={
            "review_recommended": True,
            "compound_check": CompoundCheck(
                operator="complex", outcome="matched",
                explanation=("The JD gives illustrative alternatives to one "
                             "broad experience requirement. Completed cited "
                             "work supports the overall requirement; the "
                             "examples are not separate mandatory AND items."),
            ),
        })
    return None


def _component(name: str, req: ValidatedRequirement, segments) -> CompoundComponent:
    positive = []
    negative = []
    uncertain = []
    atomic_req = req.model_copy(update={"name": name})
    for seg in segments:
        if (seg.section not in SUPPORTED_SECTIONS or instruction_like_evidence(seg.text)
                or non_candidate_requirement_copy(seg.text)):
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
        if item.assessment_state == "unverified":
            result.append(item)
            continue
        requirement = by_id[item.requirement_id]
        illustrated = _illustrative_experience(requirement, item)
        if illustrated is not None:
            result.append(illustrated)
            if item.status == "uncertain":
                notes.append(
                    f"{item.requirement_id}: descriptive experience evidence remains "
                    "uncertain; human review is required."
                )
            continue
        # The specialist validators already verified numeric tenure and
        # degree/credential claims against their actual source lines. A
        # syntactic "or" in an experience JD must NOT wipe a sufficient
        # four-year check into Unknown after that stronger check has run.
        # Keep general non-numeric compound skills on this conservative path.
        if ((requirement.constraint.kind == 'experience' and item.experience_check is not None) or
                (requirement.constraint.kind in {'education', 'certification', 'license'}
                 and item.qualification_check is not None)):
            result.append(item)
            continue
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
        if status != item.status:
            details = '; '.join(
                f'{component.name}: {component.status.replace("_", " ")} '
                f'({component.reason})' for component in check.components)
            update['reason'] = (
                f'The frozen JD requires {check.operator.replace("_", " ")} of its '
                f'explicit alternatives. Source checks found: {details or check.explanation}. '
                f'Final decision: {"Found" if status == "matched" else "Not Found" if status == "not_matched" else "review needed"}.'
            )
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

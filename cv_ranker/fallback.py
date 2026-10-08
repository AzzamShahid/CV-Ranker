import re
from dataclasses import dataclass

from .schemas import Priority, RequirementAssessment, ValidatedRequirement, YakeCandidate
from .text_utils import (
    canonical_equivalence_key,
    canonical_key,
    classify_requirement_tone,
    evidence_exists,
    evidence_supports_requirement,
    find_contexts,
    instruction_like_evidence,
    phrase_present,
    requirement_match_terms,
    requirement_options,
    standalone_phrase_line,
)


REQUIRED_HEADINGS = {
    "required", "requirements", "required skills", "required qualifications",
    "job requirements", "role requirements", "candidate requirements", "must have",
    "mandatory", "essential", "minimum qualifications", "key qualifications",
    "qualifications", "skills", "key skills", "core skills", "experience requirements",
    "education requirements", "certifications",
}
PREFERRED_HEADINGS = {
    "preferred", "preferred skills", "preferred qualifications", "nice to have",
    "desirable", "advantageous", "bonus", "bonus skills", "desired",
    "desired skills", "desired qualifications",
}
OTHER_HEADINGS = {
    "responsibilities", "key responsibilities", "job responsibilities",
    "role responsibilities", "duties", "job duties", "what you will do",
    "what you'll do", "about the role", "about us", "benefits",
    "company overview", "role overview",
}
LIST_PREFIX_RE = r"^\s*(?:[-•*▪●◦·]\s+|\d+[.)]\s+)"
GENERIC_NOISE = {
    "required skills", "preferred skills", "requirements", "job description",
    "responsibilities", "qualifications", "about the role", "about us",
}
_CONNECTOR_RE = re.compile(r"(?i)^(?:or|and|etc\.?|including|such as)\b")


@dataclass
class StructuralHint:
    name: str
    priority: Priority
    evidence: str


def _matches_heading(key: str, options: set[str]) -> bool:
    if key in options:
        return True
    return any(key.startswith(option + " ") for option in options if len(option.split()) >= 2)


def _is_heading(line: str) -> str | None:
    key = canonical_key(line.rstrip(":"))
    if not key:
        return None
    if key in OTHER_HEADINGS:
        return "other"
    if _matches_heading(key, PREFERRED_HEADINGS):
        return "preferred"
    if _matches_heading(key, REQUIRED_HEADINGS):
        return "required"
    if len(line) < 80 and line.strip().endswith(":"):
        return "other"
    return None


def _split_list_line(cleaned: str) -> list[str]:
    """Split compact comma/semicolon lists without fragmenting prose requirements."""
    pieces = [p.strip() for p in re.split(r"[;,]", cleaned) if p.strip()]
    if len(pieces) <= 1:
        return [cleaned]
    if any(_CONNECTOR_RE.match(piece) for piece in pieces):
        return [cleaned]
    if any(len(piece.split()) > 4 for piece in pieces):
        return [cleaned]
    if re.search(r"(?i)\b(?:degree|related field|equivalent experience)\b", cleaned):
        return [cleaned]
    return pieces


def structural_hints(jd_text: str) -> list[StructuralHint]:
    """Conservative structural fallback used only when the LLM is unavailable.

    Supports normal/inline headings and compact skill lists while preserving prose
    qualifications and explicit OR requirements as single requirements.
    """
    current: str | None = None
    after_blank = False
    hints: list[StructuralHint] = []

    for raw_line in jd_text.splitlines():
        line = raw_line.strip()
        if not line:
            after_blank = True
            continue

        inline_content: str | None = None
        inline_match = re.match(r"^([^:]{1,60}):\s*(\S.*)$", line)
        if inline_match:
            inline_kind = _is_heading(inline_match.group(1))
            if inline_kind in {"required", "preferred"}:
                current = inline_kind
                inline_content = inline_match.group(2).strip()
            elif inline_kind == "other":
                current = None
                after_blank = False
                continue

        if inline_content is None:
            heading = _is_heading(line)
            if heading:
                current = heading if heading in {"required", "preferred"} else None
                after_blank = False
                continue

        if current is None:
            after_blank = False
            continue

        working = inline_content if inline_content is not None else raw_line
        has_list_marker = bool(re.match(LIST_PREFIX_RE, working))
        cleaned = re.sub(LIST_PREFIX_RE, "", working).strip()
        word_count = len(cleaned.split())

        if (
            after_blank
            and not has_list_marker
            and inline_content is None
            and (len(cleaned) > 120 or word_count > 16 or cleaned.endswith("."))
        ):
            current = None
            after_blank = False
            continue

        after_blank = False
        if not cleaned or canonical_key(cleaned) in GENERIC_NOISE:
            continue

        for piece in _split_list_line(cleaned):
            piece_words = len(piece.split())
            if len(piece) <= 180 and 1 <= piece_words <= 24:
                hints.append(StructuralHint(piece, current, piece))

    return hints


def fallback_requirements(
    jd_text: str,
    yake_candidates: list[YakeCandidate],
    max_requirements: int,
) -> list[ValidatedRequirement]:
    hints = structural_hints(jd_text)
    results: list[ValidatedRequirement] = []
    seen: set[str] = set()

    priority_rank = {"required": 0, "preferred": 1}
    ordered_hints = sorted(
        enumerate(hints),
        key=lambda pair: (priority_rank.get(pair[1].priority, 2), pair[0]),
    )

    for _, hint in ordered_hints:
        key = canonical_equivalence_key(hint.name) or canonical_key(hint.name)
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(
            ValidatedRequirement(
                requirement_id=f"R{len(results)+1:03d}",
                name=hint.name,
                priority=hint.priority,
                jd_evidence=hint.evidence,
            )
        )
        if len(results) >= max_requirements:
            return results

    if results:
        return results

    for candidate in yake_candidates:
        key = canonical_equivalence_key(candidate.keyword) or canonical_key(candidate.keyword)
        if (
            not key
            or key in GENERIC_NOISE
            or key in seen
            or not evidence_exists(candidate.keyword, jd_text)
        ):
            continue
        seen.add(key)
        results.append(
            ValidatedRequirement(
                requirement_id=f"R{len(results)+1:03d}",
                name=candidate.keyword,
                priority="unknown",
                jd_evidence=candidate.keyword,
            )
        )
        if len(results) >= min(12, max_requirements):
            break

    return results


def _fallback_single(
    requirement: ValidatedRequirement,
    resume_text: str,
    term: str,
) -> RequirementAssessment:
    matching_terms = sorted(requirement_match_terms(term) or {canonical_key(term)}, key=len, reverse=True)
    found_term: str | None = None
    contexts: list[str] = []
    standalone: str | None = None

    for candidate_term in matching_terms:
        if not phrase_present(candidate_term, resume_text):
            continue
        candidate_standalone = standalone_phrase_line(resume_text, candidate_term)
        if candidate_standalone and (
            instruction_like_evidence(candidate_standalone)
            or not evidence_supports_requirement(requirement.name, candidate_standalone, candidate_term)
        ):
            candidate_standalone = None
        candidate_contexts = [
            context for context in find_contexts(resume_text, candidate_term)
            if not instruction_like_evidence(context)
            and evidence_supports_requirement(requirement.name, context, candidate_term)
        ]
        if candidate_standalone or candidate_contexts:
            found_term = candidate_term
            standalone = candidate_standalone
            contexts = candidate_contexts or ([candidate_standalone] if candidate_standalone else [])
            break

    if not found_term:
        return RequirementAssessment(
            requirement_id=requirement.requirement_id,
            status="not_matched",
            evidence=None,
        )

    key = canonical_key(found_term)
    if len(key) <= 2 and key.isalpha() and standalone is None:
        cues = (
            "skill", "experience", "experienced", "proficient", "proficiency",
            "knowledge", "familiar", "programming", "language", "using ", "used ",
            "worked with", "developed with", "built with",
        )
        contexts = [context for context in contexts if any(cue in context.casefold() for cue in cues)]
        if not contexts:
            return RequirementAssessment(
                requirement_id=requirement.requirement_id,
                status="not_matched",
                evidence=None,
            )

    classified = [
        (context, classify_requirement_tone(context, term, found_term))
        for context in contexts
    ]
    positives = [context for context, tone in classified if tone == "positive"]
    negatives = [context for context, tone in classified if tone == "negated"]
    uncertain = [context for context, tone in classified if tone == "uncertain"]

    if positives and negatives:
        status = "uncertain"
        evidence = negatives[0]
    elif positives:
        status = "matched"
        evidence = standalone or positives[0]
    elif negatives:
        status = "not_matched"
        evidence = negatives[0]
    elif uncertain:
        status = "uncertain"
        evidence = uncertain[0]
    else:
        status = "not_matched"
        evidence = None

    return RequirementAssessment(
        requirement_id=requirement.requirement_id,
        status=status,
        evidence=evidence,
        matched_term=(
            found_term
            if len(requirement_options(requirement.name)) > 1
            or canonical_key(found_term) != canonical_key(requirement.name)
            else None
        ),
    )


def fallback_assessment(
    requirement: ValidatedRequirement,
    resume_text: str,
) -> RequirementAssessment:
    """Conservative exact/alias fallback for technical LLM failure only."""
    options = requirement_options(requirement.name)
    if len(options) == 1:
        return _fallback_single(requirement, resume_text, options[0])

    results = [_fallback_single(requirement, resume_text, option) for option in options]
    matched = next((item for item in results if item.status == "matched"), None)
    if matched:
        return matched
    uncertain = next((item for item in results if item.status == "uncertain"), None)
    if uncertain:
        return uncertain
    negative = next((item for item in results if item.evidence), None)
    return negative or RequirementAssessment(
        requirement_id=requirement.requirement_id,
        status="not_matched",
        evidence=None,
    )

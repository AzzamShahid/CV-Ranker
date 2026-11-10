import re
from dataclasses import dataclass

from .schemas import EvidenceCitation, Priority, RequirementAssessment, ValidatedRequirement, YakeCandidate
from .segments import segment_resume
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
    "education requirements", "certifications", "required experience",
    "minimum experience", "minimum required experience", "required education",
    "education", "academic requirements", "academic qualifications",
    "minimum requirements", "required experience and education",
    "required qualifications and experience",
    "basic qualifications", "minimum qualifications and experience",
    "required skills and experience", "education and experience",
    "education and qualifications", "academic credentials",
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
    "company overview", "role overview", "core responsibilities",
    "how to interpret requirements", "requirement interpretation",
    "explanatory notes", "important notes", "notes to applicants",
}
LIST_PREFIX_RE = r"^\s*(?:[-•*▪●◦·\uf0b7]\s*|\d+[.)]\s+)"
GENERIC_NOISE = {
    "required skills", "preferred skills", "requirements", "job description",
    "responsibilities", "qualifications", "about the role", "about us",
}
_CONNECTOR_RE = re.compile(r"(?i)^(?:or|and|etc\.?|including|such as)\b")

_NON_REQUIREMENT_RE = re.compile(
    r"(?i)\b(?:competitive salary|salary package|compensation|great culture|"
    r"flexible hours?|paid leave|vacation|health insurance|equal opportunity employer)\b"
)
_ACTION_START_RE = re.compile(
    r"(?i)^(?:build|develop|maintain|work|collaborate|design|support|manage|create|implement|"
    r"integrate|participate|assist|lead|deliver|coordinate|prepare|perform|handle)\b"
)
_REQUIREMENT_CUE_RE = re.compile(
    r"(?i)\b(?:experience|proficiency|knowledge|skill|ability|familiarity|degree|certif|license|licence|years?)\b"
)


def looks_like_non_requirement(text: str) -> bool:
    """Generic benefit/action wording; never a profession-specific skill list."""
    return bool(
        _NON_REQUIREMENT_RE.search(text)
        or (_ACTION_START_RE.search(text) and not _REQUIREMENT_CUE_RE.search(text))
    )


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
    title_like = (not re.search(r"\d", line) and not line.rstrip().endswith((".", "!", "?"))
                  and len(line.split()) <= 7)
    if key in PREFERRED_HEADINGS or (title_like and line.rstrip().endswith(":")
                                     and _matches_heading(key, PREFERRED_HEADINGS)):
        return "preferred"
    if key in REQUIRED_HEADINGS or (title_like and line.rstrip().endswith(":")
                                    and _matches_heading(key, REQUIRED_HEADINGS)):
        return "required"
    # Variants such as "Basic Qualifications", "Required education and
    # certifications" and "Minimum experience & education" describe source
    # structure. These are not a fixed list of technical/professional skills.
    if (title_like and re.search(r"(?i)\b(?:requirements?|qualifications?|experience|education|credentials?)\b", key)):
        if re.search(r"(?i)\b(?:required|mandatory|minimum|basic|essential|must have)\b", key):
            return "required"
        if re.search(r"(?i)\b(?:preferred|desired|bonus|optional|nice to have)\b", key):
            return "preferred"
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


def _logical_source_lines(jd_text: str) -> list[str]:
    """Rejoin visual PDF line wraps, preserving genuine JD list boundaries.

    This is layout repair only: it never creates a requirement or supplies a
    field/skill. All reunited words must still be found in the original JD.
    """
    rows: list[str] = []
    for original in jd_text.splitlines():
        current = original.strip()
        if not current:
            rows.append("")
            continue
        previous = rows[-1].strip() if rows else ""
        if (previous and not re.match(LIST_PREFIX_RE, current)
                and _is_heading(current) is None and _is_heading(previous) is None
                and not previous.endswith((".", "!", "?", ";", ":"))
                and not re.match(LIST_PREFIX_RE, previous)
                and (len(previous) >= 75 or
                     bool(re.search(r"(?i)\b(?:of|in|with|for|and|or|the|a|an|to|by|from)\s*$", previous)))):
            rows[-1] = previous + " " + current
        else:
            rows.append(current)
    return rows


def structural_hints(jd_text: str) -> list[StructuralHint]:
    """Conservative structural fallback used only when the LLM is unavailable.

    Supports normal/inline headings and compact skill lists while preserving prose
    qualifications and explicit OR requirements as single requirements.
    """
    current: str | None = None
    excluded_section = False
    after_blank = False
    hints: list[StructuralHint] = []

    for raw_line in _logical_source_lines(jd_text):
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
                excluded_section = False
                inline_content = inline_match.group(2).strip()
            elif inline_kind == "other":
                current = None
                excluded_section = True
                after_blank = False
                continue

        if inline_content is None:
            heading = _is_heading(line)
            if heading:
                current = heading if heading in {"required", "preferred"} else None
                excluded_section = heading == "other"
                after_blank = False
                continue

        if current is None:
            # Explicit mandatory qualifications in otherwise unsectioned JD
            # prose must not vanish when the model omits them. The line itself
            # must state a numeric tenure/credential AND clear obligation;
            # never infer expectations from a job title or CV content.
            strong_obligation = re.search(
                r"(?i)\b(?:minimum|at least|must have|required|mandatory|essential)\b", line)
            concrete_constraint = re.search(
                r"(?i)\b(?:\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)|"
                r"bachelor(?:'s)?|master(?:'s)?|degree|diploma|"
                r"certification|licen[cs]e|b\.?s\.?c?\.?|m\.?s\.?c?\.?)\b", line)
            if (not excluded_section and strong_obligation and concrete_constraint
                    and len(line) <= 350 and not _NON_REQUIREMENT_RE.search(line)):
                clean = re.sub(LIST_PREFIX_RE, "", line).strip()
                hints.append(StructuralHint(clean, "required", clean))
            after_blank = False
            continue

        working = inline_content if inline_content is not None else raw_line
        has_list_marker = bool(re.match(LIST_PREFIX_RE, working))
        cleaned = re.sub(LIST_PREFIX_RE, "", working).strip()
        word_count = len(cleaned.split())

        # A blank line immediately under a section title is normal in a PDF
        # or a formatted JD. Do not discard a clear mandatory duration/degree
        # statement merely because it is a paragraph rather than a bullet.
        source_names_a_constraint = bool(re.search(
            r"(?i)\b(?:\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)|"
            r"degree|bachelor(?:'s)?|master(?:'s)?|diploma|certif\w*|licen[cs]e|"
            r"b\.?s\.?c?\.?|m\.?s\.?c?\.?|b\.?tech\.?)\b",
            cleaned,
        ))
        source_declares_mandatory = bool(re.search(
            r"(?i)\b(?:minimum|at least|must have|required|mandatory|essential)\b", cleaned
        ))
        # A required/preferred section *itself* supplies the priority. A CV/JD
        # author need not repeat "required" on every line. Without this,
        # "Required Education: <blank> Bachelor's in X." disappears.
        explicit_constraint = source_names_a_constraint and (
            source_declares_mandatory or current in {"required", "preferred"}
        )
        if (after_blank and not has_list_marker and inline_content is None
                and (len(cleaned) > 120 or word_count > 16 or cleaned.endswith("."))
                and not explicit_constraint):
            current = None
            after_blank = False
            continue

        after_blank = False
        if not cleaned or canonical_key(cleaned) in GENERIC_NOISE:
            continue
        if _NON_REQUIREMENT_RE.search(cleaned):
            continue
        if not has_list_marker and inline_content is None and cleaned.endswith((".", "!", "?")):
            # A required *paragraph* is just as binding as a required bullet.
            # Keep only short, explicitly signalled experience/qualification
            # statements; plain prose after a section is not a free requirement.
            if not explicit_constraint:
                current = None
                continue
        if (
            _ACTION_START_RE.search(cleaned)
            and not _REQUIREMENT_CUE_RE.search(cleaned)
        ):
            # In structural fallback, imperative/action lines are more likely role
            # responsibilities than qualifications, even when bullet-prefixed.
            continue

        for piece in _split_list_line(cleaned):
            piece_words = len(piece.split())
            if (len(piece) <= 180 and 1 <= piece_words <= 24) or (
                # An explicit, longer qualification/experience bullet must not
                # vanish merely because it includes a clarifying sentence.
                (has_list_marker or (inline_content is None and cleaned.endswith(".")))
                and len(piece) <= 650 and piece_words <= 100
                and bool(_REQUIREMENT_CUE_RE.search(piece))
            ):
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

    # YAKE phrases are discovery hints only. If there is no explicit structural
    # requirement section, deterministic fallback cannot safely decide what is a
    # hiring requirement, so return no requirements and let the pipeline stop.
    del yake_candidates
    return results


def _fallback_positive_allowed(requirement: ValidatedRequirement, section: str, text: str) -> bool:
    name = requirement.name.casefold()
    education_like = any(word in name for word in ("degree", "bachelor", "master", "phd", "diploma"))
    certification_like = any(word in name for word in ("certification", "certified", "certificate", "license", "licence"))
    if section == "skills":
        return True
    if section == "inferred_skills":
        # A free-standing CV label proves itself only, not a related concept,
        # substring, title, or guessed synonym.
        return any(canonical_key(text) == canonical_key(opt)
                   for opt in requirement_options(requirement.name))
    if section == "education":
        return education_like
    if section == "certifications":
        return certification_like or education_like
    if section not in {"experience", "projects", "summary", "other"}:
        return False
    lower = text.casefold()
    if re.search(r"\b\d{1,2}\s*\+?\s*years?\b", lower):
        return True
    cues = (
        "experienced", "experience with", "proficient", "skilled", "expert", "expertise", "knowledge of",
        "familiar with", "used ", "using ", "worked with", "built ", "developed ",
        "implemented ", "maintained ", "created ", "designed ", "deployed ",
        "trained ", "evaluated ", "applied ", "integrated ", "managed ",
        "coordinated ", "handled ", "supported ", "prepared ", "administered ",
    )
    return any(cue in lower for cue in cues)


def _fallback_single(
    requirement: ValidatedRequirement,
    resume_text: str,
    term: str,
) -> RequirementAssessment:
    # Keep source IDs in fallback too. Formerly only free-text quotes survived,
    # making it hard to audit a fallback match against its exact CV line.
    hits: list[tuple[str, str, str, str, str]] = []
    for segment in segment_resume(resume_text):
        if instruction_like_evidence(segment.text) or not phrase_present(term, segment.text):
            continue
        contexts = find_contexts(segment.text, term) or [segment.text]
        for context in contexts:
            if instruction_like_evidence(context):
                continue
            tone = classify_requirement_tone(context, requirement.name, term)
            if tone == "positive" and not _fallback_positive_allowed(requirement, segment.section, context):
                continue
            hits.append((tone, context, segment.segment_id, segment.section, segment.text))

    positives = [item for item in hits if item[0] == "positive"]
    negatives = [item for item in hits if item[0] == "negated"]
    uncertain = [item for item in hits if item[0] == "uncertain"]

    if positives and negatives:
        status, selected = "uncertain", negatives[0]
    elif positives:
        status, selected = "matched", positives[0]
    elif negatives:
        status, selected = "not_matched", negatives[0]
    elif uncertain:
        status, selected = "uncertain", uncertain[0]
    else:
        status, selected = "not_matched", None

    evidence = selected[1] if selected else None
    evidence_ids = [selected[2]] if selected else []
    evidence_segments = ([EvidenceCitation(segment_id=selected[2],
                                           section=selected[3], text=selected[4])]
                         if selected else [])

    return RequirementAssessment(
        requirement_id=requirement.requirement_id,
        status=status,
        evidence=evidence,
        evidence_ids=evidence_ids,
        evidence_segments=evidence_segments,
        matched_term=(
            term
            if len(requirement_options(requirement.name)) > 1
            or canonical_key(term) != canonical_key(requirement.name)
            else None
        ),
    )


def fallback_assessment(
    requirement: ValidatedRequirement,
    resume_text: str,
) -> RequirementAssessment:
    """Conservative literal/explicit-OR fallback for technical LLM failure only."""
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

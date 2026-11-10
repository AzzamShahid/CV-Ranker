"""Evidence standards derived from the *frozen JD*, independent of occupation.

This module does not match candidate skills or infer synonyms. Its sole task
is to prevent an assessor from silently adding a professional-use threshold
to an ordinary named-skill criterion. Typed work, duration, qualification and
explicitly qualified skill requirements retain their original conditions.
"""

from __future__ import annotations

import re

from .schemas import ValidatedRequirement
from .text_utils import normalize_whitespace


_EXPLICIT_SCOPE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)|at\s+least|minimum|"
    r"professional\s+(?:work|experience|practice)|work\s+history|"
    r"hands[ -]on\s+experience|proven\s+(?:track\s+record|experience)|"
    r"production\s+(?:deployment|experience|use)|"
    r"commercial\s+(?:deployment|experience|use)|"
    r"experience\s+(?:with|in|using)|demonstrated\s+in\s+professional)\b",
    re.I,
)

_UNSTATED_WORK_OBJECTION = re.compile(
    r"\b(?:not|no|never|without|lack(?:s|ed|ing)?|insufficient|"
    r"fails?\s+to|does(?:n['’]?t|\s+not)|did(?:n['’]?t|\s+not)|"
    r"is(?:n['’]?t|\s+not)|was(?:n['’]?t|\s+not))\b"
    r"[^.!?]{0,145}\b(?:professional\s+(?:experience|work|practice|use|application|evidence)|"
    r"work[ -]history|experience\s+(?:section|history)|"
    r"used\s+in\s+(?:a\s+)?professional\s+(?:role|setting|project)|"
    r"production\s+(?:use|deployment|context|experience)|"
    r"commercial\s+(?:deployment|project|experience)|"
    r"hands[ -]on\s+(?:project|experience|application))\b",
    re.I,
)

# Model phrasing changes across providers: "not shown in employment" and
# "not applied on a project" express the same invented evidence threshold as
# "not demonstrated in professional experience". These are scope words, NOT
# candidate skills, platform names, or domain-specific matching rules.
_WORK_APPLICATION_OBJECTION = re.compile(
    r"\b(?:not|no|never|without|lack(?:s|ed|ing)?|missing|insufficient|"
    r"fails?\s+to|cannot|can['’]?t|does(?:n['’]?t|\s+not)|"
    r"did(?:n['’]?t|\s+not)|is(?:n['’]?t|\s+not)|was(?:n['’]?t|\s+not))\b"
    r"[^.!?]{0,150}\b(?:professional|work(?:place)?|employment|job|career|"
    r"experience|production|project|deployment|applied|practical|"
    r"commercial|real[ -]world)\b",
    re.I,
)


def ordinary_named_skill(req: ValidatedRequirement) -> bool:
    """True only for a bare single skill with no JD-stated work/depth condition.

    The requirement type alone is insufficient: inaccurate typing cannot
    cancel explicit constraints still present in the frozen JD quotation.
    """
    if req.constraint.kind != "skill" or req.constraint.operator != "single":
        return False
    name = normalize_whitespace(req.name).strip(" .;:").casefold()
    source = normalize_whitespace(req.jd_evidence).strip(" .;:").casefold()
    return bool(name and name == source and not _EXPLICIT_SCOPE.search(source))


def unstated_work_objection(req: ValidatedRequirement, reason: str) -> bool:
    """Identify an added work-history criterion, never an absent skill itself.

    This is a *reason-validity* warning, not proof that any CV meets the skill.
    Rejecting the reason cannot automatically produce Found.
    """
    if not ordinary_named_skill(req) or not reason:
        return False
    # A statement that the extra threshold is NOT required is compliant.
    if re.search(r"\b(?:professional|production|commercial)\s+"
                 r"(?:experience|use|deployment)\s+(?:is|was)\s+not\s+required\b",
                 reason, re.I):
        return False
    return bool(_UNSTATED_WORK_OBJECTION.search(reason)
                or _WORK_APPLICATION_OBJECTION.search(reason))

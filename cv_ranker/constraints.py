"""Conservative numeric-evidence consistency checks.

This module does NOT extract a complete employment history or infer skill
synonyms. It only detects a direct contradiction between an explicit minimum
experience duration in a JD and explicit, skill-scoped shorter durations in
cited resume text. Ambiguous durations are left for human review.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from .text_utils import phrase_present

_DURATION = re.compile(r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?\b", re.I)
_NON_SUBJECT = frozenset({
    "at", "least", "minimum", "of", "the", "a", "an", "and", "or", "for", "in", "with", "on", "to",
    "experience", "professional", "relevant", "working", "work", "using", "knowledge", "required",
    "preferred", "minimum", "years", "year", "hands", "practical", "strong", "industry", "skills",
})


def minimum_years(requirement_name: str) -> float | None:
    """Read a plainly written duration requirement, without guessing dates."""
    match = _DURATION.search(requirement_name)
    if not match:
        return None
    # A JD's duration is treated as a minimum in this very narrow guard.
    return float(match.group(1))


def _subject_terms(requirement_name: str) -> list[str]:
    without_duration = _DURATION.sub(" ", requirement_name)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9.+#/-]*", without_duration)
    return [w for w in tokens if w.casefold() not in _NON_SUBJECT and len(w) > 1]


def explicitly_below_minimum(requirement_name: str, cited_texts: Iterable[str]) -> bool:
    """Only act on unambiguous directly contradictory numeric statements.

    Require a specific named subject such as 'Python', not merely 'experience'.
    For each cited clause containing that name, consider a duration only if
    there is exactly one number-of-years phrase. Multiple durations in a clause
    are ambiguous (e.g. total versus skill-specific experience) and are never
    rejected automatically.
    """
    threshold = minimum_years(requirement_name)
    subjects = _subject_terms(requirement_name)
    if threshold is None or not subjects:
        return False

    found: list[float] = []
    for text in cited_texts:
        for clause in re.split(r"(?<!\d)[.;](?!\d)|\n", text):
            if not all(phrase_present(token, clause) for token in subjects):
                continue
            mentions = _DURATION.findall(clause)
            if len(mentions) != 1:
                # Multiple years in one clause could refer to different work;
                # let the existing model/reviewer handle the ambiguity.
                return False
            found.append(float(mentions[0]))
    return bool(found) and all(value < threshold for value in found)

"""Existing source-backed functional-transfer review, shared by assessment paths.

This is an inspection of the CV segment ledger already extracted for the
approved retrieval pipeline. It is not a new search engine, synonym dictionary,
or authority for granting direct named-skill credit.
"""
from __future__ import annotations

import re
from typing import Any

from .text_utils import instruction_like_evidence, non_candidate_requirement_copy, phrase_present


_PERFORMED_ACTION = re.compile(
    r"\b(?:built|trained|implemented|developed|designed|delivered|created|"
    r"integrated|deployed|operated|evaluated|orchestrated|automated|maintained)\b", re.I)
_BRIDGE_COMPARISON = re.compile(
    r"(?:\b(?:same|equivalent|comparable)\b.{0,190}?"
    r"\b(?:functions?|functionality|workflows?|capabilities|duties|tasks|responsibilities)\b"
    r".{0,140}?\b(?:achieved|performed|implemented|built|handled|done|using|with|by)\b|"
    r"\b(?:transferable|similar|overlapping|comparable)\b.{0,100}?"
    r"\b(?:functions?|functionality|workflows?|capabilities|duties|tasks|"
    r"responsibilities|design|patterns?|methods?|approach|process(?:es|ing)?)\b)", re.I)
_OVERLAP_FILLER = {"these", "those", "about", "their", "other", "which", "would", "often",
                   "using", "built", "model", "models", "functions", "tools", "platform", "system"}


def performed_functional_bridge(requirement: Any,
                                original: dict[str, Any]) -> tuple[str, str, list[str]] | None:
    """Return an explicit comparison plus independent completed-work evidence.

    No name-level equivalence is inferred. The returned source IDs support only
    Transferable with human review, never Found. Denial/comparison alone fails.
    """
    if requirement.constraint.kind != "skill" or requirement.constraint.operator != "single":
        return None
    for sid, segment in original.items():
        if (segment.section not in {"projects", "experience", "work_experience"}
                or instruction_like_evidence(segment.text)
                or non_candidate_requirement_copy(segment.text)
                or not phrase_present(requirement.name, segment.text)):
            continue
        comparison = _BRIDGE_COMPARISON.search(segment.text)
        if comparison is None or not phrase_present(requirement.name, segment.text[comparison.start():]):
            continue
        named_terms = {word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z-]{4,}", requirement.name)}
        bridge_terms = {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z-]{4,}", segment.text)
                        if token.casefold() not in _OVERLAP_FILLER | named_terms}
        for work_id, work in original.items():
            if (work_id == sid or work.section not in {"projects", "experience", "work_experience"}
                    or instruction_like_evidence(work.text)
                    or non_candidate_requirement_copy(work.text)
                    or not _PERFORMED_ACTION.search(work.text)):
                continue
            shared = sorted(bridge_terms.intersection(
                token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z-]{4,}", work.text)
            ))
            if len(shared) >= 2:
                return sid, work_id, shared[:5]
    return None

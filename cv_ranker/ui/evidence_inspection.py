"""Read-only CV segment ledger and literal-source inspection for the V4 UI.

These helpers explain what exists in the extracted document; they never award
matches, modify LLM decisions, or treat a project mention as verified mastery.
"""
from __future__ import annotations

from typing import Any

from ..assessor import _literal_initialism, _positive_literal_segment_is_capability_evidence
from ..schemas import ValidatedRequirement
from ..segments import ResumeSegment
from ..text_utils import (
    classify_requirement_tone, instruction_like_evidence,
    non_candidate_requirement_copy, phrase_present, requirement_options,
)


def segment_ledger(segments: list[ResumeSegment]) -> list[dict[str, Any]]:
    """Persist exact parsed segments, including the physical PDF/Word lines."""
    return [{
        "segment_id": segment.segment_id,
        "section": segment.section,
        "text": segment.text,
        "source_lines": list(segment.source_lines),
    } for segment in segments]


def resume_segments(ledger: list[dict[str, Any]]) -> list[ResumeSegment]:
    return [ResumeSegment(
        segment_id=item["segment_id"], section=item["section"],
        text=item["text"], source_lines=tuple(item.get("source_lines", ())),
    ) for item in ledger]


def literal_mentions(
    requirement: ValidatedRequirement,
    segments: list[ResumeSegment],
) -> list[dict[str, str]]:
    """Find EVERY literal CV mention, including guarded exact initialisms.

    A hit is an inspection checkpoint, not automatically accepted as proof or
    a scoring decision. We explicitly retain negative, learning, and copied
    job-ad matches so reviewers can see why those do not grant credit.
    """
    terms = list(requirement_options(requirement.name))
    initialism = _literal_initialism(requirement)
    if initialism:
        terms.append(initialism)
    result: list[dict[str, str]] = []
    for segment in segments:
        term = next((value for value in terms if phrase_present(value, segment.text)), None)
        if not term:
            continue
        inadmissible = (
            segment.section in {"non_candidate", "metadata"}
            or non_candidate_requirement_copy(segment.text)
            or instruction_like_evidence(segment.text)
        )
        tone = classify_requirement_tone(segment.text, requirement.name, term)
        if inadmissible:
            finding = "Excluded — copied JD, metadata, or instruction"
        elif tone == "negated":
            finding = "Explicit negative statement — no positive credit"
        elif tone == "uncertain":
            finding = "Qualified/learning statement — assess carefully"
        elif _positive_literal_segment_is_capability_evidence(requirement, segment):
            finding = ("Explicit CV skill claim" if segment.section in {"skills", "inferred_skills"}
                       else "Named in work/project account")
        else:
            finding = "Name mentioned, but capability not established"
        result.append({
            "Segment": segment.segment_id,
            "Section": segment.section,
            "Source term": term,
            "Finding": finding,
            "Text": segment.text,
        })
    return result

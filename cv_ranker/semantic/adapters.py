"""Bridge any existing ResumeSegment-like object into the shadow retriever.

Upstream must supply admitted segment IDs; nothing is admitted by default.
"""
from .core import EvidenceSegment


def from_resume_segments(candidate_id: str, segments: list, admissible_ids: set[str]) -> list[EvidenceSegment]:
    if not isinstance(admissible_ids, set):
        raise TypeError("admissible_ids must be explicitly supplied as a set")
    return [
        EvidenceSegment(
            candidate_id=candidate_id,
            segment_id=str(segment.segment_id),
            text=str(segment.text),
            section=str(getattr(segment, "section", "other")),
            admissible=str(segment.segment_id) in admissible_ids,
        )
        for segment in segments
    ]

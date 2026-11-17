"""Very conservative *gross mismatch* backstop for source-cited work awards.

LLM relation is not proof on its own. A genuinely semantically synonymous CV
passage may have no lexical anchors, so failure here must trigger evidence
review, NOT an automatic negative verdict. This guard never awards credit.
The stop vocabulary is grammatical/temporal, not profession/tool-specific.
"""
from __future__ import annotations

import re

from .schemas import ValidatedRequirement, EvidenceCitation

_GRAMMAR = frozenset('''
    a an the of for to at on by in with from through and or not both
    required preferred minimum must should can will during within into across
    use using used is are be have has their his her its our as such including
    years year experience professional work working practical skilled
    develop developed developing manage managed managing prepare prepared preparing
    build built building implement implemented implementing operate operated operating
    document documented documenting create created creating perform performed
    support supported supporting coordinate coordinated coordinating
    inspect inspected inspecting reconcile reconciled reconciling
    review reviewed reviewing analyze analysed analyzed investigate investigated
    monthly weekly daily yearly annually regularly frequent recurring routine
'''.split())


def _anchors(text: str) -> set[str]:
    return {token[:5] for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#-]{3,}", text)
            if token.casefold() not in _GRAMMAR
            and not re.match(r"\d", token)}


def grossly_unanchored_work(req: ValidatedRequirement,
                           citations: list[EvidenceCitation], *,
                           named_condition_grounded: bool = False) -> bool:
    """True only for a *total* lack of content overlap in a substantive duty.

    A lexical anchor is necessary for ordinary direct source attribution when
    there is no separately approved field-equivalence policy. It is never
    sufficient: the LLM and specialist checks still decide semantic meaning.
    When there is no overlap, pause for a specific source/equivalence review.
    """
    if named_condition_grounded:
        # A sourced explicit named tool and its performed duty can be enough
        # even if the rest of the JD uses legitimate different vocabulary.
        # The named guard is independently source validated by the caller.
        return False
    # Only the newly source-typed performed-work contract enables this gross
    # mismatch policy. Historical/manual/legacy R objects without a reviewed
    # evidence standard must retain their prior semantic-assessor behavior;
    # silently tightening them would break old reports and add paid retries.
    if req.constraint.evidence_modality not in {"performed_work", "employer_review_required"}:
        return False
    required = _anchors(req.jd_evidence)
    observed = _anchors(" ".join(c.text for c in citations))
    return len(required) >= 2 and len(observed) >= 2 and not required.intersection(observed)

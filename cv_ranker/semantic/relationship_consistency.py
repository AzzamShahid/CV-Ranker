"""Phase 7G: non-scoring checks on provisional model relationship labels.

These are review *signals*, never independent semantic verification. A literal
named-technology mention is not proof of ability, role scope, or credentials.
There are NO professional-skill or technology equivalence dictionaries here.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence


LISTING_SECTIONS = frozenset({"skills", "inferred_skills"})

# Generic evidence-modality cues, not professional-skill vocabulary. Kept
# deliberately conservative: a mixed/contradictory sentence goes to human
# review rather than becoming an automatic positive work claim.
_NON_DEMONSTRATED_RE = re.compile(
    r"\b(?:no\s+(?:\w+\s+){0,5}experience|never|without|"
    r"lack(?:s|ed|ing)?|not|didn['’]?t|don['’]?t|doesn['’]?t|"
    r"learn(?:ing)?|interested|plan(?:ning)?|hope(?:s|d)?|"
    r"intend(?:s|ed)?|want(?:s|ed)?|wish(?:es|ed)?|"
    r"exposure|familiarity|seeking|aspir(?:e|ing))\b",
    re.IGNORECASE,
)


def _has_exact_phrase(phrase: str, text: str) -> bool:
    """Literal, token-bounded match, not fuzzy or semantic substitution."""
    phrase = phrase.strip()
    if len(phrase) < 2:
        return False
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.IGNORECASE))


def _plausible_named_work(phrase: str, source_text: str, section: str) -> bool:
    """Review heuristic only: an asserted, non-listing narrative with a term.

    This does not establish authorship, job relevance, professional experience,
    duration, or competence. Ambiguous/negated/aspirational evidence is excluded
    to reduce *automatic review flags*, not to dismiss the evidence itself.
    """
    if section.strip().casefold() in LISTING_SECTIONS:
        return False
    if not _has_exact_phrase(phrase, source_text):
        return False
    if source_text.strip().casefold() == phrase.strip().casefold():
        return False
    if _NON_DEMONSTRATED_RE.search(source_text):
        return False
    return True


def relationship_consistency_flags(
    *,
    requirement_name: str,
    capability_description: str,
    relationship: str,
    citations: Sequence[tuple[str, str]],
    original_sources: Mapping[str, tuple[str, str]],
    retrieved_sources: Mapping[str, tuple[str, str]] | None = None,
) -> list[str]:
    """Flag *possible* inconsistencies without changing a proposal or score.

    `citations`: source-audited (segment_id, exact_quote) pairs.
    `original_sources`: authorized original CV (segment_id -> text, section).
    `retrieved_sources`: candidate/requirement-scoped already-audited search hits.
        If omitted, only previously established citation-based rules run.
    Only literal, single-name requirements equal to the explicit capability
    are inspected. Dynamic alternatives/compound obligations are not rewritten.
    """
    if requirement_name.strip().casefold() != capability_description.strip().casefold():
        return []
    valid_citations: list[tuple[str, bool]] = []
    for sid, quote in citations:
        source = original_sources.get(sid)
        if source is None or quote.strip() not in source[0]:
            # Invalid citations must fail upstream, not become credible here.
            continue
        valid_citations.append((source[1].strip().casefold(), _has_exact_phrase(requirement_name, quote)))
    flags: list[str] = []
    if relationship == "transferable" and valid_citations:
        if all(section in LISTING_SECTIONS for section, _ in valid_citations):
            flags.append("transferable_label_based_only_on_skills_listing")
        elif any(term and section not in LISTING_SECTIONS for section, term in valid_citations):
            flags.append("possible_direct_mislabeled_transferable")
        elif any(term and section in LISTING_SECTIONS for section, term in valid_citations):
            flags.append("named_skill_only_in_listing_other_citations_do_not_show_its_use")
    elif relationship == "direct" and valid_citations:
        if all(section in LISTING_SECTIONS for section, _ in valid_citations):
            flags.append("direct_claim_supported_only_by_skills_listing")
        elif (any(term and section in LISTING_SECTIONS for section, term in valid_citations)
              and not any(term and section not in LISTING_SECTIONS for section, term in valid_citations)):
            flags.append("direct_named_skill_only_in_listing_other_work_does_not_show_its_use")

    # The old audit inspected only cited positives. Review *nonpositive* Qwen
    # labels against search results too; a model may cite nothing when it
    # dismisses an obvious work passage. Search hits MUST have been validated
    # against the correct candidate's original CV upstream.
    if retrieved_sources is not None:
        checked = [
            (sid, text, section) for sid, (text, section) in retrieved_sources.items()
            if sid in original_sources and original_sources[sid] == (text, section)
        ]
        if relationship in {"related_only", "not_evidenced", "uncertain"}:
            if any(_plausible_named_work(requirement_name, text, section)
                   for _, text, section in checked):
                flags.append("possible_named_work_overlooked_by_nonpositive_label")
        if relationship == "not_evidenced" and any(
            section.strip().casefold() in LISTING_SECTIONS and
            _has_exact_phrase(requirement_name, text)
            for _, text, section in checked
        ):
            flags.append("named_skill_listing_present_but_reported_not_evidenced")
    return flags

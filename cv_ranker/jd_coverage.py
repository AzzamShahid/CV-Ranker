"""Evidence-only audit of which explicit employer clauses survived JD review.

This audit never creates hiring criteria, inferred source text or candidate score.
A structural hint is only a possible original JD source clause; a human can
review it when the model's frozen denominator did not retain the clause.
"""
from __future__ import annotations

from .fallback import structural_hints
from .schemas import ValidatedRequirement
from .text_utils import evidence_exists, evidence_source_line_numbers, normalize_whitespace


def explicit_clause_coverage(jd_text: str,
                             requirements: list[ValidatedRequirement]) -> list[dict]:
    """Report exact, source-bound structural candidates and their frozen R IDs.

    Duplicate source clauses retain their own entries. Matching uses contained
    original JD quotations, not semantic similarity or synthesized aliases.
    A model can have legitimately merged two genuine clauses; such a case is
    marked for HR review rather than silently claiming coverage.
    """
    report: list[dict] = []
    for hint in structural_hints(jd_text):
        original = normalize_whitespace(hint.evidence)
        if not original or not evidence_exists(original, jd_text):
            continue
        ids = [req.requirement_id for req in requirements
               if evidence_exists(original, req.jd_evidence)
               or evidence_exists(req.jd_evidence, original)]
        lines = evidence_source_line_numbers(original, jd_text)
        status = ("covered" if len(ids) == 1 else
                  "multiple_possible_mappings" if len(ids) > 1 else
                  "unmapped_review_required")
        report.append({
            "stage": "explicit_jd_clause_coverage",
            "source_quote": original,
            "source_line_numbers": lines,
            "heading_priority": hint.priority,
            "mapped_requirement_ids": ids,
            "disposition": status,
        })
    return report


def coverage_warning(entries: list[dict]) -> str | None:
    unresolved = sum(x["disposition"] != "covered" for x in entries)
    if not unresolved:
        return None
    return (f"JD source-coverage review: {unresolved} explicit employer clause(s) "
            "have no unique frozen requirement mapping. Review the original "
            "JD wording before approving; this is not a candidate deficiency.")

# Original JD clause coverage in v50

`cv_ranker.jd_coverage.explicit_clause_coverage` inventories **structurally explicit** employer hiring clauses found under identifiable Required/Preferred sections by reusing the existing source-only `structural_hints` parser. It records each clause's authentic source text, original line numbers, inferred heading priority, frozen `R###` references and one of: `covered`, `multiple_possible_mappings`, `unmapped_review_required`.

At initial JD extraction, `CVRanker.prepare_jd_review()` adds the coverage rows to `JDReviewDraft.diagnostics` before `final_denominator`. Approval with `approve_jd_rows()` recomputes coverage from the **approved edited rows**. The Streamlit review panel displays the table in an expander, expanded for unresolved clauses. If clauses are omitted/merged, a warning is shown; such warnings are **not** additional requirements and do not automatically change scores. They are relevant before freeze and included in source-bound report diagnostics.

## Critical limitations

- Structural headings and bullet/list sections are covered. The map is **not** a guarantee that every semantically binding, unbulleted or narrative qualification has been extracted. A human must read narrative JDs and approve source interpretation.
- A containment-based mapping is not a verified Boolean interpretation. If one broad frozen R quote overlaps multiple separate hiring clauses, the supervisor must examine whether they belong in one criterion or several; automatic source containment is only a lead.
- Original page/part provenance beyond physical JD line numbers, multi-span inherited heading conditions and source-cited reviewer exclusion reasons remain future work.
- If an unreadable PDF page may contain qualifications, the existing document reader blocks rather than fabricating a negative. v50 does not add OCR; obtain a readable copy or independently reviewed transcription.

## Offline verification

Use `python -m pytest -q tests/test_v4964_coverage_semantics_diagnostics.py` to confirm source coverage, exact physical lines, review recomputation, and correction behavior. This does not replace independently adjudicated JD extraction recall/precision tests.

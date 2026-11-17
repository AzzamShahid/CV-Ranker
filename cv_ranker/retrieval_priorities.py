"""Domain-neutral lexical prioritization of CV *retrieval leads*, never proof.

A nearest-neighbour search can give broad field-related work higher cosine
similarity than the direct responsibility. This lightweight second ordering
puts the JD's own informative words near the front while keeping dense-only
sources available for paraphrases. No occupation, product, degree or skill is
considered equivalent to another here, and no score comes from this module.
"""
from __future__ import annotations

import re

# Stopwords describe universal JD grammar, not a list of professions/tools.
_GRAMMAR = frozenset({
    "the", "and", "for", "with", "from", "into", "onto", "that", "this", "those",
    "these", "through", "using", "about", "their", "each", "your", "under",
    "work", "working", "ability", "experience", "required", "preferred",
    "professional", "knowledge", "proficiency", "skills", "skill", "within",
    "across", "over", "between", "must", "should", "have", "will", "need",
    "manage", "management", "develop", "development", "conduct", "perform",
    "operate", "implement", "implementation", "support", "deliver", "design",
    "system", "systems", "tools", "including", "related", "reporting",
})


def _terms(value: str) -> set[str]:
    return {term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9+#-]*", value)
            if len(term) >= 3 and term.casefold() not in _GRAMMAR}


def source_overlap_score(jd_statement: str, cv_passage: str) -> int:
    """Rank candidate source *selection*, not semantic matching or points.

    Exact terms score higher than a shared, sufficiently long word stem;
    the conservative stem comparison captures e.g. plans/planning without
    deciding that different technologies or occupations are equivalent.
    """
    sought = _terms(jd_statement)
    offered = _terms(cv_passage)
    exact = sought & offered
    remaining = sought - exact
    stems = sum(bool(len(word) >= 6 and any(
        len(candidate) >= 6 and word[:5] == candidate[:5]
        for candidate in offered)) for word in remaining)
    return 3 * len(exact) + stems


def prioritize_source_ids(jd_statement: str, source_ids: list[str],
                          source_texts: dict[str, str]) -> list[str]:
    """Stable order: direct lexical context first, original dense order second.

    A weak/zero overlap does not discard semantic leads. All arguments come
    from the current approved JD and original candidate's own source ledger.
    """
    original = list(dict.fromkeys(sid for sid in source_ids if sid in source_texts))
    order = {sid: index for index, sid in enumerate(original)}
    return sorted(original, key=lambda sid: (
        -source_overlap_score(jd_statement, source_texts[sid]), order[sid]))

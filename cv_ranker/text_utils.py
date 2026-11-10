import re
import unicodedata


NEGATION_PATTERNS = [
    r"\bno\s+(?:professional\s+|practical\s+|hands[- ]on\s+)?experience\s+(?:with|in|using|of)\b",
    r"\bno\s+(?:professional\s+|practical\s+|hands[- ]on\s+)?(?:experience|knowledge|exposure)\s+(?:with|in|using|of)\b",
    r"\bno\s+experience\b",
    r"\bnot\s+familiar\s+with\b",
    r"\bunfamiliar\s+with\b",
    r"\bnot\s+experienced\s+(?:with|in)\b",
    r"\bnot\s+proficient\s+(?:with|in)\b",
    r"\bno\s+proficiency\s+(?:with|in)\b",
    r"\bnever\s+(?:used|worked\s+(?:with|on)|operated)\b",
    r"\b(?:i|we|they|he|she)\s+(?:have|has)\s+not\s+(?:used|worked\s+(?:with|on))\b",
    r"\b(?:i|we|they|he|she)\s+haven['’]?t\s+(?:used|worked\s+(?:with|on))\b",
    r"\b(?:i|we|they|he|she)\s+(?:did\s+not|didn['’]?t)\s+(?:use|work\s+(?:with|on))\b",
    r"\bnot\s+used\b",
    r"\bnone\b",
    r"\bwithout\s+experience\b",
    r"\black(?:s|ing)?\s+(?:professional\s+|practical\s+)?experience\b",
    r"\bdo(?:es)?\s+not\s+have\s+experience\b",
    r"\bdon['’]?t\s+have\s+experience\b",
    r"\bdo(?:es)?\s+not\s+know\b",
    r"\bworked\s+with\s+a\s+team\s+that\s+used\b",
]

UNCERTAINTY_PATTERNS = [
    r"\bcurrently\s+learning\b",
    r"\blearning\b",
    r"\bplanning\s+to\s+learn\b",
    r"\bwant(?:s)?\s+to\s+learn\b",
    r"\binterested\s+in\s+learning\b",
    r"\bsome\s+exposure\b",
    r"\bbasic\s+exposure\b",
    r"\blimited\s+exposure\b",
    r"\bintroductory\s+exposure\b",
    r"\bbasic\s+familiarity\b",
    r"\blimited\s+familiarity\b",
    r"\bbasic\s+knowledge\b",
    r"\blimited\s+knowledge\b",
    r"\bcurrently\s+studying\b",
    r"\bcurrently\s+training\b",
    r"\btraining\s+in\b",
    r"\bpreparing\s+for\b",
    r"\bstudying\b",
    r"\bbeginner\b",
    r"\binterested\s+in\b",
    r"\btheoretical\s+(?:knowledge|understanding|familiarity)\b",
    r"\bcoursework\s+(?:included|covered|involving)\b",
]


def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_whitespace(text: str) -> str:
    return " ".join(normalize_unicode(text).split())


def normalize_for_evidence(text: str) -> str:
    text = normalize_unicode(text)
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def evidence_exists(evidence: str | None, source_text: str) -> bool:
    """Loose exact-text existence check used mainly for JD source quotations."""
    if not evidence:
        return False
    needle = normalize_for_evidence(evidence)
    haystack = normalize_for_evidence(source_text)
    return bool(needle) and needle in haystack


def evidence_source_line_numbers(evidence: str, source_text: str) -> list[int]:
    """Locate an exact quote, including quotations spanning physical PDF lines.

    No fuzzy token matching: joining adjacent source lines solely reconstructs
    whitespace introduced by extraction. Return the original physical lines.
    """
    rows = source_text.splitlines()
    direct = [i for i, row in enumerate(rows, start=1) if evidence_exists(evidence, row)]
    if direct:
        return direct
    needle = normalize_for_evidence(evidence)
    if not needle:
        return []
    for start in range(len(rows)):
        if not rows[start].strip():
            continue
        joined: list[str] = []
        for stop in range(start, min(start + 8, len(rows))):
            if not rows[stop].strip():
                break
            joined.append(rows[stop].strip())
            if stop > start and evidence_exists(evidence, " ".join(joined)):
                return list(range(start + 1, stop + 2))
            if len(normalize_for_evidence(" ".join(joined))) > len(needle) + 240:
                break
    return []


def instruction_like_evidence(text: str | None) -> bool:
    """Reject obvious prompt/instruction text masquerading as candidate evidence."""
    if not text:
        return False
    value = normalize_for_evidence(text)
    patterns = (
        r"^\s*(?:system|assistant|user)\s*:",
        r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
        r"\bmark\s+.{0,80}\s+as\s+(?:matched|not[_ -]?matched|uncertain)\b",
        r"\breturn\s+(?:the\s+)?(?:status\s+)?(?:matched|not[_ -]?matched|uncertain)\b",
        r"\b(?:consider|treat)\s+.{0,80}\s+(?:as\s+)?(?:matched|present|satisfied)\b",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def canonical_key(value: str) -> str:
    value = normalize_for_evidence(value)
    value = re.sub(r"[^\w+#&./-]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def phrase_regex(phrase: str) -> str | None:
    needle = canonical_key(phrase)
    if not needle:
        return None
    # A space, hyphen, underscore or slash between *whole* words is an
    # orthographic variation, not a semantic alias.  Preserve the strict
    # outside boundaries (Go must never match Good, C must not match C++).
    words = needle.split()
    pattern = r"[\s/_-]+".join(re.escape(word) for word in words)
    return rf"(?<![\w+#&]){pattern}(?![\w+#&])"


def phrase_present(phrase: str, text: str) -> bool:
    """Whole-phrase check with token boundaries.

    Prevents substring false positives such as Java->JavaScript, SQL->NoSQL,
    C->communication/C++/C#, and Go->Good.
    """
    pattern = phrase_regex(phrase)
    haystack = canonical_key(text)
    return bool(pattern and haystack and re.search(pattern, haystack, flags=re.IGNORECASE))


def _generic_spelling_key(value: str) -> str:
    """Normalize only spelling/punctuation, never semantic aliases.

    This intentionally does NOT know that NLP means Natural Language Processing,
    Postgres means PostgreSQL, etc. Semantic equivalence belongs to the LLM.
    """
    key = canonical_key(value)
    if not key:
        return ""
    # Collapse punctuation/spacing variants such as Node.js / NodeJS / Node JS.
    # Keep language-significant '+' and '#' intact.
    return re.sub(r"[\s._/-]+", "", key)


def _generic_grammar_key(value: str) -> str:
    """Conservative grammatical identity for deduplication.

    Only acronym plurals are collapsed (APIs->API, SDKs->SDK). This avoids
    corrupting proper technology names such as Pandas or Kubernetes.
    """
    key = canonical_key(value)
    if not key:
        return ""
    canonical_tokens = key.split()
    raw_tokens = normalize_whitespace(value).split()
    if canonical_tokens and raw_tokens:
        raw_last = re.sub(r"[^A-Za-z0-9]+", "", raw_tokens[-1])
        if len(raw_last) >= 3 and raw_last.endswith("s") and raw_last[:-1].isupper():
            canonical_tokens[-1] = canonical_tokens[-1][:-1]
    return " ".join(canonical_tokens)



def equivalent_terms(left: str, right: str) -> bool:
    """Generic spelling/grammar equivalence only; no domain semantic aliases."""
    a, b = canonical_key(left), canonical_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if _generic_spelling_key(a) == _generic_spelling_key(b):
        return True
    return _generic_grammar_key(a) == _generic_grammar_key(b)


def aliases_for(term: str) -> set[str]:
    """Backward-compatible name: returns spelling variants, not semantic aliases."""
    key = canonical_key(term)
    if not key:
        return set()
    variants = {key}
    compact = _generic_spelling_key(key)
    if compact and compact != key:
        variants.add(compact)
    return variants


def extract_or_requirement(text: str) -> str | None:
    """Return a compact explicit alternative requirement.

    Supports ``A or B``, ``A/B`` and ``A and/or B`` when each side is short.
    It deliberately refuses degree/equivalent-experience prose.
    """
    clean = normalize_whitespace(re.sub(r"^\s*(?:[-•*]\s+|\d+[.)]\s+)", "", text or ""))
    clean = clean.strip(" .;:")
    # Editorial explanation of an OR list is not an additional skill. Keep
    # the ORIGINAL quotation in jd_evidence; normalize only option parsing.
    clean = re.sub(r"\s*\(\s*(?:at\s+least\s+one|either\s+one|choose\s+one|one\s+of\s+these)\s*\)$",
                   "", clean, flags=re.IGNORECASE).strip(" .;:")
    clean = re.sub(
        r"^(?:experience|proficiency|knowledge|familiarity|skills?|hands-on experience)\s+(?:with|in|of)\s+",
        "", clean, flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\s+(?:is|are)\s+(?:required|preferred|desired|a plus|mandatory|essential)$",
        "", clean, flags=re.IGNORECASE,
    ).strip(" .;:")
    clean = re.sub(
        r"\s+(?:experience|skills?|knowledge|proficiency|familiarity)$",
        "", clean, flags=re.IGNORECASE,
    ).strip(" .;:")
    if re.search(r"\b(?:degree|equivalent|related field|years? of experience)\b", clean, flags=re.IGNORECASE):
        return None

    if re.search(r"\s+and/or\s+", clean, flags=re.IGNORECASE):
        parts = re.split(r"\s+and/or\s+", clean, flags=re.IGNORECASE)
    elif re.search(r"\s+or\s+", clean, flags=re.IGNORECASE):
        parts = re.split(r"\s+or\s+", clean, flags=re.IGNORECASE)
    elif "/" in clean and clean.count("/") <= 3:
        parts = clean.split("/")
    else:
        return None

    parts = [normalize_whitespace(p) for p in parts]
    if not 2 <= len(parts) <= 4:
        return None
    if any(not p or len(p.split()) > 4 for p in parts):
        return None
    return " or ".join(parts)


def requirement_options(requirement: str) -> list[str]:
    explicit = extract_or_requirement(requirement)
    if not explicit:
        value = normalize_whitespace(requirement)
        return [value] if value else []
    return [normalize_whitespace(p) for p in re.split(r"\s+or\s+", explicit, flags=re.IGNORECASE)]


def requirement_match_terms(requirement: str) -> set[str]:
    """Terms Python may match deterministically: exact requirement/explicit OR options only."""
    return {canonical_key(option) for option in requirement_options(requirement) if canonical_key(option)}


def canonical_equivalence_key(requirement: str) -> str:
    """Generic identity for deduplication; no hardcoded semantic mappings."""
    options = requirement_options(requirement)
    normalized = []
    for option in options:
        grammar = _generic_grammar_key(option)
        spelling = _generic_spelling_key(grammar)
        normalized.append(spelling or grammar)
    normalized = [item for item in normalized if item]
    if len(normalized) > 1:
        return "or:" + "|".join(sorted(set(normalized)))
    return normalized[0] if normalized else ""


def _term_context_ok(term: str, requirement: str, evidence: str) -> bool:
    key = canonical_key(term)
    if not key:
        return False
    if canonical_key(evidence) == key:
        return True
    lower = normalize_for_evidence(evidence)
    technical_cues = (
        "skill", "experience", "experienced", "proficient", "proficiency",
        "knowledge", "familiar", "programming", "language",
        "using ", "used ", "worked with", "built with", "developed with",
    )
    if len(key) <= 2 and key.isalpha():
        return any(cue in lower for cue in technical_cues)
    return True


def evidence_supports_requirement(
    requirement: str,
    evidence: str,
    matched_term: str | None = None,
) -> bool:
    """Lexical helper for deterministic fallback only.

    LLM semantic matches are NOT validated through this function.
    """
    if not evidence:
        return False
    if matched_term:
        if not phrase_present(matched_term, evidence):
            return False
        if not any(equivalent_terms(matched_term, option) for option in requirement_options(requirement)):
            return False
        return _term_context_ok(matched_term, requirement, evidence)
    return any(
        phrase_present(option, evidence) and _term_context_ok(option, requirement, evidence)
        for option in requirement_options(requirement)
    )


def standalone_phrase_line(text: str, phrase: str) -> str | None:
    """Return an explicit standalone/bulleted source line for the phrase if present."""
    target = canonical_key(phrase)
    if not target:
        return None
    for raw_line in normalize_unicode(text).splitlines():
        cleaned = re.sub(r"^\s*(?:[-•*▪●◦·]\s+|\d+[.)]\s+)", "", raw_line).strip()
        if cleaned and canonical_key(cleaned) == target:
            return normalize_whitespace(cleaned)
    return None


def _context_candidates(source_text: str) -> list[str]:
    """Source-preserving lines/sentences used to prevent tiny quote attacks."""
    source = normalize_unicode(source_text)
    values: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        clean = normalize_whitespace(re.sub(r"^\s*(?:[-•*▪●◦·]\s+|\d+[.)]\s+)", "", value))
        key = normalize_for_evidence(clean)
        if clean and key and key not in seen:
            seen.add(key)
            values.append(clean)

    for raw_line in source.splitlines():
        if not raw_line.strip():
            continue
        add(raw_line)
        line = normalize_whitespace(raw_line)
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            add(sentence)

    normalized = normalize_whitespace(re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", source))
    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        add(sentence)
    return values


def _clean_source_line(value: str) -> str:
    return normalize_whitespace(
        re.sub(r"^\s*(?:[-•*▪●◦·]\s+|\d+[.)]\s+)", "", normalize_unicode(value or ""))
    )


def _line_context_prefix(previous: str, current: str) -> str | None:
    """Attach a short preceding heading/cue to a standalone evidence line.

    This preserves meaning for layouts such as ``Currently learning:\nKubernetes``
    and ``No experience with:\nDocker`` while keeping ordinary ``Skills:\nPython``
    positive.
    """
    prev = _clean_source_line(previous)
    cur = _clean_source_line(current)
    if not prev or not cur or len(prev.split()) > 10:
        return None
    if not prev.endswith(":"):
        return None
    cue = prev.casefold()
    contextual = re.search(
        r"\b(?:no|not|never|none|without|learning|learn|studying|study|exposure|"
        r"theoretical|coursework|course|interested|unfamiliar|beginner|limited|basic)\b",
        cue,
        flags=re.IGNORECASE,
    )
    if not contextual:
        return None
    return normalize_whitespace(f"{prev[:-1]} {cur}")


def resolve_contextual_evidence(evidence: str | None, source_text: str) -> str | None:
    """Resolve a model quote to a meaningful source context.

    A one/two-word quote is accepted only when it is a standalone source line. If
    that line is controlled by a short preceding heading/cue, the heading is joined
    deterministically so learning/negation context cannot be stripped away.
    """
    if not evidence:
        return None
    evidence_clean = _clean_source_line(evidence)
    needle = normalize_for_evidence(evidence_clean)
    if not needle:
        return None

    raw_lines = [raw for raw in normalize_unicode(source_text).splitlines() if raw.strip()]
    clean_lines = [_clean_source_line(raw) for raw in raw_lines]
    for index, candidate in enumerate(clean_lines):
        if normalize_for_evidence(candidate) != needle:
            continue
        if index > 0:
            combined = _line_context_prefix(clean_lines[index - 1], candidate)
            if combined is not None:
                return combined
        return candidate

    candidates = _context_candidates(source_text)
    for candidate in candidates:
        if normalize_for_evidence(candidate) == needle:
            return candidate

    word_count = len(needle.split())
    if word_count >= 5 or len(needle) >= 40:
        for candidate in candidates:
            hay = normalize_for_evidence(candidate)
            if needle in hay:
                return candidate
    return None


def classify_evidence_tone(evidence: str | None) -> str:
    if not evidence:
        return "neutral"
    text = normalize_for_evidence(evidence)
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in NEGATION_PATTERNS):
        return "negated"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in UNCERTAINTY_PATTERNS):
        return "uncertain"
    return "positive"


def _present_target_term(evidence: str, requirement: str, matched_term: str | None = None) -> str | None:
    if matched_term and phrase_present(matched_term, evidence):
        return matched_term
    for term in sorted(requirement_match_terms(requirement), key=len, reverse=True):
        if phrase_present(term, evidence):
            return term
    return None


def non_candidate_requirement_copy(text: str | None) -> bool:
    """Flag explicit non-claim/job-ad passages, never candidate accomplishments.

    This is a provenance veto, not a domain-specific skill list. Only explicit
    self-disclaimers or job-ad introductions trigger it.
    """
    source = normalize_for_evidence(text or "")
    return bool(re.search(
        r"\b(?:target\s+job\s+description|copied\s+(?:job\s+)?requirements?|"
        r"(?:^|: )job\s+advertisement\s*:|(?:^|: )job\s+posting\s*:|"
        r"not\s+a\s+claim\s+of\s+experience|"
        r"(?:requirements?|skills?)\s+copied\s+from\s+(?:the\s+)?(?:job|role))\b",
        source,
    ))


def _coordinated_denial_scope(text: str, target: str) -> bool:
    """Block explicit negation governing comma/or/and enumerations.

    Span is bounded to one sentence/semicolon clause and a short prefix,
    avoiding a negative Redis sentence poisoning an unrelated Python claim.
    """
    source = normalize_for_evidence(text)
    pattern = phrase_regex(canonical_key(target)) or re.escape(canonical_key(target))
    for hit in re.finditer(pattern, source, flags=re.IGNORECASE):
        # Work inside punctuation-delimited clauses. Tool names like Node.js are
        # kept intact by the existing normalizer / phrase expression.
        start = max(source.rfind(';', 0, hit.start()), source.rfind('!', 0, hit.start()),
                    source.rfind('?', 0, hit.start()), source.rfind('. ', 0, hit.start())) + 1
        prefix = source[start:hit.start()]
        if len(prefix) > 190:
            prefix = prefix[-190:]
        # "has not used A or B", "no experience with A, B, C" and
        # "no professional A, B or C experience claimed".
        cue = re.search(
            r"\b(?:no\s+(?:direct\s+|hands-on\s+|professional\s+|practical\s+)?"
            r"(?:(?:experience|knowledge|exposure|proficiency)\s+(?:with|in|of|using)\s+)?|"
            r"(?:have|has|had|did)\s+not\s+(?:used?|worked\s+with|developed|built)\s+|"
            r"never\s+(?:used|worked\s+with|developed)\s+|"
            r"(?:haven't|hasn't|didn't)\s+(?:used?|worked\s+with|developed)\s+)"
            r"[^.;!?]{0,170}$",
            prefix,
        )
        if not cue:
            continue
        between = prefix[cue.start():]
        if re.search(r"\b(?:but|however|although|whereas|except|yet)\b", between):
            continue
        # The cue must be attached to a list, not a separate action clause.
        if re.search(r"\b(?:built|developed|implemented|deployed|trained|created)\b", between):
            continue
        return True
    return False


def _coordinated_learning_scope(text: str, target: str) -> bool:
    """Keep a future/learning verb's scope across a short coordinated list.

    ``Plans to learn A, B and C`` makes all three tentative; none is a
    current skill claim. The rule is grammatical, not a list of professions or
    products. It stops at a new sentence, contrasting conjunction, or a
    separate completed-work action, so ``learning A, but built B`` cannot
    erase the completed B assertion.
    """
    source = normalize_for_evidence(text)
    pattern = phrase_regex(canonical_key(target)) or re.escape(canonical_key(target))
    for hit in re.finditer(pattern, source, flags=re.IGNORECASE):
        start = max(source.rfind(';', 0, hit.start()), source.rfind('!', 0, hit.start()),
                    source.rfind('?', 0, hit.start()), source.rfind('. ', 0, hit.start())) + 1
        prefix = source[start:hit.start()][-190:]
        cue = re.search(
            r"\b(?:(?:currently\s+)?(?:learning|exploring|studying)\s+|"
            r"(?:plans?|planning|intends?|hopes?|wants?)\s+to\s+(?:learn|study|explore)\s+|"
            r"(?:currently\s+)?(?:training|experimenting)\s+(?:in|on|with)\s+)"
            r"[^.;!?]{0,170}$",
            prefix,
        )
        if not cue:
            continue
        if cue.group(0).startswith('learning '):
            # 'Deep learning and X' describes a discipline, not the act of
            # learning X. Require affirmative learning grammar to bind a list.
            before = prefix[:cue.start()].rstrip()
            previous = re.search(r"\b([a-z]+)$", before)
            if (before and not before.endswith(':')
                    and (not previous or previous.group(1) not in {
                        'am', 'is', 'are', 'was', 'were', 'been', 'currently',
                        'just', 'still', 'only', 'started', 'began',
                    })):
                continue
        between = prefix[cue.start():]
        if re.search(r"\b(?:but|however|although|whereas|except|yet)\b", between):
            continue
        if re.search(r"\b(?:built|developed|implemented|deployed|shipped|delivered|created)\b", between):
            continue
        return True
    return False


def classify_requirement_tone(
    evidence: str | None,
    requirement: str,
    matched_term: str | None = None,
) -> str:
    """Classify tone around the term that actually supports this requirement."""
    if not evidence:
        return "neutral"
    text = normalize_for_evidence(evidence)
    if non_candidate_requirement_copy(evidence):
        return "negated"
    target = _present_target_term(evidence, requirement, matched_term)
    if not target:
        return "neutral"
    if _coordinated_denial_scope(evidence, target):
        return "negated"
    if _coordinated_learning_scope(evidence, target):
        return "uncertain"

    req = canonical_key(target)
    q = phrase_regex(req) or re.escape(req)
    negative_patterns = [
        rf"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?experience\s+(?:with|in|using|of)\s+{q}",
        rf"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?(?:knowledge|exposure)\s+(?:of|to|with|in)\s+{q}",
        rf"\bno\s+(?:direct\s+|hands-on\s+|professional\s+)?{q}\s+(?:experience|knowledge|exposure|usage)\b",
        rf"\bno\s+(?:direct\s+|hands-on\s+|professional\s+)?experience\s+(?:with|in|using|of)\s+{q}",
        rf"\bno\s+{q}\s+evidence\b",
        rf"\bnot\s+familiar\s+with\s+{q}",
        rf"\bunfamiliar\s+with\s+{q}",
        rf"\bnot\s+experienced\s+(?:with|in)\s+{q}",
        rf"\bnot\s+proficient\s+(?:with|in)\s+{q}",
        rf"\bno\s+proficiency\s+(?:with|in)\s+{q}",
        rf"\bnever\s+(?:used|worked\s+(?:with|on)|operated)\s+{q}",
        rf"\b(?:i|we|they|he|she)\s+(?:have|has)\s+not\s+(?:used|worked\s+(?:with|on))\s+{q}",
        rf"\b(?:have|has)\s+not\s+(?:used|worked\s+(?:with|on))\s+{q}",
        rf"\b(?:i|we|they|he|she)\s+haven['’]?t\s+(?:used|worked\s+(?:with|on))\s+{q}",
        rf"\bhaven['’]?t\s+(?:used|worked\s+(?:with|on))\s+{q}",
        rf"\b(?:i|we|they|he|she)\s+(?:did\s+not|didn['’]?t)\s+(?:use|work\s+(?:with|on))\s+{q}",
        rf"\b(?:did\s+not|didn['’]?t)\s+(?:use|work\s+(?:with|on))\s+{q}",
        rf"\b(?:do|does)\s+not\s+use\s+{q}",
        rf"\b(?:don['’]?t|doesn['’]?t)\s+use\s+{q}",
        rf"\bnot\s+used\s+{q}",
        rf"{q}\s+(?:is|was|were)\s+not\s+used\b",
        rf"{q}\s*[:=-]\s*(?:none|no|nil|n/a)\b",
        rf"\bwithout\s+{q}\s+(?:experience|knowledge|exposure)\b",
        rf"\bwithout\s+(?:using\s+)?{q}\b",
        # Contrast/comparison is not an affirmative claim to the named tool.
        # A CV saying "Haystack rather than LangChain" must not get LangChain credit.
        rf"\b(?:rather\s+than|instead\s+of|as\s+an\s+alternative\s+to)\s+{q}\b",
        rf"\black(?:s|ing)?\s+(?:professional\s+|practical\s+)?experience\s+(?:with|in|using)\s+{q}",
        rf"\bdo(?:es)?\s+not\s+have\s+experience\s+(?:with|in|using)\s+{q}",
        rf"\bdon['’]?t\s+have\s+experience\s+(?:with|in|using)\s+{q}",
        rf"\bdo(?:es)?\s+not\s+know\s+{q}",
        rf"\bworked\s+with\s+a\s+team\s+that\s+used\s+{q}",
        rf"\b(?:the\s+)?team\s+used\s+{q}",
        rf"\b(?:the\s+)?project\s+(?:planned\s+to\s+use|planned\s+to\s+migrate\s+to)\s+{q}",
    ]
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in negative_patterns):
        return "negated"

    target_match = re.search(q, text, flags=re.IGNORECASE)
    if target_match:
        target_start = target_match.start()
        scoped_negative_cues = [
            r"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?experience\s+(?:with|in|using|of)\b",
            r"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?(?:knowledge|exposure)\s+(?:of|to|with|in)\b",
            r"\bnot\s+familiar\s+with\b",
            r"\bunfamiliar\s+with\b",
            r"\bnot\s+(?:experienced|proficient)\s+(?:with|in)\b",
            r"\bnever\s+(?:used|worked\s+(?:with|on)|operated)\b",
            r"\b(?:i|we|they|he|she)\s+(?:have|has)\s+not\s+(?:used|worked\s+(?:with|on))\b",
            r"\b(?:i|we|they|he|she)\s+haven['’]?t\s+(?:used|worked\s+(?:with|on))\b",
            r"\b(?:i|we|they|he|she)\s+(?:did\s+not|didn['’]?t)\s+(?:use|work\s+(?:with|on))\b",
        ]
        contrast = re.compile(
            r"\b(?:but|however|although|yet)\b|"
            r"(?:,|;)\s*(?:strong|experienced|proficient|skilled|familiar|knowledgeable)\b|"
            r"\band\s+(?:strong|experienced|proficient|skilled|familiar|knowledgeable)\b",
            flags=re.IGNORECASE,
        )
        for cue_pattern in scoped_negative_cues:
            for cue in re.finditer(cue_pattern, text, flags=re.IGNORECASE):
                if cue.end() <= target_start and target_start - cue.end() <= 140:
                    between = text[cue.end():target_start]
                    if not contrast.search(between):
                        return "negated"

    uncertain_patterns = [
        rf"\bcurrently\s+learning\s+(?:about\s+)?{q}",
        rf"\b(?:currently\s+)?exploring\s+(?:about\s+)?{q}\b",
        rf"\bcurrently\s+exploring\b[^.;!?]{{0,95}}\b{q}\b",
        rf"\b{q}\s+(?:tutorial|tutorials|practice\s+exercise|practice\s+exercises)\b",
        rf"\b(?:currently\s+)?experimenting\s+with\b[^.;!?]{{0,95}}\b{q}\b",
        rf"\bplanning\s+to\s+learn\s+(?:about\s+)?{q}",
        rf"\bwant(?:s)?\s+to\s+learn\s+(?:about\s+)?{q}",
        rf"\binterested\s+in\s+learning\s+(?:about\s+)?{q}",
        rf"\blearning\s+(?:about\s+)?{q}",
        rf"\b(?:some|basic|limited|introductory)?\s*exposure\s+(?:to|with|in)\s+{q}",
        rf"\b(?:some|basic|limited)\s+familiarity\s+(?:with|in)\s+{q}",
        rf"\b(?:some|basic|limited)\s+knowledge\s+(?:of|in)\s+{q}",
        rf"\bcurrently\s+studying\s+(?:about\s+)?{q}",
        rf"\bcurrently\s+training\s+(?:in|on|with)\s+{q}",
        rf"\btraining\s+(?:in|on|with)\s+{q}",
        rf"\bpreparing\s+for\s+(?:a\s+|an\s+)?{q}\b",
        rf"\bstudying\s+(?:about\s+)?{q}",
        rf"\b(?:coursework|course)\s+(?:in|on)\s+{q}",
        rf"\btaking\s+(?:a\s+)?course\s+(?:in|on)\s+{q}",
        rf"\bbeginner(?:-level)?\s+(?:in|with)\s+{q}",
        rf"\binterested\s+in\s+{q}",
        rf"\btheoretical\s+(?:knowledge|understanding|familiarity)\s+(?:of|with|in)\s+{q}",
        rf"\bcoursework\s+(?:included|covered|involving)\s+{q}",
        rf"\bskills?\s+(?:i|we)?\s*(?:want|plan)\s+to\s+learn\s+{q}",
    ]
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in uncertain_patterns):
        return "uncertain"

    if target_match:
        target_start = target_match.start()
        scoped_uncertain_cues = [
            r"\bcurrently\s+learning\b",
            r"\bplanning\s+to\s+learn\b",
    r"\bwant(?:s)?\s+to\s+learn\b",
            r"\binterested\s+in\s+learning\b",
            r"\bcurrently\s+studying\b",
            r"\bcurrently\s+training\b",
            r"\btraining\s+(?:in|on|with)\b",
            r"\bpreparing\s+for\b",
            r"\bstudying\b",
            r"\b(?:some|basic|limited|introductory)\s+exposure\s+(?:to|with|in)\b",
            r"\b(?:basic|limited)\s+(?:familiarity|knowledge)\s+(?:with|in|of)\b",
        ]
        contrast = re.compile(r"\b(?:but|however|although|yet)\b", flags=re.IGNORECASE)
        for cue_pattern in scoped_uncertain_cues:
            for cue in re.finditer(cue_pattern, text, flags=re.IGNORECASE):
                if cue.end() <= target_start and target_start - cue.end() <= 140:
                    between = text[cue.end():target_start]
                    if not contrast.search(between):
                        return "uncertain"

    return "positive"


def find_contexts(text: str, phrase: str, limit: int = 12) -> list[str]:
    """Return source contexts containing the whole phrase, in document order.

    Context is sentence/clause-local so a negation about Redis cannot contaminate
    Python later in the same line. Standalone lines inherit a short preceding
    colon-heading so ``Currently learning:\nKubernetes`` keeps its true meaning.
    """
    if not phrase:
        return []
    source = normalize_unicode(text)
    contexts: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        clean = normalize_whitespace(value)
        key = normalize_for_evidence(clean)
        if clean and key not in seen:
            seen.add(key)
            contexts.append(clean)

    raw_lines = [raw for raw in source.splitlines() if raw.strip()]
    clean_lines = [_clean_source_line(raw) for raw in raw_lines]
    for index, line in enumerate(clean_lines):
        if not phrase_present(phrase, line):
            continue
        # Prefer the smallest sentence/semicolon clause containing the term.
        pieces = [p.strip() for p in re.split(r"(?<=[.!?;])\s+", line) if p.strip()]
        selected = [piece for piece in pieces if phrase_present(phrase, piece)]
        if selected:
            for piece in selected:
                # If the phrase is itself a standalone line, inherit a contextual heading.
                if canonical_key(piece) == canonical_key(phrase) and index > 0:
                    combined = _line_context_prefix(clean_lines[index - 1], piece)
                    add(combined or piece)
                else:
                    add(piece)
                if len(contexts) >= limit:
                    return contexts
        else:
            add(line)
            if len(contexts) >= limit:
                return contexts

    # Handle PDF/text extraction where a phrase can be split by line wrapping.
    normalized = normalize_whitespace(source)
    for sentence in re.split(r"(?<=[.!?;])\s+", normalized):
        if phrase_present(phrase, sentence):
            add(sentence)
            if len(contexts) >= limit:
                break
    return contexts


def requirement_tones_in_source(source_text: str, requirement: str) -> set[str]:
    """Collect deterministic tones for all direct/alias mentions of a requirement."""
    tones: set[str] = set()
    for term in sorted(requirement_match_terms(requirement), key=len, reverse=True):
        for context in find_contexts(source_text, term):
            if instruction_like_evidence(context):
                continue
            tones.add(classify_requirement_tone(context, requirement, term))
    return tones


def find_context(text: str, phrase: str, radius: int = 140) -> str | None:
    del radius
    contexts = find_contexts(text, phrase, limit=1)
    return contexts[0] if contexts else None

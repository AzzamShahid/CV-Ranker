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
    r"\bstudying\b",
    r"\bbeginner\b",
    r"\binterested\s+in\b",
    r"\btheoretical\s+(?:knowledge|understanding|familiarity)\b",
    r"\bcoursework\s+(?:included|covered|involving)\b",
]

# Deliberately tiny direct-equivalence list. This is not a skill dictionary and does
# not grant transferable credit; it only normalizes common names/abbreviations for
# the same thing.
_ALIAS_GROUPS = (
    frozenset({"nlp", "natural language processing"}),
    frozenset({"ml", "machine learning"}),
    frozenset({"dl", "deep learning"}),
    frozenset({"postgres", "postgresql"}),
    frozenset({"node", "node.js", "nodejs", "node js"}),
    frozenset({"js", "javascript"}),
    frozenset({"k8s", "kubernetes"}),
    frozenset({"ms excel", "microsoft excel"}),
    frozenset({"gcp", "google cloud", "google cloud platform"}),
)


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
    return rf"(?<![\w+#&]){re.escape(needle)}(?![\w+#&])"


def phrase_present(phrase: str, text: str) -> bool:
    """Whole-phrase check with token boundaries.

    Prevents substring false positives such as Java->JavaScript, SQL->NoSQL,
    C->communication/C++/C#, and Go->Good.
    """
    pattern = phrase_regex(phrase)
    haystack = canonical_key(text)
    return bool(pattern and haystack and re.search(pattern, haystack, flags=re.IGNORECASE))


def _alias_group(value: str) -> frozenset[str] | None:
    key = canonical_key(value)
    for group in _ALIAS_GROUPS:
        if key in group:
            return group
    return None


def equivalent_terms(left: str, right: str) -> bool:
    a, b = canonical_key(left), canonical_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    group = _alias_group(a)
    return bool(group and b in group)


def aliases_for(term: str) -> set[str]:
    key = canonical_key(term)
    group = _alias_group(key)
    return set(group) if group else ({key} if key else set())


def extract_or_requirement(text: str) -> str | None:
    """Return a simple explicit A-or-B requirement, stripping common wrappers.

    This intentionally handles only compact alternatives. It does not try to parse
    prose such as degree/equivalent-experience clauses.
    """
    clean = normalize_whitespace(re.sub(r"^\s*(?:[-•*]\s+|\d+[.)]\s+)", "", text or ""))
    clean = clean.strip(" .;:")
    clean = re.sub(
        r"^(?:experience|proficiency|knowledge|familiarity|skills?|hands-on experience)\s+(?:with|in|of)\s+",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\s+(?:is|are)\s+(?:required|preferred|desired|a plus|mandatory|essential)$",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip(" .;:")
    # Preserve the alternatives while stripping a shared trailing wrapper.
    clean = re.sub(
        r"\s+(?:experience|skills?|knowledge|proficiency|familiarity)$",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip(" .;:")
    if re.search(r"\b(?:degree|equivalent|related field|years? of experience)\b", clean, flags=re.IGNORECASE):
        return None
    parts = [normalize_whitespace(p) for p in re.split(r"\s+or\s+", clean, flags=re.IGNORECASE)]
    if not 2 <= len(parts) <= 4:
        return None
    if any(not p or len(p.split()) > 4 for p in parts):
        return None
    return " or ".join(parts)


def requirement_options(requirement: str) -> list[str]:
    explicit = extract_or_requirement(requirement)
    if not explicit:
        return [normalize_whitespace(requirement)] if normalize_whitespace(requirement) else []
    return [normalize_whitespace(p) for p in re.split(r"\s+or\s+", explicit, flags=re.IGNORECASE)]


def requirement_match_terms(requirement: str) -> set[str]:
    terms: set[str] = set()
    for option in requirement_options(requirement):
        terms.update(aliases_for(option))
    return {term for term in terms if term}


def canonical_equivalence_key(requirement: str) -> str:
    options = requirement_options(requirement)
    normalized: list[str] = []
    for option in options:
        group = _alias_group(option)
        normalized.append(sorted(group)[0] if group else canonical_key(option))
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
        "knowledge", "familiar", "programming", "language", "developer",
        "development", "backend", "frontend", "server", "runtime", "web",
        "using ", "used ", "worked with", "built with", "developed with",
    )
    if len(key) <= 2 and key.isalpha():
        return any(cue in lower for cue in technical_cues)
    if key == "node" and any(canonical_key(option) == "node.js" for option in requirement_options(requirement)):
        node_cues = technical_cues + ("javascript", "npm", "express")
        return any(cue in lower for cue in node_cues)
    return True


def evidence_supports_requirement(
    requirement: str,
    evidence: str,
    matched_term: str | None = None,
) -> bool:
    """Require evidence to mention the requirement or a small safe direct alias."""
    if not evidence:
        return False
    options = requirement_options(requirement)
    if matched_term:
        if not phrase_present(matched_term, evidence):
            return False
        if not any(equivalent_terms(matched_term, option) for option in options):
            return False
        return _term_context_ok(matched_term, requirement, evidence)
    for term in requirement_match_terms(requirement):
        if phrase_present(term, evidence) and _term_context_ok(term, requirement, evidence):
            return True
    return False


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
    if word_count >= 1 or len(needle) >= 40:
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


def classify_requirement_tone(
    evidence: str | None,
    requirement: str,
    matched_term: str | None = None,
) -> str:
    """Classify tone around the term that actually supports this requirement."""
    if not evidence:
        return "neutral"
    text = normalize_for_evidence(evidence)
    target = _present_target_term(evidence, requirement, matched_term)
    if not target:
        return "neutral"

    req = canonical_key(target)
    q = phrase_regex(req) or re.escape(req)
    negative_patterns = [
        rf"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?experience\s+(?:with|in|using|of)\s+{q}",
        rf"\bno\s+(?:professional\s+|practical\s+|hands-on\s+)?(?:knowledge|exposure)\s+(?:of|to|with|in)\s+{q}",
        rf"\bno\s+{q}\s+(?:experience|knowledge|exposure)\b",
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
        rf"\bplanning\s+to\s+learn\s+(?:about\s+)?{q}",
        rf"\bwant(?:s)?\s+to\s+learn\s+(?:about\s+)?{q}",
        rf"\binterested\s+in\s+learning\s+(?:about\s+)?{q}",
        rf"\blearning\s+(?:about\s+)?{q}",
        rf"\b(?:some|basic|limited|introductory)?\s*exposure\s+(?:to|with|in)\s+{q}",
        rf"\b(?:some|basic|limited)\s+familiarity\s+(?:with|in)\s+{q}",
        rf"\b(?:some|basic|limited)\s+knowledge\s+(?:of|in)\s+{q}",
        rf"\bcurrently\s+studying\s+(?:about\s+)?{q}",
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

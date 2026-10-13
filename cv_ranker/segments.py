"""Deterministic resume evidence segments for source-grounded LLM citations.

The LLM cites segment IDs instead of copying evidence text. Python then owns the
exact source text, avoiding quote-copy failures caused by PDF wrapping or short
snippets such as "Python".
"""
from dataclasses import dataclass
import re

from .text_utils import canonical_key, normalize_unicode, normalize_whitespace


@dataclass(frozen=True)
class ResumeSegment:
    segment_id: str
    section: str
    text: str
    # Physical source lines are kept even when display text joins PDF wraps.
    # Numeric constraints must never infer a relationship from a display join.
    source_lines: tuple[str, ...] = ()


KNOWN_HEADINGS = {
    "professional summary": "summary",
    "summary": "summary",
    "profile": "summary",
    "professional profile": "summary",
    "education": "education",
    "academic background": "education",
    "technical skills": "skills",
    "skills": "skills",
    "core skills": "skills",
    "key skills": "skills",
    "competencies": "skills",
    "core competencies": "skills",
    "tools": "skills",
    "technologies": "skills",
    "professional experience": "experience",
    "work experience": "experience",
    "work history": "experience",
    "employment history": "experience",
    "experience": "experience",
    "ai projects": "projects",
    "projects": "projects",
    "achievements publication leadership": "achievements",
    "achievements publication & leadership": "achievements",
    "achievements": "achievements",
    "certifications": "certifications",
    "certifications & courses": "certifications",
    "certificates": "certifications",
    "requirements": "non_candidate",
    "required skills": "non_candidate",
    "preferred skills": "non_candidate",
    "desired skills": "non_candidate",
    "job description": "non_candidate",
    "minimum qualifications": "non_candidate",
    "job requirements": "non_candidate",
    "candidate requirements": "non_candidate",
    "minimum requirements": "non_candidate",
    "required qualifications": "non_candidate",
    "must have": "non_candidate",
    "desired qualifications": "non_candidate",
    "position requirements": "non_candidate",
}

_BULLET_RE = re.compile(r"^\s*(?:[-•*▪●◦·]\s*|\d+[.)]\s+)")
_INLINE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+/#& ._-]{0,32}:\s*\S")


def _clean(raw: str) -> str:
    raw = normalize_unicode(raw or "").replace("\u200b", "")
    return normalize_whitespace(_BULLET_RE.sub("", raw).strip())


def _heading(line: str) -> str | None:
    clean = _clean(line).rstrip(":").strip()
    key = canonical_key(clean)
    if key in KNOWN_HEADINGS:
        return KNOWN_HEADINGS[key]
    # Only known headings are headings. Arbitrary ALL-CAPS tokens such as
    # AWS, GCP, NLP and PYTHON are resume evidence, not section names.
    return None


# Physical-line control phrases are part of the *following* compact claims.
# They may wrap in PDF/DOCX extraction without a colon, and can govern a list.
# No profession-specific names or skill equivalences are used here.
_HANGING_QUALIFIER_RE = re.compile(
    r"(?i)^\s*(?:(?:i|we)\s+(?:have\s+)?)?"
    r"(?:no\s+(?:(?:professional|practical|hands-on)\s+)?"
    r"(?:experience|knowledge|exposure|proficiency)\s+(?:with|in|of|to)|"
    r"never\s+(?:used|worked\s+with)|"
    r"not\s+(?:familiar|proficient|experienced)\s+(?:with|in)|"
    r"currently\s+(?:learning|studying)|"
    r"learning|studying|preparing\s+for|interested\s+in|"
    r"planning\s+to\s+(?:learn|study))\s*:?\s*$"
)

_RECRUITER_PREAMBLE_RE = re.compile(
    r"(?i)^\s*(?:we\s+(?:require|seek|are\s+looking\s+for)|"
    r"candidate\s+(?:must|should)|applicants?\s+(?:must|should)|"
    r"must\s+have|(?:job\s+)?requirements?|required|desired|"
    r"what\s+we\s+(?:need|require))\s*:?\s*$"
)

_BARE_CLAIM_EXCLUDED = re.compile(
    r"(?i)^(?:no|not|never|without|currently|learning|studying|preparing|pending|"
    r"expected|interested|planning|seeking|requires?|required|must|should|"
    r"candidate|applicant|job|position|bachelor|master|bsc|msc|phd|"
    r"graduated|expired|valid|active|license|licence|certified)\b"
)


def _compact_item(value: str) -> bool:
    """Layout only: compact standalone resume list entry, never a semantic skill map."""
    value = normalize_whitespace(value)
    if not 1 <= len(value.split()) <= 5 or len(value) > 65:
        return False
    if value.endswith((".", "!", "?", ":", ",", ";")) or ":" in value:
        return False
    if _BARE_CLAIM_EXCLUDED.search(value):
        return False
    if re.search(r"(?i)\b(?:years?|yrs?|experience|worked|working|used|using|"
                 r"developed|built|managed|handled|implemented|202[0-9]|201[0-9])\b", value):
        return False
    return bool(re.search(r"[A-Za-z]", value))


def segment_resume(text: str) -> list[ResumeSegment]:
    """Build source-grounded segments without inventing skill/tenure adjacency.

    Preserve every physical line in ``source_lines``. Infer an *unheaded list*
    only for two or more neighbouring compact entries: a document layout fact,
    not a dictionary of professions or skills. A solitary role/title is never
    promoted to a skills section by this heuristic.
    """
    # Retain blank-line boundaries: they terminate the scope of a dangling
    # negation/learning cue, rather than silently attaching it to a new section.
    raw_lines = []
    blank_before = []
    had_blank = False
    for raw in normalize_unicode(text or "").splitlines():
        if raw.strip():
            raw_lines.append(raw)
            blank_before.append(had_blank)
            had_blank = False
        else:
            had_blank = True
    cleaned = [_clean(raw) for raw in raw_lines]

    segments: list[ResumeSegment] = []
    section = "other"
    buffer: list[str] = []
    hanging_qualifier: str | None = None

    def append_segment(value: str, source_lines: tuple[str, ...], sec: str) -> None:
        if value:
            segments.append(ResumeSegment(f"S{len(segments)+1:03d}", sec,
                                          value, source_lines))

    def flush() -> None:
        nonlocal buffer
        if buffer:
            append_segment(normalize_whitespace(" ".join(buffer)), tuple(buffer), section)
            buffer = []

    for i, raw in enumerate(raw_lines):
        clean = cleaned[i]
        if not clean:
            continue
        if blank_before[i]:
            hanging_qualifier = None
        heading = _heading(raw)
        if heading is not None:
            flush()
            hanging_qualifier = None
            if section == "non_candidate" and heading != "non_candidate":
                # A copied JD often contains nested "Skills" / "Experience"
                # headings. Those headings alone cannot authenticate a resume
                # claim. Resume-specific re-entry headings are more explicit.
                trusted_reentry = {
                    "professional summary", "professional profile", "work history",
                    "professional experience", "employment history",
                    "academic background", "ai projects", "achievements",
                }
                if canonical_key(_clean(raw).rstrip(":")) not in trusted_reentry:
                    continue
            section = heading
            continue
        if _RECRUITER_PREAMBLE_RE.fullmatch(clean):
            # An unheaded job-ad preamble controls subsequent lines, not a
            # candidate claim. Remain non-candidate until a real CV heading.
            flush()
            hanging_qualifier = None
            section = "non_candidate"
            append_segment(clean, (clean,), section)
            continue
        if section == "non_candidate":
            # The entire untrusted requirements region stays out of evidence,
            # including dangling qualifiers and nested skill lists.
            append_segment(clean, (clean,), section)
            continue
        if _HANGING_QUALIFIER_RE.fullmatch(clean):
            flush()
            hanging_qualifier = clean.rstrip(":").strip()
            append_segment(clean, (clean,), "other")
            continue
        if hanging_qualifier is not None:
            if _compact_item(clean) and not _BULLET_RE.match(raw):
                # Treat every compact entry of a contiguous list as scoped.
                # 'No experience with\nPython\nDjango' must never become
                # independent positive claims of Python and Django.
                flush()
                value = f"{hanging_qualifier} {clean}"
                append_segment(value, (hanging_qualifier, clean), "other")
                continue
            if _compact_item(clean) and _BULLET_RE.match(raw):
                flush()
                value = f"{hanging_qualifier} {clean}"
                append_segment(value, (hanging_qualifier, clean), "other")
                continue
            hanging_qualifier = None
        if re.match(r"(?i)^(?:candidate\s+profile\s+for|applying\s+for|target\s+role\s*:)\b", clean):
            flush()
            append_segment(clean, (clean,), "metadata")
            continue
        is_bullet = bool(_BULLET_RE.match(normalize_unicode(raw).replace("\u200b", "")))
        is_inline_label = bool(_INLINE_LABEL_RE.match(clean))
        if section == "skills" and not is_inline_label and len(clean) <= 80:
            # A short lowercase continuation of a labelled comma-separated
            # row is usually a PDF wrap ("..., model\nevaluation").
            if (buffer and not is_bullet and clean[:1].islower()
                    and ("," in " ".join(buffer) or buffer[-1].endswith("-"))):
                buffer.append(clean)
            else:
                flush()
                append_segment(clean, (clean,), section)
            continue

        # A compact, unheaded standalone line is a *self-reported literal*
        # capability candidate, not a synonym or validated skill. The guards
        # only grant credit when it equals the requirement/explicit option.
        # A one-line role title cannot prove any substring skill.
        if section == "other" and _compact_item(clean):
            flush()
            prev = cleaned[i - 1] if i else ""
            # A dangling learning/negation heading is semantically controlling:
            # "No experience with:\nDocker" must not become a skill claim.
            qualified = bool(prev.endswith(":") and re.search(
                r"(?i)\b(?:no|not|never|without|learning|learn|studying|"
                r"study|preparing|interested|exposure|limited|basic|pending)\b", prev))
            if qualified:
                append_segment(f"{prev[:-1]} {clean}", (prev, clean), "other")
            else:
                append_segment(clean, (clean,), "inferred_skills")
            continue

        if is_bullet or is_inline_label:
            flush()
            buffer = [clean]
        else:
            # Short standalone lines are independent source assertions, never
            # concatenated into adjacent numeric experience statements.
            if _compact_item(clean) and not buffer:
                append_segment(clean, (clean,), section)
                continue
            if buffer and _compact_item(buffer[-1]):
                flush()
            if not buffer:
                buffer = [clean]
            else:
                buffer.append(clean)

        if clean.endswith((".", "!", "?")):
            flush()
        elif len(" ".join(buffer)) > 700:
            flush()

    flush()
    return segments


def render_segments(segments: list[ResumeSegment]) -> str:
    return "\n".join(f"{s.segment_id} [{s.section}] {s.text}" for s in segments)


def resolve_segment_ids(ids: list[str], segments: list[ResumeSegment], limit: int = 3) -> tuple[str | None, list[str]]:
    """Resolve all supplied citations or reject the entire malformed list.

    Never silently truncate citations: a fabricated fourth ID must be visible
    to the caller rather than hidden by the display limit.
    """
    by_id = {s.segment_id: s for s in segments}
    raw_ids = [str(raw).strip().upper() for raw in (ids or [])]
    clean_ids = list(dict.fromkeys(raw_ids))
    if (not clean_ids or len(raw_ids) > limit or len(clean_ids) != len(raw_ids)
            or any(not re.fullmatch(r"S\d{3,}", i) or i not in by_id for i in clean_ids)):
        return None, clean_ids
    return " | ".join(by_id[i].text for i in clean_ids), clean_ids

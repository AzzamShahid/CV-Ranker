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


KNOWN_HEADINGS = {
    "professional summary": "summary",
    "summary": "summary",
    "profile": "summary",
    "education": "education",
    "technical skills": "skills",
    "skills": "skills",
    "professional experience": "experience",
    "work experience": "experience",
    "experience": "experience",
    "ai projects": "projects",
    "projects": "projects",
    "achievements publication leadership": "achievements",
    "achievements": "achievements",
    "certifications": "certifications",
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
    # Conservative all-caps section heading fallback.
    letters = re.sub(r"[^A-Za-z]+", "", clean)
    if letters and clean.upper() == clean and 1 <= len(clean.split()) <= 7 and len(clean) <= 60:
        return key or "other"
    return None


def segment_resume(text: str) -> list[ResumeSegment]:
    """Merge physical wrapped lines into stable evidence units and number them."""
    raw_lines = [raw for raw in normalize_unicode(text or "").splitlines() if raw.strip()]
    segments: list[ResumeSegment] = []
    section = "other"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        merged = normalize_whitespace(" ".join(buffer))
        if merged:
            segments.append(ResumeSegment(f"S{len(segments)+1:03d}", section, merged))
        buffer = []

    for raw in raw_lines:
        clean = _clean(raw)
        if not clean:
            continue

        heading = _heading(raw)
        if heading is not None:
            flush()
            section = heading
            continue

        is_bullet = bool(_BULLET_RE.match(normalize_unicode(raw).replace("\u200b", "")))
        is_inline_label = bool(_INLINE_LABEL_RE.match(clean))

        if is_bullet or is_inline_label:
            flush()
            buffer = [clean]
        else:
            if not buffer:
                buffer = [clean]
            else:
                buffer.append(clean)

        # A complete sentence/bullet is a natural evidence boundary. Inline skill
        # rows without punctuation are flushed when the next labelled row starts.
        if clean.endswith((".", "!", "?")):
            flush()
        elif len(" ".join(buffer)) > 700:
            flush()

    flush()
    return segments


def render_segments(segments: list[ResumeSegment]) -> str:
    return "\n".join(f"{s.segment_id} [{s.section}] {s.text}" for s in segments)


def resolve_segment_ids(ids: list[str], segments: list[ResumeSegment], limit: int = 3) -> tuple[str | None, list[str]]:
    by_id = {s.segment_id: s for s in segments}
    clean_ids: list[str] = []
    for raw in ids or []:
        value = str(raw).strip().upper()
        if value and value not in clean_ids:
            clean_ids.append(value)
        if len(clean_ids) >= limit:
            break
    if not clean_ids or any(i not in by_id for i in clean_ids):
        return None, clean_ids
    return " | ".join(by_id[i].text for i in clean_ids), clean_ids

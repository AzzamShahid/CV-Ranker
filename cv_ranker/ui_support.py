import json
import html
import re
from pathlib import Path

from .documents import SUPPORTED_EXTENSIONS
from .schemas import CandidateResult, RankingReport
from .scoring import _ranking_key
from .text_utils import requirement_options


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_upload_name(name: str, fallback: str = "upload.txt") -> str:
    """Return a basename-safe upload filename with a supported extension."""
    raw_name = (name or "").replace("\\", "/")
    base = raw_name.rsplit("/", 1)[-1].strip()
    if not base:
        base = fallback
    base = _FILENAME_SAFE.sub("_", base)
    base = base.strip(" .") or fallback

    suffix = Path(base).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported uploaded file type: {suffix or '[none]'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    stem = Path(base).stem
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"

    # Avoid Windows path failures from pathological upload names while preserving
    # the extension and enough of the original name for display.
    stem = stem[:120].rstrip(" .") or "upload"
    return f"{stem}{suffix}"


def save_uploaded_bytes(
    *,
    root: str | Path,
    group: str,
    index: int,
    filename: str,
    data: bytes,
) -> Path:
    """Persist one uploaded file in an isolated slot while preserving its display basename."""
    root = Path(root)
    safe_name = safe_upload_name(filename)
    slot = root / group / f"{index:04d}"
    slot.mkdir(parents=True, exist_ok=True)
    path = slot / safe_name
    path.write_bytes(data)
    return path


def report_json_bytes(report: RankingReport) -> bytes:
    return json.dumps(
        report.model_dump(),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def ranking_rows(report: RankingReport) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in report.candidates:
        rows.append(
            {
                "Rank": item.rank if item.rank is not None else "-",
                "Candidate": item.candidate_name,
                "Primary score": (
                    round(item.primary_score, 2)
                    if item.primary_score is not None
                    else None
                ),
                "Primary matched": f"{item.matched_primary}/{item.total_primary}",
                "Required coverage": (
                    round(item.required_score, 2)
                    if item.required_score is not None
                    else None
                ),
                "Preferred coverage": (
                    round(item.preferred_score, 2)
                    if item.preferred_score is not None
                    else None
                ),
                "Score basis": item.score_basis,
                "HR gate status": item.eligibility.status,
                "Evaluation mode": item.evaluation_mode,
            }
        )
    return rows


def review_label_for_candidate(candidate: CandidateResult, final: dict | None) -> str:
    """Present completion and per-criterion human review as separate states.

    This is display-only: the persisted `Provisional` compatibility flag is
    never used to withhold or create a candidate's scored qualification.
    """
    if candidate.primary_score is None:
        return (f"Ranking withheld · {final.get('Unverified', 0)} unverified"
                if final is not None and candidate.assessments else
                "Assessment unavailable · rerun")
    if final is None:
        return "Earlier run · rerun"
    if final.get("Unverified"):
        return f"Unverified ({int(final['Unverified'])}) · rerun"
    criteria = final.get("Criteria")
    if isinstance(criteria, list) and all(
            isinstance(row, dict) and "Review recommended" in row for row in criteria):
        count = sum(bool(row["Review recommended"]) for row in criteria)
        return f"Review suggested ({count})" if count else "Complete"
    # Old / partial payloads only recorded a coarse flag.
    return "Review suggested" if final.get("Provisional") else "Complete"


def final_leaderboard_rows(
    report: RankingReport, final_results: dict[str, dict] | None = None,
) -> list[dict[str, object]]:
    """One leaderboard driven by the same reconciled decisions as the detail grid.

    A transferable result is displayed for review, never scored as Found.
    Older sessions retain their original counts, visibly marked as earlier
    assessments, instead of inventing a zero-transferable final decision.
    """
    final_results = final_results or {}
    sortable = []
    for index, candidate in enumerate(report.candidates):
        final = final_results.get(str(index))
        if final is not None:
            required_found = int(final["Required matched"])
            required_total = int(final["Required total"])
            preferred_found = int(final["Preferred matched"])
            preferred_total = int(final["Preferred total"])
            if candidate.primary_score is not None and (
                    required_found != candidate.matched_required or
                    required_total != candidate.total_required or
                    preferred_found != candidate.matched_preferred or
                    preferred_total != candidate.total_preferred):
                raise ValueError(
                    "Leaderboard/detail count mismatch; rerun assessment before exporting scores."
                )
            transferable = int(final["Transferable"])
            review = review_label_for_candidate(candidate, final)
        else:
            required_found = candidate.matched_required
            required_total = candidate.total_required
            preferred_found = candidate.matched_preferred
            preferred_total = candidate.total_preferred
            transferable = "Not checked"
            review = "Incomplete" if candidate.primary_score is None else "Earlier run · rerun"

        has_partial = bool(final is not None and candidate.assessments)
        if candidate.primary_score is None:
            # A provider/embedding failure is NOT a 0%-match candidate. In
            # particular, do not turn a 429 into dozens of Not Found scores.
            review = review_label_for_candidate(candidate, final)

        row = {
            "Candidate index": index,  # Stable source identity; leaderboard order can differ.
            "Rank": 0,
            "Candidate": candidate.candidate_name,
            "Score": round(candidate.primary_score, 1) if candidate.primary_score is not None else None,
            "Required": (f"{required_found}/{required_total}" + (" · partial" if has_partial and candidate.primary_score is None else "")
                         if candidate.primary_score is not None or has_partial else "Not assessed"),
            "Preferred": (f"{preferred_found}/{preferred_total}" + (" · partial" if has_partial and candidate.primary_score is None else "")
                          if candidate.primary_score is not None or has_partial else "Not assessed"),
            "Transferable": transferable if candidate.primary_score is not None or has_partial else "Not assessed",
            "Review": review,
            "Mode": candidate.evaluation_mode,
        }
        sortable.append((candidate, row))

    # Never recompute rank with a different set of tie-breakers here. The
    # backend uses exactly this key for report ordering and export ranks.
    sortable.sort(key=lambda pair: _ranking_key(pair[0]))
    for position, (candidate, row) in enumerate(sortable, 1):
        row["Rank"] = (candidate.rank if candidate.rank is not None else position) \
            if candidate.primary_score is not None else "-"
    return [row for _, row in sortable]


def highlighted_source_html(source_text: str, term: str | list[str] | None) -> str:
    """HTML-escape untrusted resume text and highlight source-backed phrases.

    No semantic lookup or skill catalog is used. If no actual source phrase is
    available, show the full line without pretending to know its matching span.
    """
    if not term:
        return html.escape(source_text)
    terms = [term] if isinstance(term, str) else term
    terms = sorted({str(value) for value in terms if value and str(value).strip()}, key=len, reverse=True)
    if not terms:
        return html.escape(source_text)
    # Longest phrase first prevents a short name from hiding its longer,
    # source-grounded variant. No HTML from a CV is ever inserted unescaped.
    pattern = re.compile(r"(?<![\w+#&])(?:" + "|".join(re.escape(t) for t in terms) +
                         r")(?![\w+#&])", re.IGNORECASE)
    parts = []
    last = 0
    for hit in pattern.finditer(source_text):
        parts.append(html.escape(source_text[last:hit.start()]))
        parts.append("<mark>" + html.escape(hit.group()) + "</mark>")
        last = hit.end()
    parts.append(html.escape(source_text[last:]))
    return "".join(parts)


def supervisor_csv_bytes(report: RankingReport) -> bytes:
    """Export only non-sensitive ranking summary fields; source CVs stay in the full JSON."""
    import csv
    import io

    fields = ["Rank", "Candidate", "Primary score", "Primary matched", "Required coverage", "Preferred coverage", "Evaluation mode"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in ranking_rows(report):
        writer.writerow({field: row.get(field) for field in fields})
    return buf.getvalue().encode("utf-8-sig")


def _evidence_preview(assessment, requirement, width: int = 160) -> str:
    """Show the named source term when possible, not just segment characters 1-125."""
    texts = [citation.text for citation in assessment.evidence_segments]
    if assessment.evidence and assessment.evidence not in texts:
        texts.append(assessment.evidence)
    if not texts:
        return ""
    terms = [assessment.matched_term] if assessment.matched_term else []
    terms.extend(requirement_options(requirement.name))
    text = texts[0]
    offset = 0
    for term in terms:
        if not term:
            continue
        found = next(((source, source.casefold().find(term.casefold())) for source in texts
                      if term.casefold() in source.casefold()), None)
        if found:
            text, offset = found
            break
    if len(text) <= width:
        return text
    start = max(0, min(len(text) - width, offset - 24))
    return ("…" if start else "") + text[start:start + width] + ("…" if start + width < len(text) else "")


def candidate_assessment_rows(report: RankingReport, candidate_index: int) -> list[dict[str, str]]:
    """Present frozen JD rows without inferring extra skills or overriding scoring."""
    candidate = report.candidates[candidate_index]
    by_id = {a.requirement_id: a for a in candidate.assessments}
    output = []
    for requirement in report.requirements:
        assessment = by_id.get(requirement.requirement_id)
        status = assessment.status if assessment is not None else "missing_assessment"
        output.append({
            "ID": requirement.requirement_id,
            "Requirement": requirement.name,
            "Priority": requirement.priority.title(),
            "Result": {"matched": "Matched", "not_matched": "Not matched", "uncertain": "Needs review", "missing_assessment": "Not evaluated"}[status],
            "Evidence": (_evidence_preview(assessment, requirement) if assessment else ""),
        })
    return output


def review_semantic_import(raw: object, report: RankingReport) -> tuple[bool, str]:
    """Fail closed for mismatched/stale experimental semantic JSON.

    Current shadow schema omits the JD checksum. Matching candidates/scores
    is a *sanity check*, not proof it uses the identical JD or model.
    """
    if not isinstance(raw, dict) or raw.get("mode") != "qwen_transferability_shadow_not_scoring":
        return False, "Not a recognized Phase 7G shadow transferability report."
    if raw.get("scoring_unchanged") is not True or raw.get("complete") is not True:
        return False, "The semantic report is incomplete or does not guarantee ranking isolation."
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(report.candidates):
        return False, "Candidate count does not match this ranking run."
    if len({c.candidate_name for c in report.candidates}) != len(report.candidates):
        return False, "Duplicate candidate names make the shadow report ambiguous."
    actual = {c.candidate_name: c for c in report.candidates}
    used = set()
    for item in candidates:
        if not isinstance(item, dict):
            return False, "Malformed semantic candidate entry."
        name = item.get("candidate_name")
        if not isinstance(name, str) or name not in actual or name in used:
            return False, "Semantic candidate names do not match this ranking run."
        used.add(name)
        previous = actual[name]
        if previous.primary_score is None or item.get("original_primary_score") != previous.primary_score or item.get("original_rank") != previous.rank:
            return False, "Semantic report belongs to a different ranking state."
        if item.get("status") != "completed_provisional" or not isinstance(item.get("assessments"), list):
            return False, "An experimental candidate assessment is incomplete."
    return True, "Candidate names, original ranks and scores match; JD identity is not independently provable from this file."

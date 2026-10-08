import json
import re
from pathlib import Path

from .documents import SUPPORTED_EXTENSIONS
from .schemas import RankingReport


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
                "Evaluation mode": item.evaluation_mode,
            }
        )
    return rows

"""Signed, user-controlled recovery snapshots for the supervisor UI.

The application deliberately does NOT autosave sensitive applicant excerpts
to a new server-side database. The reviewer must explicitly download this
archive and store it securely. Its HMAC prevents a modified ZIP from silently
resetting cloud-request budgets or rewriting assessment decisions on import.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
from math import isfinite
from typing import Mapping
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .build_info import ASSESSMENT_PROTOCOL_VERSION, BUILD_ID
from .schemas import CandidateResult, RankingReport
from .weighted_scoring import ScoreWeights


RECOVERY_FORMAT = 1
MAX_ARCHIVE_BYTES = 48 * 1024 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
_NAMES = {"checkpoint.json", "checkpoint.hmac"}
RECOVERY_KEYS = (
    "cv_ranking_report", "cv_run_label", "cv_run_requirement_limit",
    "cv_run_provider", "cv_source_ledgers", "cv_source_ledger_errors",
    "cv_unified_metrics", "cv_request_metrics", "cv_final_results",
    "cv_resume_cache", "cv_weight_split", "cv_weight_slider_experience",
    "cv_weight_slider_education", "cv_weight_slider_jd",
    "cv_weight_slider_required", "cv_requirement_allocations",
)


def local_signing_key(path: Path) -> bytes:
    """Keep a random local signing key outside distributed source artifacts.

    The key is not a password and not encryption. It is retained across
    server restarts; moving a snapshot to another server requires the
    operator to transfer this key separately and securely.
    """
    if path.is_symlink():
        raise ValueError("Recovery signing key cannot be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            pass  # Concurrent Streamlit rerun already initialized the key.
        else:
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32))
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError("Recovery signing key was missing, truncated or corrupted")
    return key


def _validate_snapshot(snapshot: object) -> dict:
    if not isinstance(snapshot, dict) or set(snapshot) - set(RECOVERY_KEYS):
        raise ValueError("Recovery snapshot contained unexpected state fields")
    report_data = snapshot.get("cv_ranking_report")
    if not isinstance(report_data, dict):
        raise ValueError("Recovery snapshot did not contain a ranking report")
    report = RankingReport.model_validate(report_data)
    if report.build_id != BUILD_ID:
        raise ValueError("Recovery snapshot came from a different assessment build")
    request_metrics = snapshot.get("cv_request_metrics") or {}
    if not isinstance(request_metrics, dict):
        raise ValueError("Recovery request metrics were invalid")
    for metric in ("assessment_http_attempts_cumulative", "actual_model_request_attempts"):
        number = request_metrics.get(metric)
        if number is not None and (type(number) is not int or not 0 <= number <= 1_000_000):
            raise ValueError("Recovery cloud-request metrics were invalid")
    cached = snapshot.get("cv_resume_cache")
    if cached is not None:
        if not isinstance(cached, dict):
            raise ValueError("Recovery checkpoint was malformed")
        context = cached.get("context_key")
        if not isinstance(context, str) or not re.fullmatch(r"[a-f0-9]{64}", context):
            raise ValueError("Recovery checkpoint has no valid input identity")
        frozen = RankingReport.model_validate(cached.get("report"))
        if (frozen.build_id != BUILD_ID or frozen.jd_sha256 != report.jd_sha256
                or [r.model_dump() for r in frozen.requirements] !=
                   [r.model_dump() for r in report.requirements]):
            raise ValueError("Recovery checkpoint conflicts with the approved frozen JD")
        candidates = cached.get("candidates")
        if not isinstance(candidates, dict):
            raise ValueError("Recovery checkpoint has no candidate index")
        for key, entry in candidates.items():
            if not isinstance(key, str):
                raise ValueError("Recovery candidate key was invalid")
            CandidateResult.model_validate(entry)
        attempts = cached.get("assessment_http_attempts_total", 0)
        if type(attempts) is not int or not 0 <= attempts <= 1_000_000:
            raise ValueError("Recovery cloud-attempt counter was invalid")
        recorded = request_metrics.get("assessment_http_attempts_cumulative")
        if recorded is not None and recorded != attempts:
            raise ValueError("Recovery cloud-request counters disagreed")
    allocation = snapshot.get("cv_requirement_allocations", {})
    if not isinstance(allocation, dict):
        raise ValueError("Recovery requirement allocations were invalid")
    for fingerprint, shares in allocation.items():
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise ValueError("Recovery allocation identity was invalid")
        if not isinstance(shares, dict):
            raise ValueError("Recovery requirement allocation was malformed")
        for requirement_id, share in shares.items():
            if (not isinstance(requirement_id, str) or not requirement_id.strip()
                    or isinstance(share, bool) or not isinstance(share, (int, float))
                    or not isfinite(share) or not 0 <= share <= 100):
                raise ValueError("Recovery requirement shares were invalid")
    weights = [snapshot.get("cv_weight_slider_" + key, default) for key, default
               in (("experience", 10), ("education", 10), ("jd", 80))]
    ScoreWeights(*weights)
    if "cv_weight_split" in snapshot and not isinstance(snapshot["cv_weight_split"], bool):
        raise ValueError("Recovery weight display setting was invalid")
    return snapshot


def export_recovery_checkpoint(state: Mapping[str, object], signing_key: bytes) -> bytes:
    """Export one authenticated snapshot; no new model calls or applicant IO."""
    if len(signing_key) != 32:
        raise ValueError("A 32-byte local signing key is required")
    snapshot = {key: state[key] for key in RECOVERY_KEYS if key in state}
    _validate_snapshot(snapshot)
    document = {
        "format": RECOVERY_FORMAT,
        "build_id": BUILD_ID,
        "assessment_protocol_version": ASSESSMENT_PROTOCOL_VERSION,
        "snapshot": snapshot,
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("Recovery snapshot exceeds the size limit")
    digest = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    result = io.BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED, compresslevel=7) as archive:
        archive.writestr("checkpoint.json", payload)
        archive.writestr("checkpoint.hmac", digest)
    if result.tell() > MAX_ARCHIVE_BYTES:
        raise ValueError("Recovery archive exceeds the size limit")
    return result.getvalue()


def import_recovery_checkpoint(blob: bytes, signing_key: bytes) -> dict:
    """Fail closed on altered, oversized or incompatible checkpoint files."""
    if len(signing_key) != 32 or len(blob) > MAX_ARCHIVE_BYTES:
        raise ValueError("Recovery key or archive size is invalid")
    try:
        with ZipFile(io.BytesIO(blob)) as archive:
            entries = archive.infolist()
            if (len(entries) != 2 or {item.filename for item in entries} != _NAMES
                    or any(item.file_size > MAX_PAYLOAD_BYTES for item in entries)):
                raise ValueError("Recovery archive contained unexpected or oversized files")
            payload = archive.read("checkpoint.json")
            signature = archive.read("checkpoint.hmac").decode("ascii")
    except (BadZipFile, KeyError, UnicodeError) as exc:
        raise ValueError("Recovery archive was unreadable") from exc
    if len(payload) > MAX_PAYLOAD_BYTES or not re.fullmatch(r"[a-f0-9]{64}", signature):
        raise ValueError("Recovery content or signature was invalid")
    expected = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Recovery archive signature did not match this installation")
    try:
        document = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Recovery payload was not valid JSON") from exc
    if (not isinstance(document, dict) or set(document) != {
            "format", "build_id", "assessment_protocol_version", "snapshot"}
            or document["format"] != RECOVERY_FORMAT
            or document["build_id"] != BUILD_ID
            or document["assessment_protocol_version"] != ASSESSMENT_PROTOCOL_VERSION):
        raise ValueError("Recovery snapshot format or assessment identity was incompatible")
    return _validate_snapshot(document["snapshot"])

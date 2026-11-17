"""Single immutable, bounded candidate source snapshot per assessment slot.

The extraction parser sees the SAME bytes used for the resume digest. Other
candidate slots can succeed even when one path vanishes or cannot be read.
This is local input safety, not a durable remote multi-worker upload store.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .documents import DocumentError, SUPPORTED_EXTENSIONS, extract_text

MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024  # same maximum as Streamlit upload


def read_candidate_snapshot(path: Path) -> tuple[str, str]:
    """Return extracted text plus v51-compatible name+byte SHA256 identity.

    The file descriptor is opened once and read chunkwise; a separate secured
    temporary file receives the exact captured bytes for the format parser.
    Replacement of the original pathname cannot alter that parsed snapshot.
    """
    original = Path(path)
    if original.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DocumentError("Unsupported resume file extension")
    identity = hashlib.sha256()
    identity.update(original.name.encode("utf-8") + b"\0")
    try:
        with tempfile.TemporaryDirectory(prefix="cvr_candidate_snapshot_") as folder:
            dest = Path(folder) / original.name
            read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(original, read_flags), "rb") as source:
                stat_before = os.fstat(source.fileno())
                if stat_before.st_size > MAX_SNAPSHOT_BYTES:
                    raise DocumentError("Resume exceeds the 10 MiB source limit")
                fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600)
                with os.fdopen(fd, "wb") as destination:
                    consumed = 0
                    while True:
                        block = source.read(64 * 1024)
                        if not block:
                            break
                        consumed += len(block)
                        if consumed > MAX_SNAPSHOT_BYTES:
                            raise DocumentError("Resume exceeds the 10 MiB source limit")
                        identity.update(block)
                        destination.write(block)
                stat_after = os.fstat(source.fileno())
                if (stat_before.st_size != stat_after.st_size or
                    stat_before.st_mtime_ns != stat_after.st_mtime_ns):
                    raise DocumentError("Resume was modified while being captured; re-upload a stable copy")
            return extract_text(dest), identity.hexdigest()
    except DocumentError:
        raise
    except (OSError, PermissionError) as exc:
        # Do not print filesystem errors with attacker-controlled path text.
        raise DocumentError(f"Could not safely read candidate source ({type(exc).__name__})") from exc

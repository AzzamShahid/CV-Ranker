"""SQLite cache for normalized float32 vectors; no original CV text persisted."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
from .embedding import EmbeddingError, normalize


class SQLiteVectorCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise EmbeddingError("Embedding cache must not be a symbolic link")
        # Keep derived applicant vectors private from other OS accounts.
        # A preexisting cache is retained, never destroyed or truncated.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        if os.name == "posix":
            self.path.chmod(self.path.stat().st_mode & 0o700)
        self._conn = sqlite3.connect(str(self.path), timeout=15.0)
        self._conn.execute("PRAGMA busy_timeout = 15000")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA secure_delete = ON")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key TEXT PRIMARY KEY,
                dimensions INTEGER NOT NULL,
                vector BLOB NOT NULL
            )
        """)
        self._conn.commit()

    @staticmethod
    def key(model_fingerprint: str, role: str, text: str) -> str:
        if role not in {"query", "document"}:
            raise ValueError("Invalid embedding role")
        raw = json.dumps(["phase7g-v1", model_fingerprint, role, text], ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str, dimensions: int | None = None) -> np.ndarray | None:
        row = self._conn.execute("SELECT dimensions, vector FROM embeddings WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            return None
        size, blob = row
        try:
            # SQLite accepts text or REAL in an INTEGER/BLOB column unless
            # STRICT. Check actual storage types, not only SQL declarations.
            if type(size) is not int or size <= 0 or size > 1_000_000:
                raise ValueError("Invalid stored embedding dimension")
            if type(blob) is not bytes or len(blob) != size * 4:
                raise ValueError("Invalid stored embedding payload")
            if dimensions is not None and dimensions != size:
                # A valid cached row from a different model dimension is a
                # cache miss, not grounds to delete a healthy neighbor.
                return None
            vector = np.frombuffer(blob, dtype="<f4")
            return normalize(vector.reshape(1, size), 1, size)[0]
        except (TypeError, ValueError, OverflowError, EmbeddingError) as exc:
            raise EmbeddingError("Corrupted cached embedding (single key)") from exc

    def put(self, key: str, vector: np.ndarray) -> None:
        value = normalize(np.asarray(vector, dtype=np.float32).reshape(1, -1), 1)[0]
        self._conn.execute(
            "INSERT OR REPLACE INTO embeddings (cache_key, dimensions, vector) VALUES (?, ?, ?)",
            (key, int(value.size), value.astype("<f4").tobytes()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

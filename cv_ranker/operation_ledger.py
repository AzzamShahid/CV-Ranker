"""SQLite per-operation semantic dispatch ledger for the local supervisor.

The DB contains only signatures, state, and SHA-256 result references. Applicant
text, prompts, credentials and provider replies are never stored in the DB.
A claim is *potentially dispatched*: a crashed worker's unknown remote delivery
must not be retried automatically. Complete results require a saved checkpoint.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Mapping


_STATES = frozenset({'claimed_unknown_delivery', 'validated_result',
                     'invalid_response', 'provider_unknown_delivery', 'retryable_error'})


def _validate_keys(signatures: list[str]) -> None:
    if not signatures or len(set(signatures)) != len(signatures):
        raise ValueError('Operation signatures must be unique and nonempty')
    if any(len(x) != 64 or any(c not in '0123456789abcdef' for c in x)
           for x in signatures):
        raise ValueError('Operation signature must be a lowercase SHA256 digest')


class LocalOperationLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise ValueError('Operation ledger may not be a symlink')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                         getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        self.db = sqlite3.connect(str(self.path), timeout=15)
        self.db.execute('PRAGMA busy_timeout=15000')
        for attempt in range(10):
            try:
                self.db.execute('PRAGMA journal_mode=WAL')
                break
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == 9:
                    self.db.close()
                    raise
                time.sleep(.03 * (attempt + 1))
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS operations (
            signature TEXT PRIMARY KEY, state TEXT NOT NULL,
            attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT)''')
        # Safe and idempotent migration of legacy v52 rows.
        columns = {x[1] for x in self.db.execute('PRAGMA table_info(operations)')}
        for column, column_type in (
                ('batch_signature', 'TEXT'), ('result_sha256', 'TEXT'),
                ('attempt_count', 'INTEGER NOT NULL DEFAULT 0'),
                ('retry_after_epoch', 'REAL'), ('error_code', 'TEXT')):
            if column not in columns:
                for attempt in range(10):
                    try:
                        self.db.execute(f'ALTER TABLE operations ADD COLUMN {column} {column_type}')
                        break
                    except sqlite3.OperationalError as exc:
                        message = str(exc).lower()
                        # Two concurrent v52 upgrades can both observe a
                        # missing column, then race to add it. A successful
                        # competing upgrade is NOT an application failure.
                        if 'duplicate column' in message:
                            break
                        if 'locked' not in message or attempt == 9:
                            self.db.close()
                            raise
                        time.sleep(.03 * (attempt + 1))
        self.db.commit()

    def claim_each(self, signatures: list[str]) -> dict[str, str]:
        """Atomically claim new operations; return one disposition per key.

        An existing A must not prevent new B. A's stored state is returned
        without interpreting completed/unknown delivery as a reusable result.
        """
        _validate_keys(signatures)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            states = {}
            for key in signatures:
                existing = self.db.execute('SELECT state FROM operations WHERE signature=?',
                                           (key,)).fetchone()
                if existing:
                    states[key] = existing[0]
                else:
                    self.db.execute('INSERT INTO operations(signature,state,attempt_count) VALUES (?,?,1)',
                                    (key, 'claimed_unknown_delivery'))
                    states[key] = 'claimed_new'
            self.db.commit()
            return states
        except Exception:
            self.db.rollback()
            raise

    def claim_many(self, signatures: list[str]) -> bool:
        """Historical all-or-none API, kept for old code/tests; new callers
        must use claim_each so a blocked sibling cannot obstruct new work.
        """
        _validate_keys(signatures)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            found = self.db.execute('SELECT signature FROM operations WHERE signature IN ('+
                ','.join('?' for _ in signatures)+')', signatures).fetchall()
            if found:
                self.db.rollback()
                return False
            self.db.executemany("INSERT INTO operations(signature,state,attempt_count) VALUES (?, 'claimed_unknown_delivery',1)",
                                [(key,) for key in signatures])
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def bind_batch(self, signatures: list[str], batch_signature: str) -> None:
        """Attach a stable hash of the *actual sent payload* to claimed work."""
        _validate_keys(signatures)
        _validate_keys([batch_signature])
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for key in signatures:
                row = self.db.execute('SELECT state,batch_signature FROM operations WHERE signature=?',
                                      (key,)).fetchone()
                if row is None or row[0] != 'claimed_unknown_delivery' or row[1] is not None:
                    raise ValueError('Operation was not newly claimed for dispatch')
                self.db.execute('UPDATE operations SET batch_signature=? WHERE signature=?',
                                (batch_signature, key))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise


    def claim_review(self, signature: str, *, now: float | None = None,
                     max_attempts: int = 3) -> str:
        '''Claim a new review or a *known rejected* retryable provider attempt.

        A 429 provides a definitive rejection, unlike a timeout or unknown
        delivery. Retry creates a new attempt for the same logical operation;
        concurrent workers cannot both win the transaction.
        '''
        _validate_keys([signature])
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        moment = time.time() if now is None else float(now)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute(
                'SELECT state,attempt_count,retry_after_epoch FROM operations WHERE signature=?',
                (signature,)).fetchone()
            if row is None:
                self.db.execute('''INSERT INTO operations(signature,state,attempt_count)
                                   VALUES (?,?,1)''', (signature,'claimed_unknown_delivery'))
                disposition='claimed_new'
            elif (row[0] == 'retryable_error' and
                  int(row[1] or 0) < max_attempts and
                  (row[2] is None or moment >= float(row[2]))):
                self.db.execute('''UPDATE operations SET
                    state='claimed_unknown_delivery',attempt_count=attempt_count+1,
                    attempted_at=CURRENT_TIMESTAMP,finished_at=NULL,
                    result_sha256=NULL,batch_signature=NULL,error_code=NULL,
                    retry_after_epoch=NULL WHERE signature=?''', (signature,))
                disposition='claimed_retry'
            else:
                disposition=row[0]
            self.db.commit()
            return disposition
        except Exception:
            self.db.rollback()
            raise

    def finish_retryable(self, signatures: list[str], *, error_code: str,
                         retry_after_seconds: float = 0, now: float | None = None) -> None:
        '''Record a provider-declared retryable rejection and its cooldown.'''
        _validate_keys(signatures)
        if error_code not in {'provider_rate_limit', 'provider_unavailable'}:
            raise ValueError('Only explicit provider rejection codes can be retried')
        moment = time.time() if now is None else float(now)
        after = moment + max(0.0, float(retry_after_seconds))
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for key in signatures:
                row = self.db.execute('SELECT state FROM operations WHERE signature=?',
                                      (key,)).fetchone()
                if not row or row[0] != 'claimed_unknown_delivery':
                    raise ValueError('Retryable review must be an active attempt')
                self.db.execute('''UPDATE operations SET state='retryable_error',
                    error_code=?,retry_after_epoch=?,finished_at=CURRENT_TIMESTAMP
                    WHERE signature=?''',(error_code,after,key))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def release_undispatched(self, signatures: list[str]) -> None:
        '''Release preflight claims ONLY when no provider request was bound.'''
        if not signatures:
            return
        _validate_keys(signatures)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for key in signatures:
                row=self.db.execute('SELECT state,batch_signature FROM operations WHERE signature=?',
                                    (key,)).fetchone()
                if row and row[0] == 'claimed_unknown_delivery' and row[1] is None:
                    self.db.execute('DELETE FROM operations WHERE signature=?',(key,))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _result_dir(self) -> Path:
        '''Private local source-bound results, separate from the metadata DB.'''
        directory=self.path.with_name(self.path.stem + '_validated_results')
        if directory.is_symlink():
            raise ValueError('Result directory must not be a symlink')
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        return directory

    def commit_validated_result(self, signature: str, source_record: str | bytes) -> str:
        '''Durably publish bytes before the SQLite validated-result reference.

        A crash between filesystem and database commit only creates an orphan
        file (never a completed-but-unrecoverable operation).  A concurrent
        conflicting commit is rejected. Results contain only the validated
        assessment row, not full prompts, credentials or source documents.
        '''
        _validate_keys([signature])
        data = (source_record.encode('utf-8') if isinstance(source_record, str)
                else bytes(source_record))
        digest = hashlib.sha256(data).hexdigest()
        directory = self._result_dir()
        target=directory/(digest+'.json')
        if target.is_symlink():
            raise ValueError('Result file must not be a symlink')
        if not target.exists():
            fd, tmp = tempfile.mkstemp(prefix='.write-', dir=directory)
            try:
                # chmod on the temporary pathname works on both POSIX and
                # Windows, whereas fchmod is not supported on every Windows
                # Python/filesystem combination.
                os.chmod(tmp, 0o600)
                with os.fdopen(fd,'wb') as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp,target)
                # POSIX can fsync a directory entry after atomic replace.
                # Windows does not offer portable directory fsync; the
                # SQLite reference is committed only after replace returns.
                if os.name != "nt":
                    dirfd = os.open(directory, os.O_RDONLY)
                    try:
                        os.fsync(dirfd)
                    finally:
                        os.close(dirfd)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        else:
            if target.read_bytes()!=data:
                raise ValueError('Content-addressed result is corrupt')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT state,result_sha256 FROM operations WHERE signature=?',
                                (signature,)).fetchone()
            if row == ('validated_result',digest):
                self.db.commit()
                return digest
            if row is None or row[0] != 'claimed_unknown_delivery':
                raise ValueError('Cannot commit result to an unclaimed or conflicting operation')
            self.db.execute('''UPDATE operations SET state='validated_result',
                result_sha256=?,finished_at=CURRENT_TIMESTAMP,error_code=NULL,
                retry_after_epoch=NULL WHERE signature=?''',(digest,signature))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return digest

    def recover_validated_result(self, signature: str) -> bytes | None:
        '''Return only a digest-verified, fully published result, if present.'''
        _validate_keys([signature])
        row=self.result_reference(signature)
        if row is None or row[0] != 'validated_result' or not row[1]:
            return None
        digest=row[1]
        _validate_keys([digest])
        directory=self._result_dir()
        target=directory/(digest+'.json')
        if target.is_symlink() or not target.is_file():
            return None
        data=target.read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:
            return None
        return data

    def finish_each(self, results: Mapping[str, tuple[str, str | None]]) -> None:
        """Commit per-operation terminal state and optional result hash atomically.

        The result SHA identifies a checkpoint's validated decision; it is NOT
        recoverable applicant evidence, a model response, or license to reuse
        results without a compatible saved checkpoint.
        """
        if not results:
            return
        _validate_keys(list(results))
        for state, digest in results.values():
            if state not in _STATES - {'claimed_unknown_delivery'}:
                raise ValueError('Invalid operation terminal state')
            if digest is not None:
                _validate_keys([digest])
            if state != 'validated_result' and digest is not None:
                raise ValueError('Only verified results can store a result digest')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for key, (state, digest) in results.items():
                current = self.db.execute('SELECT state FROM operations WHERE signature=?',
                                          (key,)).fetchone()
                if current is None or current[0] != 'claimed_unknown_delivery':
                    raise ValueError('Cannot overwrite an absent or finished operation')
                self.db.execute('''UPDATE operations SET state=?,result_sha256=?,
                    finished_at=CURRENT_TIMESTAMP WHERE signature=?''',(state,digest,key))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def finish_many(self, signatures: list[str], state: str) -> None:
        if state not in _STATES - {'claimed_unknown_delivery'}:
            raise ValueError('Invalid operation terminal state')
        if not signatures:
            return
        _validate_keys(signatures)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.executemany('UPDATE operations SET state=?,finished_at=CURRENT_TIMESTAMP WHERE signature=?',
                                [(state, key) for key in signatures])
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def state(self, signature: str) -> str | None:
        row = self.db.execute('SELECT state FROM operations WHERE signature=?',(signature,)).fetchone()
        return row[0] if row else None

    def result_reference(self, signature: str) -> tuple[str, str | None] | None:
        row = self.db.execute('SELECT state,result_sha256 FROM operations WHERE signature=?',
                              (signature,)).fetchone()
        return (row[0], row[1]) if row else None

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

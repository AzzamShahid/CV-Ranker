"""Local-only transactional persistence for the TextileHR web shell.

The original CV ranking engine owns semantic decisions; this module owns durable
workflow records and process fencing. No Streamlit, embedding, provider or model
imports are performed here. All user data lives outside the source tree.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from typing import Any


SCHEMA_VERSION = 4
DATA_ROOT = Path(os.getenv('TEXTILEHR_DATA_DIR', str(Path.home() / '.textilehr-ai-web'))).expanduser().resolve()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def uid() -> str:
    return uuid.uuid4().hex


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(obj: Any) -> str:
    return hashlib.sha256(json_dumps(obj).encode('utf-8')).hexdigest()


class Conflict(RuntimeError):
    pass


class NotFound(RuntimeError):
    pass


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or DATA_ROOT).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / 'textilehr.sqlite3'
        install = self.root / 'installation-id'
        if not install.exists():
            try:
                fd=os.open(install,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(uid())
            except FileExistsError:pass
        self.installation_id=install.read_text(encoding='utf-8').strip()
        self.upload_root = self.root / 'uploads'
        self.export_root = self.root / 'exports'
        for folder in (self.upload_root, self.export_root):
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.migrate()
        try:
            self.process_pending_cleanups()
        except Exception:
            pass

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=15000')
        return conn

    @contextmanager
    def tx(self):
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self):
        with self.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS schema_info (version INTEGER PRIMARY KEY, applied TEXT NOT NULL)')
            version = db.execute('SELECT max(version) FROM schema_info').fetchone()[0] or 0
            if version > SCHEMA_VERSION:
                raise RuntimeError('Database schema is newer than this application. Restore the matching release.')
            if version == 0:
                # Each statement executes inside the explicit transaction above.
                statements = [
                  '''CREATE TABLE workspaces (
                       id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                       created TEXT NOT NULL, updated TEXT NOT NULL)''',
                  '''CREATE TABLE documents (
                       id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                       kind TEXT NOT NULL CHECK(kind IN ('jd','cv')), filename TEXT NOT NULL,
                       stored_name TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL,
                       byte_size INTEGER NOT NULL, extraction_state TEXT NOT NULL,
                       extraction_error TEXT, created TEXT NOT NULL)''',
                  '''CREATE TABLE jd_drafts (
                       id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                       document_id TEXT NOT NULL REFERENCES documents(id), revision INTEGER NOT NULL,
                       body_json TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL,
                       UNIQUE(workspace_id,revision))''',
                  '''CREATE TABLE jd_approvals (
                       id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                       draft_id TEXT NOT NULL REFERENCES jd_drafts(id), revision INTEGER NOT NULL,
                       body_json TEXT NOT NULL, approved TEXT NOT NULL,
                       UNIQUE(workspace_id,revision))''',
                  '''CREATE TABLE weights (
                       workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id), revision INTEGER NOT NULL,
                       body_json TEXT NOT NULL, updated TEXT NOT NULL)''',
                  '''CREATE TABLE jobs (
                       id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                       kind TEXT NOT NULL CHECK(kind IN ('jd_extract','assess')), state TEXT NOT NULL,
                       request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
                       owner TEXT, fencing INTEGER NOT NULL DEFAULT 0, lease_until REAL,
                       cancel_requested INTEGER NOT NULL DEFAULT 0,
                       sequence INTEGER NOT NULL DEFAULT 0,
                       result_json TEXT, result_revision INTEGER NOT NULL DEFAULT 0,
                       progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
                       error_code TEXT, error_message TEXT, created TEXT NOT NULL, updated TEXT NOT NULL)''',
                  '''CREATE TABLE idempotency (
                       workspace_id TEXT NOT NULL REFERENCES workspaces(id), key TEXT NOT NULL,
                       request_hash TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES jobs(id),
                       PRIMARY KEY(workspace_id,key))''',
                  '''CREATE TABLE events (
                       job_id TEXT NOT NULL REFERENCES jobs(id), seq INTEGER NOT NULL,
                       kind TEXT NOT NULL, payload_json TEXT NOT NULL, created TEXT NOT NULL,
                       PRIMARY KEY(job_id,seq))''',
                  '''CREATE TABLE candidate_results (
                       job_id TEXT NOT NULL REFERENCES jobs(id), document_id TEXT NOT NULL REFERENCES documents(id),
                       position INTEGER NOT NULL, result_json TEXT NOT NULL,
                       source_ledger_json TEXT NOT NULL, committed TEXT NOT NULL,
                       PRIMARY KEY(job_id,document_id), UNIQUE(job_id,position))''',
                  '''CREATE TABLE exports (
                       id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                       workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                       weight_revision INTEGER NOT NULL, result_revision INTEGER NOT NULL,
                       stored_name TEXT NOT NULL, size INTEGER NOT NULL, created TEXT NOT NULL)''',
                  '''CREATE TABLE audit (
                       id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT,
                       event TEXT NOT NULL, reference_id TEXT, created TEXT NOT NULL)''',
                  'CREATE INDEX jobs_state ON jobs(state,created)',
                  'CREATE INDEX documents_workspace ON documents(workspace_id,kind)',
                  'CREATE INDEX events_job ON events(job_id,seq)',
                ]
                for sql in statements: db.execute(sql)
                db.execute('INSERT INTO schema_info VALUES (?,?)', (1,now()))
            if version < 2:
                db.execute('''CREATE TABLE IF NOT EXISTS historical_reports (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    source_name TEXT NOT NULL, source_build TEXT NOT NULL,
                    body_json TEXT NOT NULL, created TEXT NOT NULL)''')
                db.execute('INSERT OR IGNORE INTO schema_info VALUES (?,?)',(2,now()))
            if version < 3:
                # Additions are migration-only; no source or scoring semantics change.
                db.execute('ALTER TABLE jobs ADD COLUMN eligible_at REAL')
                db.execute('ALTER TABLE jobs ADD COLUMN recovery_resolution TEXT')
                db.execute('INSERT OR IGNORE INTO schema_info VALUES (?,?)',(3,now()))
            if version < 4:
                # Keep the intent fingerprint after an explicitly deleted job.
                # An old browser tab must not accidentally recreate deleted
                # applicant processing using its still-persisted operation key.
                db.execute('''CREATE TABLE IF NOT EXISTS submission_tombstones (
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    key TEXT NOT NULL, request_hash TEXT NOT NULL,
                    deleted_at TEXT NOT NULL, PRIMARY KEY(workspace_id,key))''')
                db.execute('INSERT OR IGNORE INTO schema_info VALUES (?,?)',(4,now()))
            # Supporting tables for feature parity (focused review, semantic shadow, usage metrics, durable operations, cleanup)
            db.execute('''CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                job_id TEXT REFERENCES jobs(id),
                operation_type TEXT NOT NULL,
                candidate_id TEXT,
                requirement_id TEXT,
                idempotency_key TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                base_result_revision INTEGER,
                state TEXT NOT NULL CHECK(state IN ('in_progress','response_saved','completed','failed')),
                attempt_count INTEGER NOT NULL DEFAULT 1,
                resolved_provider TEXT,
                resolved_model TEXT,
                saved_response_json TEXT,
                committed_revision INTEGER,
                error_code TEXT,
                error_message TEXT,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                UNIQUE(workspace_id, operation_type, idempotency_key))''')
            db.execute('CREATE INDEX IF NOT EXISTS operations_lookup ON operations(workspace_id, operation_type, idempotency_key)')

            db.execute('''CREATE TABLE IF NOT EXISTS usage_events (
                event_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                operation_id TEXT,
                stage TEXT NOT NULL,
                candidate_id TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                logical_calls INTEGER NOT NULL DEFAULT 0,
                request_attempts INTEGER NOT NULL DEFAULT 0,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                is_unknown_tokens INTEGER NOT NULL DEFAULT 0,
                cost_amount REAL NOT NULL DEFAULT 0.0,
                cost_currency TEXT NOT NULL DEFAULT 'USD',
                cost_provenance TEXT NOT NULL DEFAULT 'model_card_estimate',
                created TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS usage_events_job ON usage_events(job_id)')

            db.execute('''CREATE TABLE IF NOT EXISTS pending_cleanups (
                id TEXT PRIMARY KEY,
                root_type TEXT NOT NULL CHECK(root_type IN ('documents', 'exports')),
                stored_name TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                UNIQUE(root_type, stored_name))''')
            db.execute('CREATE INDEX IF NOT EXISTS pending_cleanups_lookup ON pending_cleanups(root_type, stored_name)')
            db.execute('''CREATE TABLE IF NOT EXISTS focused_reviews (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                job_id TEXT NOT NULL REFERENCES jobs(id), candidate_id TEXT NOT NULL REFERENCES documents(id),
                requirement_id TEXT NOT NULL, prior_verdict TEXT NOT NULL,
                new_verdict TEXT NOT NULL, explanation TEXT NOT NULL,
                sources_json TEXT NOT NULL, created TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS semantic_shadows (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                job_id TEXT NOT NULL REFERENCES jobs(id),
                retrieval_json TEXT NOT NULL, proposals_json TEXT NOT NULL,
                created TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS job_metrics (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                metrics_json TEXT NOT NULL, updated TEXT NOT NULL)''')

    def audit(self, db, workspace_id: str, event: str, reference_id: str = ''):
        db.execute('INSERT INTO audit(workspace_id,event,reference_id,created) VALUES(?,?,?,?)',
                   (workspace_id,event,reference_id,now()))

    def workspace(self, workspace_id: str):
        with self.connect() as db:
            row = db.execute('SELECT * FROM workspaces WHERE id=?',(workspace_id,)).fetchone()
        if row is None: raise NotFound('Workspace not found')
        return dict(row)

    def create_workspace(self, title: str):
        identifier = uid()
        with self.tx() as db:
            db.execute('INSERT INTO workspaces VALUES(?,?,1,?,?)',(identifier,title,now(),now()))
            self.audit(db,identifier,'workspace_created',identifier)
        return self.workspace(identifier)

    def list_workspaces(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM workspaces ORDER BY created DESC LIMIT 100')]

    def add_document(self, workspace_id: str, kind: str, filename: str, suffix: str, content: bytes):
        self.workspace(workspace_id)
        identifier = uid()
        stored_name = identifier + suffix
        path = self.upload_root / stored_name
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(content);f.flush();os.fsync(f.fileno())
            with self.tx() as db:
                db.execute('''INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (identifier,workspace_id,kind,filename,stored_name,hashlib.sha256(content).hexdigest(),
                     len(content),'pending',None,now()))
                self.audit(db,workspace_id,'document_uploaded',identifier)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.document(workspace_id,identifier)

    def document(self, workspace_id: str, doc_id: str):
        with self.connect() as db:
            row = db.execute('SELECT * FROM documents WHERE id=? AND workspace_id=?',(doc_id,workspace_id)).fetchone()
        if row is None:raise NotFound('Document not found in workspace')
        return dict(row)

    def document_path(self, workspace_id: str, doc_id: str):
        doc = self.document(workspace_id, doc_id)
        # Names are generated by this server. DB corruption cannot escape the root.
        path = (self.upload_root / doc['stored_name']).resolve()
        if path.parent != self.upload_root or not path.is_file():
            raise NotFound('Stored document unavailable')
        return path

    def documents(self, workspace_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM documents WHERE workspace_id=? ORDER BY created DESC',(workspace_id,))]

    def latest_draft(self, workspace_id: str):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jd_drafts WHERE workspace_id=? ORDER BY revision DESC LIMIT 1',(workspace_id,)).fetchone()
        if row is None:return None
        return {**dict(row),'body':json.loads(row['body_json'])}

    def draft(self, workspace_id: str, draft_id: str):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jd_drafts WHERE id=? AND workspace_id=?',(draft_id,workspace_id)).fetchone()
        if row is None:raise NotFound('JD draft not found')
        return {**dict(row),'body':json.loads(row['body_json'])}

    def save_draft(self, workspace_id: str, document_id: str, body: dict):
        with self.tx() as db:
            rev = db.execute('SELECT coalesce(max(revision),0)+1 FROM jd_drafts WHERE workspace_id=?',(workspace_id,)).fetchone()[0]
            identifier=uid()
            db.execute('INSERT INTO jd_drafts VALUES(?,?,?,?,?,?,?)',
                (identifier,workspace_id,document_id,rev,json_dumps(body),'review',now()))
            self.audit(db,workspace_id,'jd_draft_extracted',identifier)
        return self.draft(workspace_id,identifier)

    def commit_extracted_jd(self, job_id: str, worker_id: str, fence: int,
                            document_id: str, body: dict):
        """Atomically publish a JD draft and its job result."""
        with self.tx() as db:
            self.assert_owner(db,job_id,worker_id,fence)
            job=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if job['kind']!='jd_extract':raise ValueError('Only JD extraction jobs publish drafts')
            document=db.execute('SELECT * FROM documents WHERE id=? AND workspace_id=?',
                                (document_id,job['workspace_id'])).fetchone()
            if document is None or document['kind']!='jd':raise NotFound('JD document unavailable')
            rev=db.execute('SELECT coalesce(max(revision),0)+1 FROM jd_drafts WHERE workspace_id=?',
                           (job['workspace_id'],)).fetchone()[0]
            identifier=uid()
            db.execute('INSERT INTO jd_drafts VALUES(?,?,?,?,?,?,?)',
                       (identifier,job['workspace_id'],document_id,rev,json_dumps(body),'review',now()))
            db.execute("UPDATE documents SET extraction_state='completed' WHERE id=?",(document_id,))
            db.execute("""UPDATE jobs SET result_json=?,result_revision=result_revision+1,
                state='completed',owner=NULL,lease_until=NULL,progress=total,updated=? WHERE id=?""",
                       (json_dumps({'draft_id':identifier,'revision':rev}),now(),job_id))
            self._event(db,job_id,'completed',{'state':'completed','draft_id':identifier})
            self.audit(db,job['workspace_id'],'jd_draft_extracted',identifier)
        return self.draft(job['workspace_id'],identifier)

    def revise_draft(self, workspace_id: str, draft_id: str, expected_rev: int, body: dict):
        # Historical revision remains immutable; editing creates the next revision.
        with self.tx() as db:
            row = db.execute('SELECT * FROM jd_drafts WHERE id=? AND workspace_id=?',(draft_id,workspace_id)).fetchone()
            if row is None:raise NotFound('JD draft not found')
            if row['revision'] != expected_rev: raise Conflict('JD revision changed. Reload and review.')
            newest=db.execute('SELECT max(revision) FROM jd_drafts WHERE workspace_id=?',(workspace_id,)).fetchone()[0]
            if newest!=expected_rev:raise Conflict('A newer JD revision exists. Reload and review.')
            identifier=uid();rev=expected_rev+1
            db.execute('INSERT INTO jd_drafts VALUES(?,?,?,?,?,?,?)',
                (identifier,workspace_id,row['document_id'],rev,json_dumps(body),'review',now()))
            self.audit(db,workspace_id,'jd_draft_revised',identifier)
        return self.draft(workspace_id,identifier)

    def latest_approval(self, workspace_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jd_approvals WHERE workspace_id=? ORDER BY revision DESC LIMIT 1',(workspace_id,)).fetchone()
        return None if row is None else {**dict(row),'body':json.loads(row['body_json'])}

    def approval(self, workspace_id: str, revision_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jd_approvals WHERE id=? AND workspace_id=?',(revision_id,workspace_id)).fetchone()
        if row is None:raise NotFound('Approved revision not found')
        return {**dict(row),'body':json.loads(row['body_json'])}

    def approve(self, workspace_id: str, draft_id: str, draft_rev: int, approved_json: dict):
        with self.tx() as db:
            draft=db.execute('SELECT * FROM jd_drafts WHERE id=? AND workspace_id=?',(draft_id,workspace_id)).fetchone()
            if draft is None:raise NotFound('Draft unavailable')
            if draft['revision']!=draft_rev:raise Conflict('JD draft revision has changed')
            latest=db.execute('SELECT max(revision) FROM jd_drafts WHERE workspace_id=?',(workspace_id,)).fetchone()[0]
            if latest!=draft_rev:raise Conflict('A newer JD draft exists')
            existing=db.execute('SELECT * FROM jd_approvals WHERE draft_id=?',(draft_id,)).fetchone()
            if existing:
                if fingerprint(json.loads(existing['body_json'])) != fingerprint(approved_json):
                    raise Conflict('This draft is already approved with different content. Save a successor draft revision before approving edited requirements.')
                return {**dict(existing),'body':json.loads(existing['body_json'])}
            rev=db.execute('SELECT coalesce(max(revision),0)+1 FROM jd_approvals WHERE workspace_id=?',(workspace_id,)).fetchone()[0]
            identifier=uid()
            db.execute('INSERT INTO jd_approvals VALUES(?,?,?,?,?,?)',
                       (identifier,workspace_id,draft_id,rev,json_dumps(approved_json),now()))
            self.audit(db,workspace_id,'jd_approved',identifier)
        return self.approval(workspace_id,identifier)

    def weights(self, workspace_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            row = db.execute('SELECT * FROM weights WHERE workspace_id=?',(workspace_id,)).fetchone()
        if row is None:
            from cv_ranker.weighted_scoring import ScoreWeights
            return {'revision':0,'body':ScoreWeights().as_dict()}
        return {'revision':row['revision'],'body':json.loads(row['body_json'])}

    def set_weights(self, workspace_id: str, expected_rev: int, body: dict):
        with self.tx() as db:
            current=db.execute('SELECT revision FROM weights WHERE workspace_id=?',(workspace_id,)).fetchone()
            if (current['revision'] if current else 0)!=expected_rev:raise Conflict('Weight revision changed. Reload and review.')
            revision=expected_rev+1
            db.execute('''INSERT INTO weights VALUES(?,?,?,?) ON CONFLICT(workspace_id)
                    DO UPDATE SET revision=excluded.revision,body_json=excluded.body_json,updated=excluded.updated''',
                    (workspace_id,revision,json_dumps(body),now()))
            self.audit(db,workspace_id,'weights_updated',str(revision))
        return self.weights(workspace_id)

    def make_job(self, workspace_id: str, kind: str, request: dict, key: str):
        if not key or len(key)>150:raise ValueError('An idempotency key is required')
        self.workspace(workspace_id)
        request_hash=fingerprint({'kind':kind,'request':request})
        with self.tx() as db:
            tombstone=db.execute('SELECT key FROM submission_tombstones WHERE workspace_id=? AND key=?',
                                 (workspace_id,key)).fetchone()
            if tombstone:
                raise Conflict('This submission was deliberately deleted; start a new independent intent')
            existing=db.execute('SELECT * FROM idempotency WHERE workspace_id=? AND key=?',(workspace_id,key)).fetchone()
            if existing:
                if existing['request_hash']!=request_hash:raise Conflict('Idempotency key belongs to a different request')
                return self.job(workspace_id,existing['job_id'])  # cross-connection read is safe after existing commit
            identifier=uid()
            if kind=='assess':
                from cv_ranker.build_info import BUILD_ID
                request=dict(request)
                request['assessment_context']={
                    'as_of_date':datetime.now(timezone.utc).date().isoformat(),
                    'engine_build':BUILD_ID,
                    'approved_revision_id':request.get('approved_revision_id'),
                    'candidate_source_ids':list(request.get('candidate_ids',[])),
                    'settings_sha256':fingerprint(request.get('settings',{})),
                }
            total=len(request.get('candidate_ids',[])) if kind=='assess' else 1
            db.execute('''INSERT INTO jobs(id,workspace_id,kind,state,request_json,request_hash,
               progress,total,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)''',
               (identifier,workspace_id,kind,'queued',json_dumps(request),request_hash,0,total,now(),now()))
            db.execute('INSERT INTO idempotency VALUES(?,?,?,?)',(workspace_id,key,request_hash,identifier))
            self._event(db,identifier,'queued',{'state':'queued'})
            self.audit(db,workspace_id,'job_submitted',identifier)
        return self.job(workspace_id,identifier)

    def submission(self, workspace_id: str, key: str):
        """Read-only HTTP-response recovery, using the original workspace-scoped key."""
        if not key or len(key) > 150:
            raise NotFound('Submission intent not found')
        with self.connect() as db:
            row = db.execute('SELECT job_id FROM idempotency WHERE workspace_id=? AND key=?',
                             (workspace_id,key)).fetchone()
        if row is None:
            with self.connect() as db:
                deleted=db.execute('SELECT 1 FROM submission_tombstones WHERE workspace_id=? AND key=?',
                                   (workspace_id,key)).fetchone()
            if deleted:
                raise Conflict('This submission was deliberately deleted; start a new independent intent')
            raise NotFound('Submission intent not found')
        return self.job(workspace_id, row['job_id'])

    def job(self, workspace_id: str, job_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',(job_id,workspace_id)).fetchone()
        if row is None:raise NotFound('Job not found')
        data=dict(row);data['request']=json.loads(row['request_json'])
        # Do not return server filesystem path, frozen secret environment, or raw report on snapshot.
        return {k:v for k,v in data.items() if k not in {'request_json','result_json','request_hash','lease_until','owner'}}

    def get_job_record(self, job_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None:raise NotFound('Job not found')
        return dict(row)

    def jobs(self, workspace_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            return [self.job(workspace_id,row['id']) for row in db.execute(
              'SELECT id FROM jobs WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(workspace_id,)).fetchall()]

    def _event(self, db, job_id: str, kind: str, payload: dict):
        db.execute('UPDATE jobs SET sequence=sequence+1,updated=? WHERE id=?',(now(),job_id))
        seq=db.execute('SELECT sequence FROM jobs WHERE id=?',(job_id,)).fetchone()['sequence']
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(job_id,seq,kind,json_dumps(payload),now()))
        return seq

    def event_snapshot(self, workspace_id: str, job_id: str):
        """One SQLite read transaction: state and event watermark cannot disagree."""
        with self.connect() as db:
            db.execute('BEGIN')
            try:
                row=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',
                               (job_id,workspace_id)).fetchone()
                if row is None:raise NotFound('Job not found')
                earliest=db.execute('SELECT min(seq) FROM events WHERE job_id=?',(job_id,)).fetchone()[0]
                snapshot=dict(row)
                snapshot['request']=json.loads(row['request_json'])
                for field in ('request_json','request_hash','lease_until','owner','result_json'):
                    snapshot.pop(field,None)
                db.commit()
            except Exception:
                db.rollback();raise
        return {'snapshot':snapshot,'earliest':earliest or snapshot['sequence']+1}

    def events(self, workspace_id: str, job_id: str, after: int, limit: int = 100):
        self.job(workspace_id,job_id)
        with self.connect() as db:
            rows=db.execute('SELECT * FROM events WHERE job_id=? AND seq>? ORDER BY seq LIMIT ?',
                            (job_id,after,max(1,min(limit,200)))).fetchall()
        return [dict(r) | {'payload':json.loads(r['payload_json'])} for r in rows]

    def claim_job(self, worker_id: str, lease_seconds: int = 30):
        with self.tx() as db:
            row=db.execute('SELECT * FROM jobs WHERE state=? ORDER BY created LIMIT 1',('queued',)).fetchone()
            if row is None:return None
            fencing=row['fencing']+1
            db.execute('''UPDATE jobs SET state='running',owner=?,fencing=?,lease_until=?,updated=?
                           WHERE id=? AND state='queued' ''',
                       (worker_id,fencing,time.time()+lease_seconds,now(),row['id']))
            self._event(db,row['id'],'running',{'state':'running'})
        return (row['id'],fencing)

    def heartbeat(self, job_id: str, worker_id: str, fence: int, lease_seconds=30):
        with self.tx() as db:
            n=db.execute('''UPDATE jobs SET lease_until=? WHERE id=? AND owner=? AND fencing=? AND state IN ('running','cancelling')''',
                        (time.time()+lease_seconds,job_id,worker_id,fence)).rowcount
        return n==1

    def assert_owner(self, db, job_id: str, worker_id: str, fence: int):
        row=db.execute('SELECT owner,fencing,state FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None or row['owner']!=worker_id or row['fencing']!=fence or row['state'] not in ('running','cancelling'):
            raise Conflict('Worker lease is no longer owned by this attempt')

    def commit_candidate(self, job_id: str, worker_id: str, fence: int, doc_id: str,
                         position: int, result: dict, source_ledger: list, report: dict,
                         metrics: dict | None = None):
        with self.tx() as db:
            self.assert_owner(db,job_id,worker_id,fence)
            db.execute('''INSERT INTO candidate_results VALUES(?,?,?,?,?,?) ON CONFLICT(job_id,document_id)
               DO UPDATE SET result_json=excluded.result_json,source_ledger_json=excluded.source_ledger_json,
               committed=excluded.committed''',
               (job_id,doc_id,position,json_dumps(result),json_dumps(source_ledger),now()))
            progress=db.execute('SELECT count(*) FROM candidate_results WHERE job_id=?',(job_id,)).fetchone()[0]
            db.execute('UPDATE jobs SET result_json=?,result_revision=result_revision+1,progress=?,updated=? WHERE id=?',
                       (json_dumps(report),progress,now(),job_id))
            if metrics:
                row = db.execute('SELECT workspace_id FROM jobs WHERE id=?', (job_id,)).fetchone()
                if row:
                    ws_id = row['workspace_id']
                    existing_metric = db.execute('SELECT metrics_json FROM job_metrics WHERE job_id=?', (job_id,)).fetchone()
                    if existing_metric:
                        prev = json.loads(existing_metric['metrics_json'])
                        accumulated = {
                            'actual_model_request_attempts': prev.get('actual_model_request_attempts', 0) + metrics.get('actual_model_request_attempts', 0),
                            'logical_model_calls': prev.get('logical_model_calls', 0) + metrics.get('logical_model_calls', 0),
                            'validated_identical_prompt_reuses': prev.get('validated_identical_prompt_reuses', 0) + metrics.get('validated_identical_prompt_reuses', 0),
                        }
                        prev_tokens = prev.get('provider_reported_tokens', {})
                        cur_tokens = metrics.get('provider_reported_tokens', {})
                        prompt_tok = None
                        if prev_tokens.get('prompt_tokens') is not None or cur_tokens.get('prompt_tokens') is not None:
                            prompt_tok = (prev_tokens.get('prompt_tokens') or 0) + (cur_tokens.get('prompt_tokens') or 0)
                        comp_tok = None
                        if prev_tokens.get('completion_tokens') is not None or cur_tokens.get('completion_tokens') is not None:
                            comp_tok = (prev_tokens.get('completion_tokens') or 0) + (cur_tokens.get('completion_tokens') or 0)
                        total_tok = None
                        if prev_tokens.get('total_tokens') is not None or cur_tokens.get('total_tokens') is not None:
                            total_tok = (prev_tokens.get('total_tokens') or 0) + (cur_tokens.get('total_tokens') or 0)
                        accumulated['provider_reported_tokens'] = {
                            'prompt_tokens': prompt_tok,
                            'completion_tokens': comp_tok,
                            'total_tokens': total_tok,
                        }
                        db.execute('UPDATE job_metrics SET metrics_json=?, updated=? WHERE job_id=?',
                                   (json_dumps(accumulated), now(), job_id))
                    else:
                        db.execute('INSERT INTO job_metrics VALUES(?,?,?,?)',
                                   (job_id, ws_id, json_dumps(metrics), now()))
                    event_id = f"{job_id}:{doc_id}:candidate_assess"
                    req_row = db.execute('SELECT request_json FROM jobs WHERE id=?', (job_id,)).fetchone()
                    req_obj = json.loads(req_row['request_json']) if req_row and req_row['request_json'] else {}
                    settings_obj = req_obj.get('settings', {})
                    prov = settings_obj.get('provider', 'ollama')
                    if prov == 'openrouter':
                        mod = settings_obj.get('openrouter_model') or settings_obj.get('model_name') or os.environ.get('OPENROUTER_MODEL') or 'google/gemini-2.5-flash-lite'
                    else:
                        mod = settings_obj.get('ollama_model') or settings_obj.get('model_name') or os.environ.get('OLLAMA_MODEL') or 'qwen2.5:3b'
                    toks = metrics.get('provider_reported_tokens', {})
                    p_tok = toks.get('prompt_tokens')
                    c_tok = toks.get('completion_tokens')
                    t_tok = toks.get('total_tokens')
                    is_unk = 1 if (p_tok is None and c_tok is None and t_tok is None) else 0
                    db.execute('''INSERT OR IGNORE INTO usage_events (
                        event_id, job_id, workspace_id, operation_id, stage, candidate_id,
                        provider, model, logical_calls, request_attempts, prompt_tokens,
                        completion_tokens, total_tokens, is_unknown_tokens, cost_amount,
                        cost_currency, cost_provenance, created
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        event_id, job_id, ws_id, None, 'candidate_assessment', doc_id,
                        prov, mod, metrics.get('logical_model_calls', 0),
                        metrics.get('actual_model_request_attempts', 0),
                        p_tok, c_tok, t_tok, is_unk, 0.0, 'USD', 'model_card_estimate', now()
                    ))
            self._event(db,job_id,'candidate_committed',{'document_id':doc_id,'position':position,'completed':progress})

    def set_result(self, job_id: str, worker_id: str, fence: int, result: dict, state: str = 'completed'):
        with self.tx() as db:
            self.assert_owner(db,job_id,worker_id,fence)
            db.execute('''UPDATE jobs SET result_json=?,result_revision=result_revision+1,state=?,owner=NULL,
                         lease_until=NULL,updated=?,progress=total WHERE id=?''',
                       (json_dumps(result),state,now(),job_id))
            self._event(db,job_id,state,{'state':state})

    def terminal(self, job_id: str, worker_id: str, fence: int, state: str, code: str,
                 message: str, eligible_at: float | None = None):
        with self.tx() as db:
            self.assert_owner(db,job_id,worker_id,fence)
            db.execute('''UPDATE jobs SET state=?,owner=NULL,lease_until=NULL,error_code=?,error_message=?,eligible_at=?,updated=? WHERE id=?''',
                       (state,code,message,eligible_at,now(),job_id))
            self._event(db,job_id,state,{'state':state,'error_code':code,'eligible_at':eligible_at})

    def progress(self, job_id: str, worker_id: str, fence: int, message: str):
        # Do not expose full arbitrary progress strings, which may contain CV content.
        safe='Processing candidate evidence' if 'CV ' in message else 'Running assessment stage'
        with self.tx() as db:
            self.assert_owner(db,job_id,worker_id,fence)
            self._event(db,job_id,'progress',{'message':safe})

    def control(self, workspace_id: str, job_id: str, action: str):
        with self.tx() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',(job_id,workspace_id)).fetchone()
            if row is None:raise NotFound('Job not found')
            if action=='cancel':
                if row['state'] in ('completed','completed_with_errors','cancelled','failed'):
                    return self.job(workspace_id,job_id)
                if row['error_code']=='worker_unknown_delivery':
                    raise Conflict('Unknown provider delivery requires explicit reconciliation before cancellation')
                if row['state']=='cancelling':
                    # A second operator/tab cannot revoke ownership while the
                    # first worker might still be inside a billable request.
                    return self.job(workspace_id,job_id)
                new_state='cancelling' if row['state']=='running' else 'cancelled'
                db.execute('UPDATE jobs SET cancel_requested=1,state=?,updated=? WHERE id=?',
                           (new_state,now(),job_id))
                self._event(db,job_id,'cancellation_requested',{'state':new_state})
            elif action=='resume':
                if row['state'] not in ('paused','failed','cancelled','completed_with_errors'):
                    raise Conflict('Only unfinished/failed/cancelled jobs may resume')
                if row['error_code']=='worker_unknown_delivery':
                    # There may be a billed provider call that never reached a
                    # durable per-operation decision. A bare Resume POST cannot
                    # establish non-delivery; require deliberate reconciliation.
                    raise Conflict('Unknown delivery: reconcile the provider operation and preserved result ledger before resubmitting; no automatic retry')
                if row['eligible_at'] is not None and time.time()<row['eligible_at']:
                    raise Conflict('Provider cooldown has not elapsed. Retry is eligible at the stored timestamp.')
                db.execute('''UPDATE jobs SET state='queued',owner=NULL,lease_until=NULL,
                   cancel_requested=0,error_code=NULL,error_message=NULL,eligible_at=NULL,updated=? WHERE id=?''',(now(),job_id))
                self._event(db,job_id,'resumed',{'state':'queued'})
            else:raise ValueError('Unknown action')
        return self.job(workspace_id,job_id)

    def recover_unknown(self, workspace_id: str, job_id: str, resolution: str,
                        acknowledgement: str | None = None):
        """Explicit recovery boundary. No method here contacts the provider.

        Finalized committed candidate siblings are recovered before any new
        scheduling. A dispatch may have been paid even without a local commit;
        only an operator may acknowledge that risk and choose to resubmit.
        """
        with self.tx() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',
                           (job_id,workspace_id)).fetchone()
            if row is None:raise NotFound('Job not found')
            if row['state']!='paused' or row['error_code']!='worker_unknown_delivery':
                raise Conflict('This job is not waiting for unknown-delivery resolution')
            saved=db.execute('SELECT count(*) FROM candidate_results WHERE job_id=?',(job_id,)).fetchone()[0]
            if resolution=='inspect':
                return {'job_id':job_id,'state':'paused','committed_candidates':saved,
                        'total':row['total'],'may_have_incurred_provider_cost':True,
                        'next_actions':['accept_duplicate_risk']}
            if resolution!='accept_duplicate_risk':
                raise ValueError('Unknown recovery resolution')
            if acknowledgement!='I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES':
                raise Conflict('Explicit duplicate-charge acknowledgement is required')
            db.execute('''UPDATE jobs SET state='queued',owner=NULL,lease_until=NULL,cancel_requested=0,
                          error_code=NULL,error_message=NULL,recovery_resolution=?,updated=? WHERE id=?''',
                       ('operator_acknowledged_duplicate_cost',now(),job_id))
            self._event(db,job_id,'recovery_acknowledged',{'state':'queued',
                        'committed_candidates':saved,'duplicate_billing_risk_acknowledged':True})
            self.audit(db,workspace_id,'unknown_delivery_operator_resolution',job_id)
        return self.job(workspace_id,job_id)

    def _safe_unlink(self, root: Path, stored_name: str, root_type: str | None = None) -> bool:
        path = (root / stored_name).resolve()
        if path.parent != root.resolve():
            raise RuntimeError('Stored path is outside its private data directory')
        rtype = root_type or ('exports' if root == self.export_root else 'documents')
        cleanup_id = uid()
        try:
            with self.tx() as db:
                db.execute('''INSERT OR IGNORE INTO pending_cleanups (id, root_type, stored_name, attempts, last_error, created, updated)
                              VALUES (?, ?, ?, 0, NULL, ?, ?)''', (cleanup_id, rtype, stored_name, now(), now()))
        except Exception:
            pass
        try:
            path.unlink(missing_ok=True)
            try:
                with self.tx() as db:
                    db.execute('DELETE FROM pending_cleanups WHERE root_type=? AND stored_name=?', (rtype, stored_name))
            except Exception:
                pass
            return True
        except OSError as exc:
            try:
                with self.tx() as db:
                    db.execute('''UPDATE pending_cleanups SET attempts = attempts + 1, last_error = ?, updated = ?
                                  WHERE root_type=? AND stored_name=?''', (str(exc), now(), rtype, stored_name))
            except Exception:
                pass
            return False

    def process_pending_cleanups(self) -> int:
        """Retry deleting unlinked physical files previously blocked by Windows file locks."""
        cleaned = 0
        try:
            with self.connect() as db:
                rows = [dict(r) for r in db.execute('SELECT * FROM pending_cleanups').fetchall()]
        except Exception:
            return 0
        for r in rows:
            root = self.export_root if r['root_type'] == 'exports' else self.upload_root
            path = (root / r['stored_name']).resolve()
            if path.parent != root.resolve():
                continue
            try:
                path.unlink(missing_ok=True)
                with self.tx() as db:
                    db.execute('DELETE FROM pending_cleanups WHERE id=?', (r['id'],))
                cleaned += 1
            except OSError as exc:
                with self.tx() as db:
                    db.execute('UPDATE pending_cleanups SET attempts = attempts + 1, last_error = ?, updated = ? WHERE id=?',
                               (str(exc), now(), r['id']))
        return cleaned

    def list_pending_cleanups(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM pending_cleanups ORDER BY created').fetchall()]

    def delete_assessment(self, workspace_id: str, job_id: str):
        """Delete only terminal job data; never race an active worker."""
        names=[]
        with self.tx() as db:
            job=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',(job_id,workspace_id)).fetchone()
            if job is None:raise NotFound('Assessment job not found')
            if job['state'] in ('queued','running','cancelling'):
                raise Conflict('Stop and reconcile the active worker before deleting a job')
            if job['error_code']=='worker_unknown_delivery':
                raise Conflict('Resolve unknown provider delivery before deleting source checkpoints')
            names=[r['stored_name'] for r in db.execute('SELECT stored_name FROM exports WHERE job_id=?',(job_id,))]
            db.execute('''INSERT OR IGNORE INTO submission_tombstones(workspace_id,key,request_hash,deleted_at)
                 SELECT workspace_id,key,request_hash,? FROM idempotency WHERE job_id=?''',(now(),job_id))
            for table in ('operations','usage_events','focused_reviews','semantic_shadows','job_metrics','candidate_results','events','exports','idempotency'):
                db.execute(f'DELETE FROM {table} WHERE job_id=?',(job_id,))
            db.execute('DELETE FROM jobs WHERE id=?',(job_id,))
            self.audit(db,workspace_id,'assessment_job_deleted',job_id)
        for name in names:self._safe_unlink(self.export_root,name)
        return {'deleted':job_id}

    def delete_workspace(self, workspace_id: str):
        """Explicit wholesale private-record deletion, without weakening FKs."""
        paths=[]
        with self.tx() as db:
            if db.execute('SELECT 1 FROM workspaces WHERE id=?',(workspace_id,)).fetchone() is None:
                raise NotFound('Workspace unavailable')
            jobs=db.execute('SELECT * FROM jobs WHERE workspace_id=?',(workspace_id,)).fetchall()
            if any(j['state'] in ('queued','running','cancelling') or
                   j['error_code']=='worker_unknown_delivery' for j in jobs):
                raise Conflict('Resolve all active and unknown-delivery jobs before deleting a workspace')
            paths.extend((self.export_root,r['stored_name']) for r in db.execute(
                'SELECT stored_name FROM exports WHERE workspace_id=?',(workspace_id,)))
            paths.extend((self.upload_root,r['stored_name']) for r in db.execute(
                'SELECT stored_name FROM documents WHERE workspace_id=?',(workspace_id,)))
            ids=[r['id'] for r in jobs]
            for job_id in ids:
                for table in ('operations','usage_events','focused_reviews','semantic_shadows','job_metrics','candidate_results','events','exports','idempotency'):
                    db.execute(f'DELETE FROM {table} WHERE job_id=?',(job_id,))
            db.execute('DELETE FROM jobs WHERE workspace_id=?',(workspace_id,))
            db.execute('DELETE FROM jd_approvals WHERE workspace_id=?',(workspace_id,))
            db.execute('DELETE FROM jd_drafts WHERE workspace_id=?',(workspace_id,))
            for table in ('operations','usage_events','focused_reviews','semantic_shadows','job_metrics','documents','weights','historical_reports','submission_tombstones'):
                db.execute(f'DELETE FROM {table} WHERE workspace_id=?',(workspace_id,))
            db.execute('DELETE FROM workspaces WHERE id=?',(workspace_id,))
            self.audit(db,workspace_id,'workspace_deleted',workspace_id)
        for root,stored in paths:self._safe_unlink(root,stored)
        return {'deleted':workspace_id}

    def delete_export(self, workspace_id: str, export_id: str):
        with self.tx() as db:
            row=db.execute('SELECT * FROM exports WHERE workspace_id=? AND id=?',
                           (workspace_id,export_id)).fetchone()
            if row is None:raise NotFound('Export not found')
            # Never delete if this job is active: export may be in preparation.
            job=db.execute('SELECT state FROM jobs WHERE id=?',(row['job_id'],)).fetchone()
            if job['state'] in ('running','queued','cancelling'):
                raise Conflict('Cannot delete an export while its assessment job is active')
            db.execute('DELETE FROM exports WHERE id=?',(export_id,))
            self.audit(db,workspace_id,'export_deleted',export_id)
        self._safe_unlink(self.export_root,row['stored_name'])
        return {'deleted':export_id}

    def delete_document(self, workspace_id: str, doc_id: str):
        with self.tx() as db:
            doc=db.execute('SELECT * FROM documents WHERE workspace_id=? AND id=?',
                           (workspace_id,doc_id)).fetchone()
            if doc is None:raise NotFound('Document not found')
            if db.execute('SELECT 1 FROM jd_drafts WHERE document_id=? LIMIT 1',(doc_id,)).fetchone():
                raise Conflict('This JD has an immutable draft or approval; preserve assessment provenance')
            if db.execute('SELECT 1 FROM candidate_results WHERE document_id=? LIMIT 1',(doc_id,)).fetchone():
                raise Conflict('This CV is referenced by committed candidate evidence')
            jobs=db.execute('SELECT id,state,request_json FROM jobs WHERE workspace_id=?',
                            (workspace_id,)).fetchall()
            for job in jobs:
                request=json.loads(job['request_json'])
                if doc_id==request.get('document_id') or doc_id in request.get('candidate_ids',[]):
                    if job['state'] in ('queued','running','cancelling'):
                        raise Conflict('A job still references this document; cancel and reconcile first')
                    # Historical jobs must retain their inputs to support
                    # restart, audit and immutable evidence identity.
                    raise Conflict('A retained job references this document; delete the job through an audited retention workflow first')
            db.execute('DELETE FROM documents WHERE id=?',(doc_id,))
            self.audit(db,workspace_id,'document_deleted',doc_id)
        self._safe_unlink(self.upload_root,doc['stored_name'])
        return {'deleted':doc_id}

    def committed_candidates(self, job_id: str):
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM candidate_results WHERE job_id=? ORDER BY position',(job_id,))]

    def assessment_snapshot(self, workspace_id: str, job_id: str):
        """One SQLite WAL read snapshot for report, revisions, weights, and ledgers.

        Revisions returned here label exactly the values read in this same
        transaction, rather than a later separately queried job counter.
        """
        with self.connect() as db:
            db.execute('BEGIN')
            try:
                job=db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?',
                               (job_id,workspace_id)).fetchone()
                if job is None:raise NotFound('Assessment job not found')
                weight=db.execute('SELECT * FROM weights WHERE workspace_id=?',(workspace_id,)).fetchone()
                if weight is None:
                    from cv_ranker.weighted_scoring import ScoreWeights
                    weight_revision=0
                    weight_body=ScoreWeights().as_dict()
                else:
                    weight_revision=weight['revision']
                    weight_body=json.loads(weight['body_json'])
                ledgers=[dict(x) for x in db.execute(
                    'SELECT * FROM candidate_results WHERE job_id=? ORDER BY position',(job_id,))]
                result={'job':dict(job),'report':json.loads(job['result_json']) if job['result_json'] else None,
                        'result_revision':job['result_revision'],'weight_revision':weight_revision,
                        'weights':weight_body,'ledgers':ledgers}
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def report(self, workspace_id: str, job_id: str):
        row=self.get_job_record(job_id)
        if row['workspace_id']!=workspace_id:raise NotFound('Job not found')
        return json.loads(row['result_json']) if row['result_json'] else None

    def reap_stale(self):
        # Lost process may have made paid calls: never silently requeue.
        with self.tx() as db:
            rows=db.execute("SELECT id FROM jobs WHERE state IN ('running','cancelling') AND lease_until<?",
                            (time.time(),)).fetchall()
            for row in rows:
                db.execute('''UPDATE jobs SET state='paused',owner=NULL,lease_until=NULL,
                    error_code='worker_unknown_delivery',error_message='Worker stopped; review persisted results before Resume',
                    updated=? WHERE id=?''',(now(),row['id']))
                self._event(db,row['id'],'worker_lost',{'state':'paused','code':'worker_unknown_delivery'})
        return len(rows)

    def historical(self, workspace_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT id,workspace_id,source_name,source_build,created
                   FROM historical_reports WHERE workspace_id=? ORDER BY created DESC''',(workspace_id,))]

    def historical_report(self, workspace_id: str, report_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM historical_reports WHERE id=? AND workspace_id=?',(report_id,workspace_id)).fetchone()
        if row is None:raise NotFound('Historical report not found')
        return {**dict(row),'body':json.loads(row['body_json'])}

    def import_historical(self, workspace_id: str, source_name: str, body: dict):
        self.workspace(workspace_id)
        identifier=uid()
        with self.tx() as db:
            db.execute('INSERT INTO historical_reports VALUES(?,?,?,?,?,?)',
                       (identifier,workspace_id,source_name[:140],body.get('build_id','historical'),
                        json_dumps(body),now()))
            self.audit(db,workspace_id,'historical_report_imported',identifier)
        return self.historical_report(workspace_id,identifier)

    def export_row(self, workspace_id: str, export_id: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM exports WHERE id=? AND workspace_id=?',(export_id,workspace_id)).fetchone()
        if row is None:raise NotFound('Export not found')
        return dict(row)

    def record_export(self, workspace_id: str, job_id: str, weight_revision: int, result_revision: int, data: bytes):
        identifier=uid();name=identifier+'.zip'
        path=self.export_root/name
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        try:
            with self.tx() as db:
                current=db.execute('SELECT result_revision,state FROM jobs WHERE id=? AND workspace_id=?',
                                   (job_id,workspace_id)).fetchone()
                config=db.execute('SELECT revision FROM weights WHERE workspace_id=?',(workspace_id,)).fetchone()
                if (current is None or current['result_revision']!=result_revision
                        or (config['revision'] if config else 0)!=weight_revision):
                    raise Conflict('Result or weight revision changed during export; retry with fresh results')
                db.execute('INSERT INTO exports VALUES(?,?,?,?,?,?,?,?)',
                    (identifier,job_id,workspace_id,weight_revision,result_revision,name,len(data),now()))
                self.audit(db,workspace_id,'export_created',identifier)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.export_row(workspace_id,identifier)

    def exports(self, workspace_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            return [dict(x) for x in db.execute('SELECT * FROM exports WHERE workspace_id=? ORDER BY created DESC',(workspace_id,))]

    def execute_focused_review(self, workspace_id: str, job_id: str, candidate_id: str,
                               requirement_id: str, provider: str | None = None,
                               use_llm: bool | None = None,
                               *, ranker_factory = None,
                               expected_result_revision: int | None = None,
                               idempotency_key: str | None = None):
        from backend import engine_service
        with self.connect() as db:
            job = db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?', (job_id, workspace_id)).fetchone()
            if job is None:
                raise NotFound('Assessment job not found')
            if job['state'] in ('queued', 'running', 'cancelling'):
                raise Conflict('Wait for assessment processing to finish or pause before running a focused review')
            if not job['result_json']:
                raise Conflict('Assessment has not produced a report to review')

            base_revision = job['result_revision']
            if expected_result_revision is not None and base_revision != expected_result_revision:
                raise Conflict(f'Report revision conflict: expected revision {expected_result_revision}, but current revision is {base_revision}')

            cand_row = db.execute('SELECT * FROM candidate_results WHERE job_id=? AND document_id=?',
                                  (job_id, candidate_id)).fetchone()
            if cand_row is None:
                raise NotFound('Candidate result not found')
            ledger_data = json.loads(cand_row['source_ledger_json'])
            segments = ledger_data.get('segments', [])
            job_request = json.loads(job['request_json'])
            settings = dict(job_request.get('settings', {}))
            if provider is not None:
                settings['provider'] = provider
            if use_llm is not None:
                settings['use_llm'] = use_llm
            report_data = json.loads(job['result_json'])

        operation_id = uid()
        req_fp = f"{candidate_id}:{requirement_id}:{settings.get('provider')}:{settings.get('use_llm')}"
        effective_key = idempotency_key or req_fp

        outcome = None
        with self.tx() as db:
            op = db.execute('''SELECT * FROM operations WHERE workspace_id=? AND operation_type=? AND idempotency_key=?''',
                            (workspace_id, 'focused_review', effective_key)).fetchone()
            if op:
                if op['state'] == 'completed' and op['saved_response_json']:
                    saved_res = json.loads(op['saved_response_json'])
                    saved_res['result_revision'] = op['committed_revision'] or saved_res.get('result_revision')
                    return saved_res
                elif op['state'] == 'response_saved' and op['saved_response_json']:
                    outcome = json.loads(op['saved_response_json'])
                    operation_id = op['id']
                else:
                    db.execute('''UPDATE operations SET attempt_count = attempt_count + 1, updated=? WHERE id=?''',
                               (now(), op['id']))
                    operation_id = op['id']
            else:
                db.execute('''INSERT INTO operations (
                    id, workspace_id, job_id, operation_type, candidate_id, requirement_id,
                    idempotency_key, request_fingerprint, base_result_revision, state,
                    attempt_count, resolved_provider, resolved_model, created, updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', 1, ?, ?, ?, ?)''',
                (
                    operation_id, workspace_id, job_id, 'focused_review', candidate_id, requirement_id,
                    effective_key, req_fp, base_revision,
                    settings.get('provider', 'ollama'), settings.get('model_name', ''),
                    now(), now()
                ))

        if outcome is None:
            outcome = engine_service.focused_review_candidate(
                report_data, candidate_id, requirement_id, segments, settings,
                ranker_factory=ranker_factory,
            )
            with self.tx() as db:
                db.execute('''UPDATE operations SET state='response_saved', saved_response_json=?, updated=? WHERE id=?''',
                           (json_dumps(outcome), now(), operation_id))

        review_id = uid()
        with self.tx() as db:
            current_job = db.execute('SELECT result_revision, result_json FROM jobs WHERE id=?', (job_id,)).fetchone()
            current_revision = current_job['result_revision']
            if expected_result_revision is not None and current_revision != expected_result_revision:
                raise Conflict(f'Report revision conflict: revision changed from {expected_result_revision} to {current_revision} during evaluation')

            if current_revision != base_revision:
                current_report = json.loads(current_job['result_json'])
                cand_idx = next((i for i, c in enumerate(current_report['candidates']) if c['candidate_source'] == candidate_id), -1)
                if cand_idx >= 0:
                    new_cand_assess = outcome['updated_candidate']['assessments']
                    current_cand_assess = current_report['candidates'][cand_idx]['assessments']
                    for na in new_cand_assess:
                        if na['requirement_id'] == requirement_id:
                            for idx, ca in enumerate(current_cand_assess):
                                if ca['requirement_id'] == requirement_id:
                                    current_cand_assess[idx] = na
                                    break
                    from cv_ranker.schemas import RequirementAssessment, CandidateResult
                    from cv_ranker.scoring import score_candidate, assign_ranks
                    rescored = score_candidate(
                        candidate_name=current_report['candidates'][cand_idx]['candidate_name'],
                        requirements=report_data['requirements'],
                        assessments=[RequirementAssessment.model_validate(a) for a in current_cand_assess],
                        evaluation_mode=current_report['candidates'][cand_idx]['evaluation_mode'],
                        errors=current_report['candidates'][cand_idx].get('errors', []),
                        candidate_source=candidate_id,
                    )
                    current_report['candidates'][cand_idx] = rescored.model_dump(mode='json')
                    current_report['candidates'] = [c.model_dump(mode='json') for c in assign_ranks([CandidateResult.model_validate(c) for c in current_report['candidates']])]
                    final_report = current_report
                    final_candidate = current_report['candidates'][cand_idx]
                else:
                    final_report = outcome['updated_report']
                    final_candidate = outcome['updated_candidate']
            else:
                final_report = outcome['updated_report']
                final_candidate = outcome['updated_candidate']

            new_revision = current_revision + 1
            db.execute('''UPDATE jobs SET result_json=?, result_revision=?, updated=? WHERE id=?''',
                       (json_dumps(final_report), new_revision, now(), job_id))
            db.execute('''UPDATE candidate_results SET result_json=?, committed=? WHERE job_id=? AND document_id=?''',
                       (json_dumps(final_candidate), now(), job_id, candidate_id))
            db.execute('''INSERT INTO focused_reviews VALUES(?,?,?,?,?,?,?,?,?,?)''',
                       (review_id, workspace_id, job_id, candidate_id, requirement_id,
                        outcome['prior_verdict'], outcome['new_verdict'], outcome['explanation'],
                        json_dumps(outcome['citations']), now()))
            response_payload = {
                'candidate_id': candidate_id,
                'requirement_id': requirement_id,
                'prior_verdict': outcome['prior_verdict'],
                'new_verdict': outcome['new_verdict'],
                'explanation': outcome['explanation'],
                'result_revision': new_revision,
                'citations': outcome['citations'],
            }
            db.execute('''UPDATE operations SET state='completed', committed_revision=?, saved_response_json=?, updated=? WHERE id=?''',
                       (new_revision, json_dumps(response_payload), now(), operation_id))
            self.audit(db, workspace_id, 'focused_review_finalized', review_id)
            self._event(db, job_id, 'focused_review_completed', {
                'candidate_id': candidate_id,
                'requirement_id': requirement_id,
                'verdict': outcome['new_verdict'],
                'result_revision': new_revision,
            })

        return response_payload

    def list_focused_reviews(self, workspace_id: str, job_id: str, candidate_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            rows = db.execute(
                '''SELECT id, job_id, candidate_id, requirement_id, prior_verdict, new_verdict,
                          explanation, sources_json, created
                   FROM focused_reviews WHERE workspace_id=? AND job_id=? AND candidate_id=?
                   ORDER BY created DESC''',
                (workspace_id, job_id, candidate_id)).fetchall()
        return [
            {
                'id': r['id'],
                'job_id': r['job_id'],
                'candidate_id': r['candidate_id'],
                'requirement_id': r['requirement_id'],
                'prior_verdict': r['prior_verdict'],
                'new_verdict': r['new_verdict'],
                'explanation': r['explanation'],
                'sources': json.loads(r['sources_json']),
                'created': r['created'],
            }
            for r in rows
        ]

    def save_semantic_shadow(self, workspace_id: str, job_id: str, shadow_data: dict):
        self.workspace(workspace_id)
        identifier = uid()
        with self.tx() as db:
            db.execute('''INSERT INTO semantic_shadows VALUES(?,?,?,?,?,?)''',
                       (identifier, workspace_id, job_id,
                        json_dumps(shadow_data.get('retrieval', {})),
                        json_dumps(shadow_data), now()))
            self.audit(db, workspace_id, 'semantic_shadow_executed', identifier)
        return shadow_data

    def get_semantic_shadow(self, workspace_id: str, job_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            row = db.execute(
                '''SELECT proposals_json FROM semantic_shadows WHERE workspace_id=? AND job_id=?
                   ORDER BY created DESC LIMIT 1''',
                (workspace_id, job_id)).fetchone()
        if row is None:
            return {
                'ready': False,
                'scoring_unchanged': True,
                'notice': 'Semantic shadow has not been run for this assessment.',
                'items': [],
            }
        return json.loads(row['proposals_json'])

    def record_usage_event(self, job_id: str, workspace_id: str, event_id: str,
                           stage: str, provider: str, model: str,
                           candidate_id: str | None = None, operation_id: str | None = None,
                           logical_calls: int = 0, request_attempts: int = 0,
                           prompt_tokens: int | None = None, completion_tokens: int | None = None,
                           total_tokens: int | None = None, is_unknown_tokens: bool = False,
                           cost_amount: float = 0.0, cost_currency: str = 'USD',
                           cost_provenance: str = 'model_card_estimate') -> bool:
        with self.tx() as db:
            cur = db.execute('''INSERT OR IGNORE INTO usage_events (
                event_id, job_id, workspace_id, operation_id, stage, candidate_id,
                provider, model, logical_calls, request_attempts, prompt_tokens,
                completion_tokens, total_tokens, is_unknown_tokens, cost_amount,
                cost_currency, cost_provenance, created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                event_id, job_id, workspace_id, operation_id, stage, candidate_id,
                provider, model, logical_calls, request_attempts, prompt_tokens,
                completion_tokens, total_tokens, 1 if is_unknown_tokens else 0,
                cost_amount, cost_currency, cost_provenance, now()
            ))
            return cur.rowcount > 0

    def get_job_metrics(self, workspace_id: str, job_id: str):
        self.workspace(workspace_id)
        with self.connect() as db:
            job = db.execute('SELECT * FROM jobs WHERE id=? AND workspace_id=?', (job_id, workspace_id)).fetchone()
            if job is None:
                raise NotFound('Job not found')
            events = [dict(r) for r in db.execute('SELECT * FROM usage_events WHERE job_id=?', (job_id,)).fetchall()]
            metric_row = db.execute('SELECT metrics_json FROM job_metrics WHERE job_id=?', (job_id,)).fetchone()

        req = json.loads(job['request_json'])
        settings = req.get('settings', {})
        provider = settings.get('provider', 'ollama')
        if provider == 'openrouter':
            model = settings.get('openrouter_model') or settings.get('model_name') or os.environ.get('OPENROUTER_MODEL') or 'google/gemini-2.5-flash-lite'
        else:
            model = settings.get('ollama_model') or settings.get('model_name') or os.environ.get('OLLAMA_MODEL') or 'qwen2.5:3b'

        if events:
            logical_calls = sum(e['logical_calls'] for e in events)
            http_attempts = sum(e['request_attempts'] for e in events)
            reuses = 0
            if metric_row:
                raw_m = json.loads(metric_row['metrics_json'])
                reuses = raw_m.get('validated_identical_prompt_reuses', 0)
            any_unknown = any(e['is_unknown_tokens'] for e in events)
            has_p = any(e['prompt_tokens'] is not None for e in events)
            has_c = any(e['completion_tokens'] is not None for e in events)
            prompt_tok = sum(e['prompt_tokens'] for e in events if e['prompt_tokens'] is not None) if (has_p and not any_unknown) else None
            comp_tok = sum(e['completion_tokens'] for e in events if e['completion_tokens'] is not None) if (has_c and not any_unknown) else None
            total_tok = sum(e['total_tokens'] for e in events if e['total_tokens'] is not None) if (has_p and has_c and not any_unknown) else None
            provider = events[0]['provider'] or provider
            model = events[0]['model'] or model
        elif metric_row is not None:
            raw = json.loads(metric_row['metrics_json'])
            token_usage = raw.get('provider_reported_tokens', {})
            prompt_tok = token_usage.get('prompt_tokens')
            comp_tok = token_usage.get('completion_tokens')
            total_tok = token_usage.get('total_tokens')
            logical_calls = raw.get('logical_model_calls', 0)
            http_attempts = raw.get('actual_model_request_attempts', 0)
            reuses = raw.get('validated_identical_prompt_reuses', 0)
        else:
            prompt_tok = comp_tok = total_tok = None
            logical_calls = http_attempts = reuses = 0

        KNOWN_CLOUD_RATES = {
            'google/gemini-2.5-flash-lite': (0.000000075, 0.00000030),
            'google/gemini-2.0-flash-lite': (0.000000075, 0.00000030),
            'qwen/qwen-2.5-7b-instruct': (0.00000015, 0.00000060),
            'deepseek/deepseek-chat': (0.00000014, 0.00000028),
        }

        if provider == 'ollama':
            cost = 0.0
            cost_label = f'Estimated cost: $0.00 (Local model {model} - zero provider cost)'
            preserved_unknown = False
        elif prompt_tok is not None and comp_tok is not None:
            if model in KNOWN_CLOUD_RATES:
                rate_prompt, rate_comp = KNOWN_CLOUD_RATES[model]
                cost = (prompt_tok * rate_prompt) + (comp_tok * rate_comp)
                cost_label = f'Estimated cost: ${cost:.4f} USD (OpenRouter {model})'
                preserved_unknown = False
            else:
                cost = None
                cost_label = f'Pricing tariff unknown for {model} - cost estimate unavailable'
                preserved_unknown = True
        else:
            cost = None
            cost_label = 'Token usage unknown - provider did not report token counts'
            preserved_unknown = True

        return {
            'job_id': job_id,
            'provider': provider,
            'model': model,
            'logical_model_calls': logical_calls,
            'actual_model_request_attempts': http_attempts,
            'token_usage': {
                'prompt_tokens': prompt_tok,
                'completion_tokens': comp_tok,
                'total_tokens': total_tok,
            },
            'estimated_cost_usd': cost,
            'cost_label': cost_label,
            'reused_prompt_calls': reuses,
            'preserved_unknown': preserved_unknown,
        }

    def _retention_plan(self, db, workspace_id: str, retention_days: int) -> dict:
        if retention_days < 1:
            raise ValueError('Retention period must be at least 1 day')
        cutoff_sec = time.time() - (retention_days * 86400)
        cutoff_str = str(int(cutoff_sec))

        active_jobs = db.execute(
            "SELECT count(*) FROM jobs WHERE workspace_id=? AND state IN ('queued','running','cancelling')",
            (workspace_id,)).fetchone()[0]
        unknown_jobs = db.execute(
            "SELECT count(*) FROM jobs WHERE workspace_id=? AND error_code='worker_unknown_delivery'",
            (workspace_id,)).fetchone()[0]

        eligible_jobs = db.execute(
            """SELECT id FROM jobs WHERE workspace_id=?
               AND state IN ('completed','completed_with_errors','cancelled','failed')
               AND (error_code IS NULL OR error_code != 'worker_unknown_delivery')
               AND strftime('%s', updated) < ?""",
            (workspace_id, cutoff_str)).fetchall()
        eligible_job_ids = [r['id'] for r in eligible_jobs]

        if eligible_job_ids:
            qmarks = ','.join('?' * len(eligible_job_ids))
            exports = db.execute(
                f"""SELECT id, stored_name FROM exports WHERE workspace_id=?
                    AND (job_id IN ({qmarks}) OR strftime('%s', created) < ?)""",
                [workspace_id] + eligible_job_ids + [cutoff_str]).fetchall()
        else:
            exports = db.execute(
                "SELECT id, stored_name FROM exports WHERE workspace_id=? AND strftime('%s', created) < ?",
                (workspace_id, cutoff_str)).fetchall()

        retained_jobs = db.execute(
            "SELECT id, request_json FROM jobs WHERE workspace_id=?", (workspace_id,)).fetchall()
        protected_doc_ids = set()
        for j in retained_jobs:
            if j['id'] not in eligible_job_ids:
                try:
                    req_data = json.loads(j['request_json'])
                    if 'document_id' in req_data:
                        protected_doc_ids.add(req_data['document_id'])
                    for cid in req_data.get('candidate_ids', []):
                        protected_doc_ids.add(cid)
                except Exception:
                    pass
                for cr in db.execute("SELECT document_id FROM candidate_results WHERE job_id=?", (j['id'],)).fetchall():
                    protected_doc_ids.add(cr['document_id'])
                for fr in db.execute("SELECT candidate_id FROM focused_reviews WHERE job_id=?", (j['id'],)).fetchall():
                    protected_doc_ids.add(fr['candidate_id'])

        for dr in db.execute("SELECT document_id FROM jd_drafts WHERE workspace_id=?", (workspace_id,)).fetchall():
            protected_doc_ids.add(dr['document_id'])

        expired_docs = db.execute(
            """SELECT id, stored_name FROM documents WHERE workspace_id=?
               AND strftime('%s', created) < ?""",
            (workspace_id, cutoff_str)).fetchall()

        eligible_docs = [doc for doc in expired_docs if doc['id'] not in protected_doc_ids]

        return {
            'workspace_id': workspace_id,
            'retention_days': retention_days,
            'cutoff_sec': cutoff_sec,
            'active_jobs': active_jobs,
            'unknown_jobs': unknown_jobs,
            'eligible_jobs': eligible_job_ids,
            'eligible_exports': exports,
            'eligible_documents': eligible_docs,
        }

    def get_retention_summary(self, workspace_id: str, default_days: int = 30):
        self.workspace(workspace_id)
        with self.connect() as db:
            plan = self._retention_plan(db, workspace_id, default_days)
            return {
                'workspace_id': workspace_id,
                'eligible_jobs': len(plan['eligible_jobs']),
                'eligible_exports': len(plan['eligible_exports']),
                'eligible_documents': len(plan['eligible_documents']),
                'protected_active_jobs': plan['active_jobs'],
                'protected_unknown_delivery_jobs': plan['unknown_jobs'],
                'default_retention_days': default_days,
            }

    def purge_retention(self, workspace_id: str, retention_days: int = 30):
        self.workspace(workspace_id)
        export_paths = []
        doc_paths = []
        with self.tx() as db:
            plan = self._retention_plan(db, workspace_id, retention_days)
            job_ids = plan['eligible_jobs']
            exports = plan['eligible_exports']
            docs = plan['eligible_documents']

            for exp in exports:
                export_paths.append((self.export_root, exp['stored_name']))
                db.execute("DELETE FROM exports WHERE id=?", (exp['id'],))

            for jid in job_ids:
                for tbl in ('operations', 'usage_events', 'focused_reviews', 'semantic_shadows', 'job_metrics', 'candidate_results', 'events', 'idempotency'):
                    db.execute(f"DELETE FROM {tbl} WHERE job_id=?", (jid,))
                db.execute("DELETE FROM jobs WHERE id=?", (jid,))

            for doc in docs:
                doc_paths.append((self.upload_root, doc['stored_name']))
                db.execute("DELETE FROM documents WHERE id=?", (doc['id'],))

            purged_jobs = len(job_ids)
            purged_exports = len(exports)
            purged_docs = len(docs)
            self.audit(db, workspace_id, 'retention_purged',
                       f"jobs:{purged_jobs},exports:{purged_exports},documents:{purged_docs},days:{retention_days}")

        for root, stored in export_paths + doc_paths:
            self._safe_unlink(root, stored)

        return {
            'purged_jobs': purged_jobs,
            'purged_exports': purged_exports,
            'purged_documents': purged_docs,
            'retention_days': retention_days,
        }

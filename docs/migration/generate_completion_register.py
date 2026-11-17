"""Merge 41 original parity rows with evidence-based completion findings."""
from __future__ import annotations
from pathlib import Path
import csv

HERE=Path(__file__).resolve().parent
rows=list(csv.DictReader((HERE/'PARITY_REGISTER_SOURCE.csv').open(encoding='utf-8-sig',newline='')))
extra=[
 ('Lost HTTP submission response','Duplicate assessments and provider costs','frontend/src/api/submissionIntent.ts; backend.storage.submission','Same intent must use the original key across tabs/restarts','tests/web/test_submission_identity.py; frontend/tests/submissionIntent.test.mjs','Implemented, available checks verified','Real browser restart still unverified'),
 ('Deleted job retry tombstone','Deleted applicant job could be recreated by a stale browser','backend.storage; schema v4','Old key must conflict after deletion','tests/web/test_submission_identity.py::test_deleted_job_cannot_be_recreated_by_stale_browser_intent','Verified','Native Windows schema migration unverified'),
 ('Candidate batching 1/6/7/12/13','Candidate skipped after one bounded batch','worker.runner.process_claim','Every candidate gets its own durable checkpoint','tests/web/test_batch_parity.py','Verified','Actual paid LLM batches not exercised'),
 ('Unreadable sibling input','One corrupt CV blocks all other candidates','worker.runner.process_claim','Incomplete CV has null score; healthy siblings finish','tests/web/test_input_sibling_survival.py','Verified','Complex scanned PDFs not model-qualified'),
 ('Cancel during response receipt','Received paid response could be discarded when Cancel arrived','worker.runner.process_claim','Commit result before stopping next candidate','tests/web/test_worker_cancel_siblings.py','Verified','Cannot cancel already-sent remote call'),
 ('SSE duplicates/reconnect','Unnecessary simultaneous stream and polling reads','frontend/src/api/observation.ts; pages/Results.tsx','Sequence dedupe, backoff, fallback-only polling, terminal cleanup','frontend/tests/observation.test.mjs','Implemented, verification pending','Real browser/HTTP cutover untested'),
 ('Nested candidate API contracts','Source and Why returned as untyped arbitrary dicts','backend/contracts.py; frontend/src/api/client.ts','Typed criteria, checkpoint and processing metadata','tests/web/test_result_revision_consistency.py; scripts/generate_web_contract.py --check','Implemented, available checks verified','Frontend npm typecheck blocked'),
 ('Candidate screen evidence field','Why screen used nonexisting Evidence checkpoints field','frontend/src/pages/Results.tsx','Display engine Checkpoints and JD source','source inspection; test_result_revision_consistency.py','Implemented, verification pending','Browser visual tests not runnable'),
 ('Primary vs weighted score','Candidate detail labeled primary score as weighted official score','frontend/src/pages/Results.tsx','Display canonical weighted projection with revision','tests/web/test_result_revision_consistency.py','Implemented, verification pending','React bundle unavailable'),
 ('Focused operator review','Cannot explicitly run bounded focused judge from web','existing cv_ranker/ui/final_decisions.py','Durable explicit job with validated canonical successor result','No new verified test','Open','Requires service+worker+UI implementation; not an external gate'),
 ('Optional semantic shadow','No explicit operator shadow retrieval flow','existing cv_ranker.pipeline.run_semantic_shadow','Bounded explicit source-grounded retrieval, no scoring promotion','Existing engine semantic tests only','Open','Requires new shared API/worker/UI workflow'),
 ('Actual modern frontend bundle','Web UI returns 503 until Vite build is produced','frontend/package.json; frontend/vite.config.ts','Authentic lockfile, npm ci, strict typecheck, lint, tests, vite build','verification/completion_v3/npm_install.log','Open','npm registry DNS/ENOTCACHED external block to building'),
 ('Retention automation','No scheduled policy purge, only explicit deletion','backend.storage; scripts/data_backup.py','Configured policy with safe references and audit','No automated-retention test','Open','Missing implementation'),
 ('Windows 10 native qualification','Cannot confirm launch or installer paths on Windows','install_web.cmd; run_web.cmd; stop_web.cmd','Windows Python 3.11 + Node 22 native run/stop/restart','No Windows test','Externally blocked','No Windows machine in execution environment'),
 ('Live provider acceptance','No measured model accuracy, tokens or costs','cv_ranker engine remains unchanged','Authorized local/cloud test with heldout cross-department records','No live-provider evaluation','Externally blocked','No approved provider/cost budget'),
]
fields=['Issue ID','User-visible consequence','Existing behavior','Source owner','New implementation location','API operation','UI control or screen','Required behavior','Regression / acceptance evidence','Status','Concrete blocker / remaining limitation']
compiled=[]
for i,row in enumerate(rows,1):
    old=row.get('Current status','')
    limitation=row.get('External blocker / concrete limitation','')
    if 'Not implemented' in old or 'Source implemented; build blocked' in old:status='Open'
    elif 'Windows' in limitation or 'Live ' in limitation:status='Externally blocked'
    elif 'Browser' in limitation or 'visual' in limitation.lower() or 'unverified' in limitation.lower():status='Implemented, verification pending'
    else:status='Implemented, available checks verified'
    # Release acceptance cannot be inferred from helper tests or source-only
    # presence. These entries shared an inconsistent 'verified' status in 0.2.1.
    if row['Legacy behavior'] in ('Built dependency-managed frontend',
                                  'Native browser workflow & accessibility'):
        status='Open'
    compiled.append({'Issue ID':f'MIG-{i:03d}',
      'User-visible consequence':row['Legacy behavior']+' missing or inconsistent',
      'Existing behavior':row['Legacy behavior'],
      'Source owner':row['Existing source owner'],
      'New implementation location':row['New implementation location'],
      'API operation':row['API operation'],
      'UI control or screen':row['UI control or screen'],
      'Required behavior':row['Legacy behavior'],
      'Regression / acceptance evidence':row['Verification / acceptance test'],
      'Status':status,'Concrete blocker / remaining limitation':limitation})
for i,(behavior,impact,owner,required,test,status,limitation) in enumerate(extra,len(compiled)+1):
    compiled.append({'Issue ID':f'MIG-{i:03d}','User-visible consequence':impact,
      'Existing behavior':behavior,'Source owner':owner,
      'New implementation location':owner,'API operation':'See implementation source',
      'UI control or screen':'See implementation source','Required behavior':required,
      'Regression / acceptance evidence':test,'Status':status,
      'Concrete blocker / remaining limitation':limitation})
with (HERE/'PARITY_REGISTER.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields)
    writer.writeheader();writer.writerows(compiled)
print(f'Updated {len(compiled)} individually tracked migration acceptance rows')

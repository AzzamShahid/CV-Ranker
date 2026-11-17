# Windows installation — TextileHR AI modern web checkpoint

**Do not overwrite your working Streamlit installation.** Use a new source directory and a separate local data directory. Python 3.11 is required for the existing Windows project; use Node.js 22.12+ and npm for frontend build. The engineering environment was Linux/Python 3.13.5 and **did not validate native Windows**.

## Prepare and run on a network-connected development workstation

1. Extract the source ZIP into a new folder, such as `C:\TextileHR\WebMigration`.
2. Install 64-bit Python 3.11 and Node 22.12+; ensure `py`, `python`, `node` and `npm` work.
3. From the project directory run `install_web.cmd`. It creates `.venv` and installs the pinned engine and web Python packages.
4. It then enters `frontend` and runs `npm ci` **only if a reviewed package-lock exists**. Because the dependency registry was unavailable during release creation, no lockfile has been falsely fabricated. If missing, installation attempts `npm install --package-lock` to create an authentic lockfile from the configured exact dependencies, followed by `npm run typecheck` and `npm run build`. Review and commit that resolved lockfile before declaring a reproducible production build.
5. Only when the build succeeds will `frontend/dist/index.html` exist. The server returns `503 frontend_build_missing` to UI paths otherwise. Do **not** reuse the removed React16 fallback.
6. Configure provider models/keys in the local environment or securely managed `.env` under existing `cv_ranker` conventions; do not type keys in the browser. Set `TEXTILEHR_DATA_DIR` to an access-restricted local folder outside source if desired.
7. Run `run_web.cmd` and open `http://127.0.0.1:8765/`. A separate worker and API process will start. Use `stop_web.cmd` to stop only this installation's owned processes.
8. `run_web_tests.cmd` runs source integrity, frontend typecheck/route tests/build, web/API tests and the full Python suite. Resolve all dependency/test failures before real applicant deployment.

## Recovery and data handling

Active/unknown-delivery jobs cannot be deleted until reconciled. A paused unknown worker request may have reached a paid provider. Inspect stored checkpoints first; an explicit duplicate-charge acknowledgement is needed to requeue. Completed siblings are retained. For 429, Resume is disabled until the stored `eligible_at` timestamp.

Delete exported ZIPs, unreferenced CVs, terminal jobs or whole workspaces only with confirmation; backup and external copies are not deleted automatically. Stop API/worker before making a plaintext local backup:

```powershell
.\.venv\Scripts\python.exe scripts\data_backup.py backup --data-dir "$env:USERPROFILE\.textilehr-ai-web" --output "$env:USERPROFILE\Desktop\TextileHR-backup.zip"
```

Restore into an empty directory with `scripts\data_backup.py restore --archive ... --destination ...`. Archive is **plaintext**; protect appropriately. The stable Streamlit installation remains your rollback.

**Testing not performed here:** npm install/build, native Windows, live provider runs or real browser screens. Do not treat this guide as a report that those gates passed.


## 0.2.1 specific notes

- `npm test` now runs route, submission-intent and SSE observation tests; `run_web_tests.cmd` also invokes lint. These do not replace real browser validation.
- SQLite migration **3→4** introduces deleted-operation tombstones. Old browser tabs attempting an intentionally deleted submission receive conflict and must start a new independent intent.
- The UI distinguishes weighted projection from primary engine score. Weight changes never rerun source assessments.
- After a provider response is received, cooperative cancellation preserves the finished candidate checkpoint before stopping further scheduling. In-flight calls can still be billable.
- **The frontend bundle is not distributed** because npm dependencies were unavailable in the engineering environment. Do not claim the application is ready until a real lockfile, `npm ci`, typecheck, lint, tests and `npm run build` pass.

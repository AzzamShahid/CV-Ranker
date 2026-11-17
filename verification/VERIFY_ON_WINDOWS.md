# v4.9.66 / v52 native Windows supervisor verification handoff

**Not yet executed on native Windows.** From a NEW extracted release directory (do not overwrite v51):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
.\run_runtime_check.cmd
python -m pytest -q --continue-on-collection-errors
python -m pytest -q tests/test_v4966_current_defects.py tests/test_v4966_operation_ledger.py
python -m evaluation.evaluate_supervisor --output supervisor_original.json
python -m evaluation.evaluate_supervisor --cross-domain --output supervisor_cross_domain.json
.\run_ui.cmd
```

Set model IDs, provider credentials and location only in the private `.env`; never upload them to this release. Startup must verify build `phase7g-v4-9-66-differential-integrity-repair-2026-11-13`, protocol **52**. Test entire Streamlit workflow with fictional JD and two/three fictional resumes, including good/bad/good unreadable candidate; review exact JD, raw citations, candidate Why and criterion Why; record every weight and score/status in UI/CSV/JSON/reviewer ZIP. Test pooled 50 and 90/10→90, 10/90→10 with no model calls on reweight. Verify light/dark high-contrast buttons, narrow viewport, keyboard navigation and original file replacement warnings. Resume after interrupt, provider failure and double-click. Inspect source provenance and ensure no secrets in logs or archive. Test signed recovery tampering, old historical v51 view/rollback and no silently upgraded results. Record actual `pytest` pass/fail/skip/collection numbers and attach sanitized screenshots/logs. **Only after these checks can the Windows qualification gate be marked VERIFIED_WINDOWS.**

# v4.9.67 / protocol v53 — native Windows qualification handoff

This checklist has **not** been executed on Windows by the release engineer. It is an actionable handoff, not a passing certification.

From a NEW extracted v53 directory on Windows 10/11, Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
.\run_runtime_check.cmd
python -m pytest -q --continue-on-collection-errors
python -m pytest -q tests/test_v4967_operation_subset.py tests/test_v4967_differential_oracle.py tests/test_v4967_finalizer_identity.py tests/test_v4967_independent_gold.py
python -m evaluation.evaluate_supervisor --output supervisor_original.json
python -m evaluation.evaluate_supervisor --cross-domain --output supervisor_cross_domain.json
.\run_ui.cmd
```

- Confirm `phase7g-v4-9-67-recovery-oracle-repair-2026-11-14`, protocol 53, and strict source fingerprints. Install configured local Ollama/EmbeddingGemma only when needed; test provider selection and cost/cap controls only with authorization.
- With fictional resumes: upload JD, review entire original JD and nested conditions, freeze, upload 2–3 fictional CVs including a missing/broken file, inspect original S IDs, all four states, candidate and criterion Why, category and per-requirement shares. Reweight without AI calls; compare pooled 50, split 90 and split 10 cases and CSV/JSON/ZIP.
- Resume from a saved partial checkpoint, interrupt before/after SQLite claim, double-click and restart. Verify completed A is not resent when B is new. Do not resend unknown provider delivery automatically.
- Execute the differential verifier with an **independently known** current candidate manifest SHA:

```powershell
$root=(Get-Location).Path
$baseline='C:\path\to\extracted\v4.9.66\CV_Ranker_Supervisor_Edition'
$manifest=(Get-FileHash .\cv_ranker\build_manifest.json -Algorithm SHA256).Hash.ToLower()
python scripts/verify_differential_v4966.py --pair v52_to_v53 --baseline $baseline --candidate $root --candidate-manifest-sha256 $manifest --output local_v52_v53_differential.json
```

The same-tree or reversed-source comparison **must return nonzero**. Independently inspect test outputs and actual UI screenshots; record Python/OS/package versions, pass/fail/skip/collection counts, provider/model identity, each model request/tokens/cost and permission/privacy constraints. Signed recovery archives are integrity-protected, not encrypted. No remote/public deployment until separately accepted security controls.

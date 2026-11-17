# Native Windows and live-provider qualification (NOT EXECUTED HERE)

On a clean Windows 10 workstation with Python 3.11 (use the project’s pinned requirements and operator-authorized keys):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CVR_ACCESS_MODE = 'local'
$env:CVR_STRICT_SOURCE_HASHES = '1'
.\.venv\Scripts\python.exe -m cv_ranker.runtime_check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/test_v4971_deep_audit.py tests/test_v4971_recovery_contracts.py tests/test_v4970_supervisor_three_verdict_e2e.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Check Unicode paths and folders with spaces; frozen JD editing, CV upload, complete/partial evaluation, failed 429 Resume, changed weights, individual Why, CSV/ZIP, process restart, concurrent local ledger use and source identity. Check file permission and Windows atomic replacement behavior with an actual restart or simulated interruption.

Live-model evaluation requires approved Ollama / OpenRouter provider availability, permission to send authorized synthetic test examples and a defined spend cap. Compare the old and new versions with the SAME frozen JD/CV packets/model/time/context. Measure direct Found precision/recall, unsupported positives, incorrect Not Found, Transferable correctness, citation integrity, OR/AND behavior, completion, tokens, model calls, costs, latency, repeated-run variation and 429 recovery. Lock held-out acceptance thresholds **before** evaluating. The scripted regression suite is not a substitute for human-adjudicated independent labels.

The exact historical Windows-compatible baseline with SHA `813f1deb...` is still required for ancestry/fix-parity acceptance. Do not claim that absent archive was integrated.

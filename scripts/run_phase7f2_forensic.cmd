@echo off
setlocal
cd /d "%~dp0.."
call run_runtime_check.cmd || exit /b 2
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" -m pytest -q || exit /b 1
"%PY%" -m scripts.forensic_scope_demo || exit /b 1
"%PY%" -m evaluation.evaluate_industrial --mode fallback --output outputs\phase7f2_fallback.json --markdown outputs\phase7f2_fallback_report.md || exit /b 1
"%PY%" -m evaluation.evaluate_industrial --mode fallback --exact-initialism --output outputs\phase7f2_initialism.json --markdown outputs\phase7f2_initialism_report.md || exit /b 1
exit /b 0

@echo off
setlocal
cd /d "%~dp0.."
call run_runtime_check.cmd || exit /b 2
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m evaluation.evaluate_industrial --mode fallback --exact-initialism --output outputs\phase7f_initialism.json --markdown outputs\phase7f_initialism_report.md
) else (
  python -m evaluation.evaluate_industrial --mode fallback --exact-initialism --output outputs\phase7f_initialism.json --markdown outputs\phase7f_initialism_report.md
)
exit /b %ERRORLEVEL%

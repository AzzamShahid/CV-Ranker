@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m evaluation.compare_industrial --baseline evaluation\results\industrial\phase7e_fallback_baseline.json --current outputs\phase7f_fallback.json --output outputs\phase7f_comparison.json
) else (
  python -m evaluation.compare_industrial --baseline evaluation\results\industrial\phase7e_fallback_baseline.json --current outputs\phase7f_fallback.json --output outputs\phase7f_comparison.json
)
exit /b %ERRORLEVEL%

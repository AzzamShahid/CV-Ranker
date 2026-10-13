@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe was not found.
  exit /b 1
)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check || exit /b 1
REM Run both against the same build and dataset to avoid confounding the comparison.
REM Exit code 3 means mixed/fallback, but the JSON is saved and remains diagnostic.
".venv\Scripts\python.exe" -m evaluation.evaluate_benchmark --scope assessment --batch-size 20 --output outputs\batch_probe_size20.json
set "baseline_rc=%ERRORLEVEL%"
if not "%baseline_rc%"=="0" if not "%baseline_rc%"=="3" exit /b 2
".venv\Scripts\python.exe" -m evaluation.evaluate_benchmark --scope assessment --batch-size 3 --output outputs\batch_probe_size3.json
set "probe_rc=%ERRORLEVEL%"
if not "%probe_rc%"=="0" if not "%probe_rc%"=="3" exit /b 2
".venv\Scripts\python.exe" -m evaluation.compare_batch_runs --baseline outputs\batch_probe_size20.json --probe outputs\batch_probe_size3.json
endlocal

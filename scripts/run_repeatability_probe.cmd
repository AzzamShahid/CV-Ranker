@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found.
  exit /b 1
)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check || exit /b 1
REM 3 paired experiments; production ranker batch size remains unchanged.
REM Use: .\.venv\Scripts\python.exe -m evaluation.repeatability_probe --repeats 2 --output-dir outputs\custom_probe
".venv\Scripts\python.exe" -m evaluation.repeatability_probe --repeats 3 --batch-sizes 20 3 --scope assessment --output-dir outputs\repeatability_probe
endlocal

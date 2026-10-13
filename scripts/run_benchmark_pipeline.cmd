@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe was not found.
  echo Keep or create the project virtual environment before running this benchmark.
  exit /b 1
)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check || exit /b 1
".venv\Scripts\python.exe" -m evaluation.evaluate_benchmark --scope pipeline --output outputs\benchmark_pipeline.json
endlocal

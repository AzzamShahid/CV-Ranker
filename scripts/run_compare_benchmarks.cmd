@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe was not found.
  exit /b 1
)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check || exit /b 1
".venv\Scripts\python.exe" -m evaluation.compare_benchmarks --assessment outputs\benchmark_assessment.json --pipeline outputs\benchmark_pipeline.json --output outputs\benchmark_comparison.json
exit /b %errorlevel%

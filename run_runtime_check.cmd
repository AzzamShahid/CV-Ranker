@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found.
  exit /b 1
)
"%PYTHON%" -m cv_ranker.runtime_check

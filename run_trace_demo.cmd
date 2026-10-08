@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found. Create/install the project virtual environment first.
  exit /b 1
)
"%PYTHON%" trace_demo.py --demo backend --candidate 01_strong.txt

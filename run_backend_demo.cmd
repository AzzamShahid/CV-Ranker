@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found. Create/install the project virtual environment first.
  exit /b 1
)
"%PYTHON%" main.py --jd sample_data/backend_jd.txt --resumes sample_data/backend_resumes --output outputs/backend_demo.json --details

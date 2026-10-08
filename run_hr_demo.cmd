@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found. Create/install the project virtual environment first.
  exit /b 1
)
"%PYTHON%" main.py --jd sample_data/hr_jd.txt --resumes sample_data/hr_resumes --output outputs/hr_demo.json --details

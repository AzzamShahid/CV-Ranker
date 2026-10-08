@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found. Create/install the project virtual environment first.
  exit /b 1
)
"%PYTHON%" -m streamlit run app.py --server.address localhost --server.port 8501

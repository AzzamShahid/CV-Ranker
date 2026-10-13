@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: .venv Python was not found at:
  echo   %PYTHON%
  exit /b 1
)

echo Checking CV Ranker runtime...
"%PYTHON%" -m cv_ranker.runtime_check
if errorlevel 1 (
  echo.
  echo ERROR: Runtime check failed. The project contains mixed/stale files.
  echo Keep .venv, replace the rest of the project with the current package, then retry.
  exit /b 1
)

set "LISTENER_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8501 .*LISTENING"') do set "LISTENER_PID=%%P"
if defined LISTENER_PID (
  echo.
  echo ERROR: Port 8501 is already being used by PID %LISTENER_PID%.
  echo This may be an OLD Streamlit server. Stop that server first ^(Ctrl+C in its terminal^),
  echo then run this launcher again. The launcher will not silently reuse a stale UI process.
  exit /b 1
)

echo.
echo Starting verified CV Ranker build on http://localhost:8501
"%PYTHON%" -m streamlit run app.py --server.address localhost --server.port 8501

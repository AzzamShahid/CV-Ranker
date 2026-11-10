@echo off
setlocal
cd /d "%~dp0.."
call run_runtime_check.cmd || exit /b 2
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m scripts.phase7g_shadow --jd sample_data\backend_jd.txt --resumes sample_data\backend_resumes %*
) else (
  python -m scripts.phase7g_shadow --jd sample_data\backend_jd.txt --resumes sample_data\backend_resumes %*
)
exit /b %ERRORLEVEL%

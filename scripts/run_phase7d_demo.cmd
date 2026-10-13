@echo off
setlocal
cd /d "%~dp0.."
call run_runtime_check.cmd
if errorlevel 1 exit /b %errorlevel%
if exist .venv\Scripts\python.exe (
    set "PYCMD=.venv\Scripts\python.exe"
) else (
    set "PYCMD=python"
)
%PYCMD% main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --output outputs\compound_no_gates.json
if errorlevel 1 exit /b %errorlevel%
%PYCMD% main.py --no-llm --details --jd sample_data\compound_jd.txt --resumes sample_data\compound_resumes --eligibility-policy sample_data\compound_eligibility_policy.EXAMPLE.json --output outputs\compound_with_gates.json
exit /b %errorlevel%

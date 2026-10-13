@echo off
setlocal
cd /d "%~dp0"
call run_runtime_check.cmd || exit /b 1
".venv\Scripts\python.exe" doctor.py --live || exit /b 1
call run_ui.cmd

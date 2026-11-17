@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || exit /b 2
if not exist ".venv\Scripts\python.exe" (echo Run install_web.cmd first.& popd & exit /b 2)
".venv\Scripts\python.exe" "scripts\web_control.py" start
set RET=%ERRORLEVEL%
popd
exit /b %RET%

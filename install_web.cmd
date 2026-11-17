@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || exit /b 2
where py >nul 2>&1 || (echo Python launcher not installed.& popd & exit /b 2)
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv ".venv" || (popd & exit /b 3)
)
echo Installing pinned Python engine and FastAPI dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt" -r "requirements-web.txt"
if errorlevel 1 (echo Dependency installation failed. Check connectivity and pinned versions.& popd & exit /b 4)
echo Building the maintained React and Vite frontend...
where npm >nul 2>&1 || (echo Node.js and npm are required for frontend installation.& popd & exit /b 5)
pushd "frontend" || (popd & exit /b 5)
if exist "package-lock.json" (
    call npm ci --no-audit
) else (
    echo No audited lockfile was distributed due to unavailable dependency registry.
    echo Resolve and review dependency versions and generated package-lock.json before production deployment.
    call npm install --package-lock --no-audit
)
if errorlevel 1 (echo Frontend dependency installation failed.& popd & popd & exit /b 5)
call npm run typecheck
if errorlevel 1 (echo Frontend typecheck failed.& popd & popd & exit /b 5)
call npm run build
if errorlevel 1 (echo Vite production build failed.& popd & popd & exit /b 5)
popd
if not exist "frontend\dist\index.html" (echo Vite did not create frontend assets.& popd & exit /b 5)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check
if errorlevel 1 (echo Source integrity check failed.& popd & exit /b 6)
echo Install succeeded. Use run_web.cmd to start the local worker and API.
popd
exit /b 0

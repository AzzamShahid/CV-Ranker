@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || exit /b 2
if not exist ".venv\Scripts\python.exe" (echo Run install_web.cmd first.& popd & exit /b 2)
".venv\Scripts\python.exe" -m cv_ranker.runtime_check || (popd & exit /b 3)
pushd "frontend"
call npm run typecheck || (popd & popd & exit /b 6)
call npm run lint || (popd & popd & exit /b 6)
call npm run test || (popd & popd & exit /b 6)
call npm run build || (popd & popd & exit /b 6)
popd
".venv\Scripts\python.exe" -m pytest -q tests\web || (popd & exit /b 4)
".venv\Scripts\python.exe" -m pytest -q || (popd & exit /b 5)
echo Full Python verification complete. Browser and native UI acceptance remain separate.
popd
exit /b 0

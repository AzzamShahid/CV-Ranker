@echo off
setlocal
cd /d "%~dp0.."
echo PHASE 7G APPLIED AI DEMO - ranking, decomposition and semantic retrieval
echo Uses the Applied AI JD and all 12 synthetic example resumes.
echo NOTE: live provider calls may take time or cost API credits.
call scripts\run_phase7g_shadow.cmd --decompose --top-k 8
if errorlevel 1 exit /b 2
echo PHASE 7G APPLIED AI DEMO - reviewing functional transferability
call scripts\run_phase7g_transferability.cmd %*
if errorlevel 1 exit /b 2
echo Finished. See outputs\phase7g_shadow\transferability.json
exit /b 0

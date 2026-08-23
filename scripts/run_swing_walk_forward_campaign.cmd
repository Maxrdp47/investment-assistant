@echo off
setlocal
cd /d "%~dp0.."
if not exist "runtime\logs" mkdir "runtime\logs"
".venv\Scripts\python.exe" "scripts\run_swing_walk_forward_campaign.py" >> "runtime\logs\swing_walk_forward_campaign.log" 2>&1
if errorlevel 1 exit /b %errorlevel%
".venv\Scripts\python.exe" "scripts\run_swing_broad_research_supervisor.py" --maximum-assets-per-batch 32 --workers 6 >> "runtime\logs\swing_broad_research.log" 2>&1
exit /b %errorlevel%

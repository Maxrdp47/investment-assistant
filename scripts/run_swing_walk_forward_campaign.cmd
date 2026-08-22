@echo off
setlocal
cd /d "%~dp0.."
if not exist "runtime\logs" mkdir "runtime\logs"
".venv\Scripts\python.exe" "scripts\run_swing_walk_forward_campaign.py" >> "runtime\logs\swing_walk_forward_campaign.log" 2>&1
if errorlevel 1 exit /b %errorlevel%
".venv\Scripts\python.exe" "scripts\run_swing_broad_research.py" --automatic-handoff --maximum-assets 16 --workers 4 >> "runtime\logs\swing_broad_research.log" 2>&1
exit /b %errorlevel%

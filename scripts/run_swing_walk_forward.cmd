@echo off
setlocal
cd /d "%~dp0.."
if not exist "runtime\logs" mkdir "runtime\logs"
".venv\Scripts\python.exe" "scripts\run_swing_walk_forward_locked.py" --start 2016-01-01 --development-end 2021-12-31 --validation-end 2023-12-31 --step-sessions 5 --future-sessions 25 --maximum-cases-per-symbol 12 --batch-size 100 --analysis-workers 4 --analysis-executor threads --profiles current >> "runtime\logs\swing_walk_forward.log" 2>&1
exit /b %errorlevel%

@echo off
setlocal
if "%~1"=="" exit /b 2
cd /d "%~dp0.."
set "swing_scope=%~1"
set "swing_log_dir=%~dp0..\runtime\logs"
set "swing_wrapper_log=%swing_log_dir%\swing_task_wrapper_%swing_scope%.log"
if not exist "%swing_log_dir%" mkdir "%swing_log_dir%"
>> "%swing_wrapper_log%" echo [%date% %time%] START scope=%swing_scope%
"%~dp0..\.venv\Scripts\python.exe" "%~dp0run_swing_scans.py" --scope "%swing_scope%" >> "%swing_wrapper_log%" 2>&1
set "swing_exit=%errorlevel%"
>> "%swing_wrapper_log%" echo [%date% %time%] ENDE scope=%swing_scope% exit=%swing_exit%
exit /b %swing_exit%

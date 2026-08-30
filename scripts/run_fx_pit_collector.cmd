@echo off
setlocal
cd /d "%~dp0.."
set "fx_pit_log_dir=%~dp0..\runtime\logs"
set "fx_pit_log=%fx_pit_log_dir%\fx_pit_collector.log"
if not exist "%fx_pit_log_dir%" mkdir "%fx_pit_log_dir%"
>> "%fx_pit_log%" echo [%date% %time%] START mode=FX_PIT_OBSERVER
"%~dp0..\.venv\Scripts\python.exe" "%~dp0run_fx_pit_collector.py" >> "%fx_pit_log%" 2>&1
set "fx_pit_exit=%errorlevel%"
>> "%fx_pit_log%" echo [%date% %time%] ENDE mode=FX_PIT_OBSERVER exit=%fx_pit_exit%
exit /b %fx_pit_exit%

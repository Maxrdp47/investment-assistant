@echo off
setlocal
cd /d "%~dp0.."
set "forecast_log_dir=%~dp0..\runtime\logs"
set "forecast_wrapper_log=%forecast_log_dir%\forecast_task_wrapper.log"
if not exist "%forecast_log_dir%" mkdir "%forecast_log_dir%"
>> "%forecast_wrapper_log%" echo [%date% %time%] START
"%~dp0..\.venv\Scripts\python.exe" "%~dp0run_forecasts.py" %* >> "%forecast_wrapper_log%" 2>&1
set "forecast_exit=%errorlevel%"
>> "%forecast_wrapper_log%" echo [%date% %time%] ENDE exit=%forecast_exit%
exit /b %forecast_exit%

@echo off
setlocal
cd /d "%~dp0.."
set "evening_log_dir=%~dp0..\runtime\logs"
set "evening_log=%evening_log_dir%\evening_pipeline.log"
if not exist "%evening_log_dir%" mkdir "%evening_log_dir%"

>> "%evening_log%" echo [%date% %time%] START stage=forecasts
call "%~dp0run_forecasts.cmd"
set "forecast_exit=%errorlevel%"
>> "%evening_log%" echo [%date% %time%] ENDE stage=forecasts exit=%forecast_exit%

>> "%evening_log%" echo [%date% %time%] START stage=america_global
call "%~dp0run_swing_scans.cmd" america_global
set "america_exit=%errorlevel%"
>> "%evening_log%" echo [%date% %time%] ENDE stage=america_global exit=%america_exit%

>> "%evening_log%" echo [%date% %time%] START stage=crypto
call "%~dp0run_swing_scans.cmd" crypto
set "crypto_exit=%errorlevel%"
>> "%evening_log%" echo [%date% %time%] ENDE stage=crypto exit=%crypto_exit%

set "pipeline_exit=0"
if not "%forecast_exit%"=="0" set "pipeline_exit=%forecast_exit%"
if "%pipeline_exit%"=="0" if not "%america_exit%"=="0" set "pipeline_exit=%america_exit%"
if "%pipeline_exit%"=="0" if not "%crypto_exit%"=="0" set "pipeline_exit=%crypto_exit%"
>> "%evening_log%" echo [%date% %time%] ENDE pipeline exit=%pipeline_exit%
exit /b %pipeline_exit%

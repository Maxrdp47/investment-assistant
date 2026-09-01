@echo off
setlocal
cd /d "%~dp0.."
if not exist "runtime\logs" mkdir "runtime\logs"
".venv\Scripts\python.exe" "scripts\run_multi_asset_development.py" --run >> "runtime\logs\multi_asset_discovery_v1_development.log" 2>&1
exit /b %errorlevel%

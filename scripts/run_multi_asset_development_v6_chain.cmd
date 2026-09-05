@echo off
setlocal
cd /d C:\investment-assistent
if not exist ".venv\Scripts\python.exe" exit /b 3
".venv\Scripts\python.exe" "scripts\run_multi_asset_development_v6_chain.py" --advance
exit /b %ERRORLEVEL%

@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Die virtuelle Umgebung wurde nicht gefunden.
    echo Erwartet: %~dp0.venv\Scripts\python.exe
    pause
    exit /b 1
)

start "Investment-Assistent Server" /min ".venv\Scripts\python.exe" -m streamlit run "app.py" --server.port=8501

timeout /t 5 /nobreak >nul
start "" "http://localhost:8501"

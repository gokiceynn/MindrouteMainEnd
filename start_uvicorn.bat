@echo off
echo ========================================
echo Starting Uvicorn Server
echo ========================================
echo.

cd /d "%~dp0"
REM Proje kök dizininde kal (app klasörüne girme!)
REM Virtual environment'i aktif et
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
REM Backend'i başlat (proje kök dizininden)
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1

pause

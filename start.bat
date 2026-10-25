@echo off
title InvoicePilot - AP Decision Workbench

echo.
echo  =========================================
echo   InvoicePilot - AP Decision Workbench
echo  =========================================
echo.

:: Set Tesseract OCR path
set "PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR;%PATH%"

:: Move to the project directory
cd /d "%~dp0"

:: Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run:  uv venv .venv  then  uv pip install -r requirements.txt
    pause
    exit /b 1
)

:: Generate fixtures if missing
if not exist "data\fixtures\happy_path_apex_invoice.pdf" (
    echo [INFO] Generating fixtures...
    .venv\Scripts\python.exe scripts\generate_fixtures.py
    .venv\Scripts\python.exe scripts\generate_advanced_fixtures.py
    echo [OK] Fixtures ready.
    echo.
)

:: Kill anything already on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [INFO] Starting server at http://127.0.0.1:8000
echo [INFO] Press Ctrl+C to stop.
echo.

:: Open the browser after a short delay (background)
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"

:: Start the application
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause

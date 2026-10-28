@echo off
title Trading Journal Pro - Quantitative Portfolio Suite
color 0B
cd /d "%~dp0"

echo ===================================================================
echo             * TRADING JOURNAL PRO - LAUNCHER *
echo ===================================================================
echo [1/3] Locating Python environment...

set PYTHON_EXEC=..\.venv\Scripts\python.exe
if not exist "%PYTHON_EXEC%" (
    set PYTHON_EXEC=C:\Users\antho\Maurice_Codes\.venv\Scripts\python.exe
)
if not exist "%PYTHON_EXEC%" (
    set PYTHON_EXEC=python
)

echo [2/3] Verified Python: %PYTHON_EXEC%
echo [3/3] Starting Web Server & Launching Dashboard...
echo.
echo Dashboard URL: http://127.0.0.1:5000
echo Auto-backup and MT5 sync engine loaded.
echo.
echo (Keep this terminal open while using the journal. Press Ctrl+C to stop.)
echo ===================================================================
echo.

:: Auto-open browser after short delay (lets Flask start first)
start "" /min cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

"%PYTHON_EXEC%" main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)


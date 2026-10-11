@echo off
REM ===================================================================
REM  Proxmark3 RFID / NFC Toolkit - GUI launcher (Windows)
REM  Creates a local virtual environment, installs PySide6 and starts
REM  the application. This GUI is a visual mock-up only.
REM ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- choose a Python launcher ---------------------------------------
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYLAUNCH=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYLAUNCH=python"
    ) else (
        echo [ERROR] Python 3 was not found on PATH.
        echo         Install it from https://www.python.org/downloads/
        echo         and make sure "Add Python to PATH" is checked.
        pause
        exit /b 1
    )
)

REM --- create the virtual environment on first run -------------------
if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment ...
    %PYLAUNCH% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

REM --- install / update dependencies --------------------------------
echo [setup] Installing dependencies ...
"%VENV_PY%" -m pip install --upgrade pip >nul 2>nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

REM --- launch the application ----------------------------------------
echo [run] Starting Proxmark3 Toolkit GUI ...
"%VENV_PY%" main.py
if errorlevel 1 pause

endlocal

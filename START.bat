@echo off
setlocal enabledelayedexpansion
title Portable Hermes Agent

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%python_embedded\python.exe"
if not defined HERMES_HOME set "HERMES_HOME=%USERPROFILE%\.hermes"

:: ============================================
::   First-time setup check
:: ============================================
if exist "%PYTHON_EXE%" goto :launch

echo.
echo  ============================================
echo   Portable Hermes Agent - First Time Setup
echo  ============================================
echo.
echo   Welcome! This is your first time running
echo   Hermes Agent. I need to download a few
echo   things to get started:
echo.
echo     - Python 3.13 (portable, stays in this folder)
echo     - AI libraries and dependencies
echo     - LM Studio SDK (for local models)
echo.
echo   This takes about 5-10 minutes on a fast
echo   connection. Nothing is installed system-wide.
echo.
echo   Press any key to begin setup...
pause >nul

call "%SCRIPT_DIR%install.bat"

if not exist "%PYTHON_EXE%" (
    echo.
    echo   Setup failed. Please check your internet
    echo   connection and try again.
    echo.
    pause
    exit /b 1
)

:: ============================================
::   Launch
:: ============================================
:launch
echo.
echo   Starting Hermes Agent...
echo.

:: Check if GUI is available
if exist "%SCRIPT_DIR%gui\app.py" (
    call "%SCRIPT_DIR%hermes_gui.bat" %*
) else (
    call "%SCRIPT_DIR%hermes.bat"
)

endlocal

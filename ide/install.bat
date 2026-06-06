@echo off
:: Cross-platform installation launcher for Windows

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: python is not installed or not on PATH.
    pause
    exit /b 1
)

python "%~dp0\install.py" %*
pause

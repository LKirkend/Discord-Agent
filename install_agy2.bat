@echo off
:: Cross-platform installation launcher for Windows (AGY2 Version)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: python is not installed or not on PATH.
    pause
    exit /b 1
)

python "%~dp0\install_agy2.py" %*
pause

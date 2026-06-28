@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "OUT=%~dp0report.html"

if not exist "%PY%" (
    echo [建立虛擬環境...]
    python -m venv .venv
    call .venv\Scripts\pip install -q -r requirements.txt
)

REM 用法: run_html.bat [TAIEX或台指期價格] [--tx] [--basis 基差]
"%PY%" "%~dp0taiex_to_0050.py" %* --html "%OUT%"
if errorlevel 1 (
    echo 執行失敗
    pause
    exit /b 1
)

echo 已產生: %OUT%
start "" "%OUT%"

endlocal

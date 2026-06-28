@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [建立虛擬環境...]
    python -m venv .venv
    call .venv\Scripts\pip install -q -r requirements.txt
)

echo [更新行情資料...]
"%PY%" "%~dp0scripts\export_data.py" -o "%~dp0docs\data.json"
if errorlevel 1 (
    echo 資料更新失敗，請確認網路連線
    pause
    exit /b 1
)

echo.
echo 啟動本機預覽：http://localhost:8080
echo 請勿直接雙擊 index.html（file:// 無法載入資料）
echo 關閉此命令視窗即可停止伺服器
echo.

start "" "http://localhost:8080"
cd /d "%~dp0docs"
"%PY%" -m http.server 8080

endlocal

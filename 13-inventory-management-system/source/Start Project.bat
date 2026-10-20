@echo off
cd /d "%~dp0frontend"
start "Stockroom API" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0backend\run.ps1"
start "Stockroom Web" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0frontend\run.ps1"
timeout /t 3 >nul
start "" http://127.0.0.1:5185

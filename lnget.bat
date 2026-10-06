@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\lnget.exe (
  echo Chua cai dat. Hay chay setup.bat truoc.
  pause
  exit /b 1
)
.venv\Scripts\lnget.exe %*
if "%~1"=="" pause

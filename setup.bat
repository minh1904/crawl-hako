@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==== Cai dat lnget ====
where py >nul 2>nul
if errorlevel 1 (
  echo [LOI] Chua cai Python. Tai tai https://www.python.org/downloads/ va tick "Add Python to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo Dang tao moi truong .venv ...
  py -3 -m venv .venv || goto :fail
)

echo Dang cai thu vien (lan dau mat 1-3 phut) ...
.venv\Scripts\python -m pip install --upgrade pip -q || goto :fail
.venv\Scripts\python -m pip install -e ".[browser]" -q || goto :fail

echo.
echo Xong! Bam dup:
echo   - lnget-ui.bat  de mo giao dien tren trinh duyet
echo   - lnget.bat     de dung menu trong cua so lenh
pause
exit /b 0

:fail
echo [LOI] Cai dat that bai. Kiem tra mang roi chay lai setup.bat.
pause
exit /b 1

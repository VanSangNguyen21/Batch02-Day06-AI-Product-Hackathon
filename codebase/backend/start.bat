@echo off
REM ============================================================
REM  start.bat - Khoi dong AI Path Backend (Windows)
REM  Su dung: start.bat  hoac  .\start.bat
REM ============================================================
setlocal

REM Chuyen den thu muc chua script nay
cd /d "%~dp0"

REM Dam bao console Windows xuat UTF-8 (hien thi tieng Viet)
chcp 65001 >nul

REM Force UTF-8 cho Python stdout/stderr
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Chay server (hardcoded localhost:8000 trong app/main.py)
echo [start.bat] Khoi dong AI Path Backend tai http://127.0.0.1:8000 ...
python -m app.main

REM Neu loi, hien thi thong bao
if errorlevel 1 (
    echo.
    echo [start.bat] LOI: Kiem tra Python da cai dat chua (python --version)
    pause
)
endlocal

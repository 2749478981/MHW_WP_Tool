@echo off
REM Build MHW_WP_Tool.exe (onefile, windowed) with bundled assets + data.
REM Run this file by double-clicking. Output: dist\MHW_WP_Tool.exe

set PY=C:\Users\x1887\.workbuddy-ai\binaries\python\envs\wp_tool\Scripts\python.exe
if not exist "%PY%" (
    echo [ERROR] venv not found: %PY%
    echo Create it first:  "D:\develop\python314\python.exe" -m venv "%PY%"
    pause
    exit /b 1
)

cd /d "%~dp0"

"%PY%" -m PyInstaller ^
    --noconfirm --clean --onefile --windowed ^
    --name MHW_WP_Tool ^
    --icon "icon\logo.ico" ^
    --version-file "version_info.txt" ^
    --add-data "assets;assets" ^
    --add-data "data;data" ^
    --exclude-module numpy ^
    --exclude-module PIL ^
    --exclude-module openpyxl ^
    --exclude-module pytest ^
    --exclude-module setuptools ^
    main.py

if errorlevel 1 (
    echo.
    echo [FAIL] build failed
    pause
    exit /b 1
)

echo.
echo [OK] dist\MHW_WP_Tool.exe
pause

@echo off
chcp 65001 >nul
title 163MusicConverter - Executable Builder
cd /d "%~dp0"

echo ========================================================
echo  163MusicConverter Standalone Executable Packaging
echo ========================================================
echo.

python build_exe.py

echo.
echo ========================================================
echo  Build process finished. Check dist\163MusicConverter.exe
echo ========================================================
pause

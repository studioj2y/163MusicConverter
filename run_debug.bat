@echo off
setlocal
cd /d "%~dp0"
title CloudMusicConverter (Debug Console)

if exist "C:\Tools\Utilities\Python\python.exe" (
    "C:\Tools\Utilities\Python\python.exe" app.py
    pause
    exit /b %ERRORLEVEL%
)

python app.py
pause

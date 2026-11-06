@echo off
cd /d "%~dp0"

where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw app.py
    exit /b 0
)

if exist "C:\Tools\Utilities\Python\pythonw.exe" (
    start "" "C:\Tools\Utilities\Python\pythonw.exe" app.py
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" python app.py
    exit /b 0
)

if exist "C:\Tools\Utilities\Python\python.exe" (
    start "" "C:\Tools\Utilities\Python\python.exe" app.py
    exit /b 0
)

echo [ERROR] Python not found in system!
pause
exit /b 1

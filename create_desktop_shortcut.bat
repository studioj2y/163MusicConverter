@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$Shortcut = $WshShell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), '网易云音乐VIP解密转换.lnk')); " ^
    "$Shortcut.TargetPath = '%~dp0run.bat'; " ^
    "$Shortcut.WorkingDirectory = '%~dp0'; " ^
    "$Shortcut.IconLocation = '%~dp0app_icon.ico,0'; " ^
    "$Shortcut.Save(); " ^
    "Write-Host '[成功] 已在桌面生成快捷方式: 网易云音乐VIP解密转换.lnk' -ForegroundColor Green"

pause

@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%prepare_miniprogram_package.ps1" %*
exit /b %ERRORLEVEL%

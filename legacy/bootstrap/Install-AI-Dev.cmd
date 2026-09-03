@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0init.ps1"
if errorlevel 1 (
  echo.
  echo Deployment failed. Review deploy.log and press any key to close.
  pause >nul
) else (
  echo.
  echo Deployment finished. Press any key to close.
  pause >nul
)
endlocal

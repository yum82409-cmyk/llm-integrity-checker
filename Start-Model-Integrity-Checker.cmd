@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-Model-Integrity-Checker.ps1"
if errorlevel 1 (
  echo.
  echo Model integrity checker failed to start.
  pause
)
endlocal

@echo off
title SimplyFy - Commit to GitHub - %~dp0
REM Commit (and push) SimplyFy to GitHub. Options: -Message "..." -Paths a,b -NoVerify -NoPush -Deploy -Yes
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Commit-To-GitHub.ps1" %*
if errorlevel 1 (
  echo.
  echo Commit-To-GitHub FAILED - read the error above.
)
pause

@echo off
REM Put the code GitHub has live on sf.valuestream.in: runs deploy.sh on the VPS over ssh.
REM Options: -Server root@host -Key C:\Users\you\.ssh\key
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Deploy-To-VPS.ps1" %*
if errorlevel 1 (
  echo.
  echo Deploy-To-VPS FAILED - read the error above.
)
pause

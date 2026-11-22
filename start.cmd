@echo off
REM SimplyFy (sf.valuestream.in) - Windows. First run installs what it needs into .venv.
REM
REM 2026-09-17: never `call .venv\Scripts\activate.bat`. Python from the Microsoft Store builds a
REM venv with python.exe and pip but NO activate scripts, so activating failed and the portal
REM refused to start on a machine where everything it needs was already installed. Calling the
REM interpreter by its path needs no activation at all, and if the venv is unusable we fall back to
REM the Python on PATH rather than stopping.
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Creating .venv ...
  python -m venv .venv
)
if not exist "%PY%" (
  echo No usable .venv - using the Python on PATH.
  set "PY=python"
)

"%PY%" -c "import fastapi, jsonschema" 2>nul || (
  echo Installing requirements ...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r requirements.txt || goto :fail
)

"%PY%" -c "import fastapi" 2>nul || goto :fail

if "%TV_PORT%"=="" set TV_PORT=8830
if "%PORTAL_COOKIE%"=="" set PORTAL_COOKIE=sf_session
REM 2026-11-22 (DomainTemplate lesson feedback_port_identify_then_next_free): reuse the port only if THIS folder answers
REM /health/run there, else the next free port from TV_PORT (tools\pick_port.py).
set "PICK="
for /f "tokens=1,2" %%a in ('%PY% -I tools\pick_port.py %TV_PORT%') do (set "PICK=%%a" & set "TV_PORT=%%b")
if "%PICK%"=="" goto :fail
set "URL=http://localhost:%TV_PORT%/"
if "%PICK%"=="running" (
  echo.
  echo   SimplyFy is already running  -^>  %URL%
  echo   ^(To stop it, press Ctrl+C in its own window.^)
  echo.
  if not "%TV_NO_BROWSER%"=="1" start "" "%URL%"
  ping -n 6 127.0.0.1 >nul
  goto :eof
)
echo.
echo   SimplyFy  -^>  http://localhost:%TV_PORT%
echo   Stop it with Ctrl+C.
echo.
"%PY%" -m uvicorn app:app --host 0.0.0.0 --port %TV_PORT%
goto :eof

:fail
echo.
echo Could not start. Check that Python 3.11 or newer is installed and on PATH.
exit /b 1

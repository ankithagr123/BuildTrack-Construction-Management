@echo off
setlocal EnableExtensions
set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:5001"
set "STARTUP_LOG=%LOCALAPPDATA%\BuildTrack\logs\startup.log"

title BuildTrack Flask Server and Startup Log
echo ============================================================
echo BuildTrack startup supervisor - visible diagnostic console
echo Project: "%PROJECT_DIR%"
echo URL: %APP_URL%
echo Log: "%STARTUP_LOG%"
echo ============================================================

if not exist "%VENV_PYTHON%" (
  echo ERROR: Existing virtual environment Python was not found:
  echo "%VENV_PYTHON%"
  goto startup_error
)

echo Checking Flask dependencies in the existing virtual environment...
"%VENV_PYTHON%" -c "import flask, werkzeug; from importlib.metadata import version; print('Flask', version('Flask'), '| Werkzeug', version('Werkzeug'))"
if errorlevel 1 (
  echo ERROR: Dependency import failed. Full Python error is shown above.
  goto startup_error
)

echo Checking port 5001 and BuildTrack health before starting Flask...
echo The supervisor will keep this window open and stream Flask stdout/stderr.
echo Press Ctrl+C here to stop the server started by this window.
echo.
"%VENV_PYTHON%" -u -m api.startup_supervisor
set "SUPERVISOR_EXIT=%ERRORLEVEL%"
echo.
echo BuildTrack supervisor stopped with exit code %SUPERVISOR_EXIT%.
echo If startup failed, review the complete log at:
echo "%STARTUP_LOG%"
echo This window will remain open. Press any key to close it.
pause >nul
exit /b %SUPERVISOR_EXIT%

:startup_error
echo.
echo Startup did not complete. Check the error above and:
echo "%STARTUP_LOG%"
echo This window will remain open. Press any key to close it.
pause >nul
exit /b 1

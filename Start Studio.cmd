@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import verovio, defusedxml" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m ensurepip
  .venv\Scripts\python.exe -m pip install -r requirements-studio.txt
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m src.studio.server
if errorlevel 1 goto failed
exit /b 0
:failed
echo Studio could not start. See the error above.
pause

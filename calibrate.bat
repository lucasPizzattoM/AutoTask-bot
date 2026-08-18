@echo off
setlocal
cd /d "%~dp0"

call setup.bat
if errorlevel 1 goto :error

echo.
echo Iniciando calibracao...
".venv\Scripts\python.exe" bot.py --calibrate
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%

:error
echo.
echo Nao foi possivel preparar o ambiente do projeto.
pause
exit /b 1

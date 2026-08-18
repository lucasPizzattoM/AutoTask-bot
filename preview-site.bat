@echo off
setlocal
cd /d "%~dp0"

call setup.bat
if errorlevel 1 goto :error

echo.
echo Abrindo o site demonstrativo...
".venv\Scripts\python.exe" bot.py --site-only
exit /b %ERRORLEVEL%

:error
echo.
echo Nao foi possivel preparar o ambiente do projeto.
pause
exit /b 1

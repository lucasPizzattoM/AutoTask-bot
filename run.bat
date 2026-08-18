@echo off
setlocal
cd /d "%~dp0"

call setup.bat
if errorlevel 1 goto :error

echo.
echo Iniciando AutoTask Bot...
".venv\Scripts\python.exe" bot.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo AutoTask Bot finalizado.
) else (
    echo O programa terminou com o codigo %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%

:error
echo.
echo Nao foi possivel preparar o ambiente do projeto.
pause
exit /b 1

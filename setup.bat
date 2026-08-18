@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :install

echo Procurando uma instalacao do Python...

where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        echo Criando ambiente virtual com o Python Launcher...
        py -3 -m venv .venv
        if not errorlevel 1 goto :install
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python --version >nul 2>&1
    if not errorlevel 1 (
        echo Criando ambiente virtual com o comando python...
        python -m venv .venv
        if not errorlevel 1 goto :install
    )
)

where python3 >nul 2>&1
if not errorlevel 1 (
    python3 --version >nul 2>&1
    if not errorlevel 1 (
        echo Criando ambiente virtual com o comando python3...
        python3 -m venv .venv
        if not errorlevel 1 goto :install
    )
)

echo.
echo Python 3 nao foi encontrado ou nao conseguiu criar o ambiente virtual.
echo Instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH".
echo Depois, execute este arquivo novamente.
exit /b 1

:install
echo Instalando dependencias do projeto...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo Nao foi possivel instalar as dependencias.
    exit /b 1
)

echo Ambiente preparado com sucesso.
exit /b 0

@echo off
title MUG Build System

cd /d "%~dp0"

if not exist VERSION (
    echo.
    echo ERRO: arquivo VERSION nao encontrado na raiz do projeto.
    exit /b 1
)

set /p MUG_VERSION=<VERSION

if "%MUG_VERSION%"=="" (
    echo.
    echo ERRO: arquivo VERSION esta vazio.
    exit /b 1
)

if not exist MUG.spec (
    echo.
    echo ERRO: arquivo MUG.spec nao encontrado.
    echo O build depende de MUG.spec versionado na raiz do projeto.
    exit /b 1
)

echo ==========================================
echo        BUILDING MUG %MUG_VERSION%
echo ==========================================
echo.

echo Limpando builds anteriores...
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if errorlevel 1 (
    echo ERRO: falha ao limpar a pasta build.
    exit /b 1
)

if exist "%~dp0dist" rmdir /s /q "%~dp0dist"
if errorlevel 1 (
    echo ERRO: falha ao limpar a pasta dist.
    exit /b 1
)

echo.
echo Gerando executavel MUG %MUG_VERSION%...
echo.

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -c "import PyInstaller" >nul 2>nul
    if errorlevel 1 (
        echo ERRO: PyInstaller nao esta instalado no ambiente virtual.
        echo Execute: .venv\Scripts\python.exe -m pip install -r requirements.txt
        exit /b 1
    )
    "%PYTHON_EXE%" -m PyInstaller MUG.spec --clean
) else (
    py -3 -c "import PyInstaller" >nul 2>nul
    if not errorlevel 1 (
        py -3 -m PyInstaller MUG.spec --clean
    ) else (
        pyinstaller --version >nul 2>nul
        if errorlevel 1 (
            echo ERRO: PyInstaller nao encontrado.
            echo Instale as dependencias com um Python local ou crie .venv.
            exit /b 1
        )
        pyinstaller MUG.spec --clean
    )
)

if errorlevel 1 (
    echo.
    echo ==========================================
    echo        BUILD FALHOU
    echo ==========================================
    exit /b 1
)

echo.
echo ==========================================
echo       BUILD FINALIZADO COM SUCESSO
echo ==========================================
echo.

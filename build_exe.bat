@echo off
title MUG Build System

cd /d "%~dp0"

set /p MUG_VERSION=<VERSION

echo ==========================================
echo        BUILDING MUG %MUG_VERSION%
echo ==========================================
echo.

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Gerando executavel MUG %MUG_VERSION%...
echo.

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -m PyInstaller MUG.spec --clean
) else (
    pyinstaller MUG.spec --clean
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

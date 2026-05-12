@echo off
title MUG Build System

cd /d "%~dp0"

echo ==========================================
echo        BUILDING MUG v1.3.1
echo ==========================================
echo.

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Gerando executavel MUG v1.3.1...
echo.

pyinstaller MUG.spec --clean

echo.
echo ==========================================
echo       BUILD FINALIZADO COM SUCESSO
echo ==========================================
echo.

pause

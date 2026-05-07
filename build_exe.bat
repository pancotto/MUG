@echo off
title MUG Build System

cd /d "%~dp0"

echo ==========================================
echo        BUILDING MUG v1.2.0
echo ==========================================
echo.

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del /q *.spec 2>nul

echo.
echo Gerando executavel MUG v1.2.0...
echo.

pyinstaller --clean ^
app.py ^
--name MUG ^
--onedir ^
--noconsole ^
--icon "assets\mug.ico" ^
--add-data "assets;assets" ^
--add-data "browser;browser" ^
--add-data "VERSION;."

echo.
echo ==========================================
echo       BUILD FINALIZADO COM SUCESSO
echo ==========================================
echo.

pause
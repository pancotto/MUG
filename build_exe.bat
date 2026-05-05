@echo off
cd /d "%~dp0"

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del /q *.spec 2>nul

echo Gerando executavel MUG...
pyinstaller --clean app.py --name MUG --onedir --noconsole --icon "assets\mug.ico" --add-data "assets;assets"

echo Build concluido.
pause
@echo off
cd /d "%~dp0"

call .venv\Scripts\activate

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name MUG_Desktop ^
  --add-data "assets;assets" ^
  app.py

pause
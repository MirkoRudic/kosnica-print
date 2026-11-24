@echo off
cd /d "%~dp0"
echo Dopuna biblioteka > dopuna.txt
".venv\Scripts\python.exe" -m pip install -r zahtevi.txt --disable-pip-version-check >> dopuna.txt 2>&1
echo. >> dopuna.txt
".venv\Scripts\python.exe" -c "import fitz, pillow_heif; print('PDF i HEIC rade')" >> dopuna.txt 2>&1
echo. >> dopuna.txt
echo GOTOVO >> dopuna.txt

@echo off
cd /d "%~dp0"
echo Sirovi DEVMODE > sirovi.txt
".venv\Scripts\python.exe" sirovi_devmode.py >> sirovi.txt 2>&1
echo. >> sirovi.txt
echo GOTOVO >> sirovi.txt

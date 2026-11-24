@echo off
cd /d "%~dp0"
echo Ispitivanje drajvera > papiri.txt
".venv\Scripts\python.exe" papiri.py >> papiri.txt 2>&1
echo. >> papiri.txt
echo GOTOVO >> papiri.txt

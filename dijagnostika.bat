@echo off
cd /d "%~dp0"
echo Izvidjanje Windows stampe > dijagnostika.txt
echo. >> dijagnostika.txt
".venv\Scripts\python.exe" -m pip install pywin32 --disable-pip-version-check >> dijagnostika.txt 2>&1
".venv\Scripts\python.exe" dijagnostika.py >> dijagnostika.txt 2>&1
echo. >> dijagnostika.txt
echo GOTOVO >> dijagnostika.txt

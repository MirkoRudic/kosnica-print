@echo off
cd /d "%~dp0"
echo Proba papira > proba_papira.txt
".venv\Scripts\python.exe" proba_papira.py >> proba_papira.txt 2>&1
echo. >> proba_papira.txt
echo GOTOVO >> proba_papira.txt

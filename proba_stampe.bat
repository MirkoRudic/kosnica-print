@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" proba_stampe.py > proba_stampe.txt 2>&1
echo GOTOVO >> proba_stampe.txt

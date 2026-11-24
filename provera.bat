@echo off
cd /d "%~dp0"
echo Provera novih ruta > provera.txt
".venv\Scripts\python.exe" provera.py >> provera.txt 2>&1
echo. >> provera.txt
echo GOTOVO >> provera.txt

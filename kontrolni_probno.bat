@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" stampaj_kontrolni.py --probno > kontrolni.txt 2>&1
echo GOTOVO >> kontrolni.txt

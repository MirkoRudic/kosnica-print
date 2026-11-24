@echo off
cd /d "%~dp0"
echo Zaustavljam aplikaciju... > osvezi.txt
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*PripremaMagneta*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> osvezi.txt 2>&1
ping -n 4 127.0.0.1 >nul
echo Pokrecem ponovo... >> osvezi.txt
wscript "%~dp0PripremaMagneta.vbs"
ping -n 12 127.0.0.1 >nul
echo. >> osvezi.txt
echo --- provera servera --- >> osvezi.txt
".venv\Scripts\python.exe" osvezi.py >> osvezi.txt 2>&1
echo. >> osvezi.txt
echo GOTOVO >> osvezi.txt

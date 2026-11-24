@echo off
cd /d "%~dp0"
echo Zaustavljam aplikaciju...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*PripremaMagneta*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul
ping -n 3 127.0.0.1 >nul
echo Pokrecem ponovo...
wscript "%~dp0PripremaMagneta.vbs"

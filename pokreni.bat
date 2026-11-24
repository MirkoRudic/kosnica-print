@echo off
setlocal
cd /d "%~dp0"
title Priprema magneta

set "PYEXE="
set "PYURL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
set "INST=%TEMP%\python-3.12.7-amd64.exe"

rem ---------------------------------------------------------------
rem 1. Da li vec postoji upotrebljiv Python?
rem    Paznja: "where python" nalazi i Microsoft Store precicu koja
rem    ne radi, pa se mora probati stvarno pokretanje.
rem ---------------------------------------------------------------
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 goto :preko_py

python -c "import sys" >nul 2>nul
if not errorlevel 1 goto :preko_python

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  goto :imamo
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  goto :imamo
)
goto :instaliraj

:preko_py
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)"') do set "PYEXE=%%P"
goto :imamo

:preko_python
for /f "delims=" %%P in ('python -c "import sys;print(sys.executable)"') do set "PYEXE=%%P"
goto :imamo

rem ---------------------------------------------------------------
rem 2. Nema ga - skini zvanicni instalater i instaliraj za korisnika
rem    (bez administratorskih prava).
rem ---------------------------------------------------------------
:instaliraj
echo.
echo Python nije nadjen na ovom racunaru.
echo Skidam zvanicni instalater sa python.org, oko 25 MB...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYURL%' -OutFile '%INST%'"
if not exist "%INST%" (
  echo Skidanje nije uspelo. Proveri internet vezu.
  goto :greska
)

echo Instaliram Python. Traje oko minut.
"%INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYEXE%" (
  echo Instalacija Pythona nije uspela.
  goto :greska
)
del "%INST%" >nul 2>nul

rem ---------------------------------------------------------------
rem 3. Okruzenje i biblioteke
rem ---------------------------------------------------------------
:imamo
echo Python: %PYEXE%
"%PYEXE%" --version

if not exist ".venv\Scripts\python.exe" (
  echo Pravim okruzenje...
  "%PYEXE%" -m venv .venv
  if errorlevel 1 goto :greska
)

".venv\Scripts\python.exe" -c "import flask, PIL, numpy, reportlab" >nul 2>nul
if not errorlevel 1 goto :pokreni

echo Skidam biblioteke, prvi put traje minut-dva...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r zahtevi.txt
if errorlevel 1 goto :greska

rem ---------------------------------------------------------------
rem 4. Pokretanje
rem ---------------------------------------------------------------
:pokreni
echo.
echo ================================================
echo  Pokrecem. Pregledac se otvara sam.
echo  Ako se ne otvori: http://127.0.0.1:8733
echo  Za gasenje zatvori ovaj prozor.
echo ================================================
echo.
".venv\Scripts\python.exe" server.py
goto :kraj

:greska
echo.
echo ------------------------------------------------
echo  NESTO NIJE PROSLO. Poruka je iznad.
echo ------------------------------------------------
pause

:kraj
endlocal

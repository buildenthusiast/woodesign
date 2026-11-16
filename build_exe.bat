@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PY="

REM 1) py launcher, python, python3 (proverka che naistina raboti)
for %%C in ("py -3" "python" "python3") do (
  if not defined PY (
    %%~C -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
REM 2) standartni papki za instalaciya
if not defined PY (
  for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*" "C:\Python3*") do (
    if not defined PY if exist "%%~D\python.exe" set "PY="%%~D\python.exe""
  )
)
if not defined PY (
  echo.
  echo Python ne e nameren.
  echo Instalirajte Python 3.10+ ot https://www.python.org/downloads/
  echo i otmetnete "Add python.exe to PATH" v parviya ekran na instalatora.
  pause
  exit /b 1
)
echo Izpolzvam Python: !PY!
!PY! -m pip install --upgrade pip
!PY! -m pip install -r requirements.txt || (echo Greshka pri instalirane na bibliotekite & pause & exit /b 1)
!PY! -m PyInstaller --noconfirm --onefile --windowed --name MebelDesigner --add-data "mebel\fonts;mebel\fonts" main.py || (echo Greshka pri kompilirane & pause & exit /b 1)
echo.
echo GOTOVO! Programata e v: %~dp0dist\MebelDesigner.exe
start "" "%~dp0dist"
pause

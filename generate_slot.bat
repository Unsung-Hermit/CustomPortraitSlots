@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: generate_slot.bat ^<Id^> -Sex Female^|Male^|Nonbinary [-Force] [-OutDir path]
  echo Example: generate_slot.bat My_Ace_01 -Sex Female
  exit /b 1
)

if exist "Tools\generate_slot.exe" (
  "Tools\generate_slot.exe" %*
  set "RC=%ERRORLEVEL%"
  goto end
)

python "Tools\generate_slot.py" %*
set "RC=%ERRORLEVEL%"

:end
exit /b %RC%

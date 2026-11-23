@echo off
setlocal
cd /d "%~dp0"
set "RC=1"

if exist "Tools\merge_slots.exe" (
  "Tools\merge_slots.exe"
  set "RC=%ERRORLEVEL%"
  goto end
)

if exist "Tools\merge_slots.py" (
  python "Tools\merge_slots.py"
  set "RC=%ERRORLEVEL%"
  goto end
)

echo ERROR: Tools\merge_slots.exe / merge_slots.py not found.
set "RC=1"

:end
echo.
pause
exit /b %RC%

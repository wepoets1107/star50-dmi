@echo off
chcp 65001 >nul
setlocal

set "PORT=5059"
set "PY="

rem --- locate pythonw.exe (prefer 3.13.12, fall back to any version) ---
set "CAND=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
if exist "%CAND%" (
  set "PY=%CAND%"
) else (
  for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
    if exist "%%D\pythonw.exe" set "PY=%%D\pythonw.exe"
  )
)

if not defined PY (
  echo [ERROR] pythonw.exe not found under %%USERPROFILE%%\.workbuddy\binaries\python\versions
  pause
  exit /b 1
)

rem --- port guard: skip if already listening ---
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo [INFO] Port %PORT% already in use - service appears to be running.
  start "" "http://localhost:%PORT%"
  exit /b 0
)

echo [OK] Starting DMI dashboard with:
echo      %PY%
start "" "%PY%" "%~dp0server.py"

timeout /t 3 /nobreak >nul
start "" "http://localhost:%PORT%"
exit /b 0

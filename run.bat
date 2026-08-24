@echo off
setlocal
pushd "%~dp0"
python "%~dp0main.py"
set "AGM_RC=%ERRORLEVEL%"
if not "%AGM_RC%"=="0" (
  echo.
  echo Arcade Game Manager failed. See:
  echo   %~dp0data\logs\manager.log
  pause
)
popd
exit /b %AGM_RC%

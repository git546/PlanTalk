@echo off
setlocal
cd /d "%~dp0\..\.."
python -m lab.water_calculator.app
if errorlevel 1 (
  echo.
  echo Failed to start the water calculator lab.
  echo Check that Python is installed and available as "python".
  pause
)

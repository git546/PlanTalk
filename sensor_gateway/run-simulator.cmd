@echo off
setlocal
cd /d "%~dp0\.."
python -m sensor_gateway run --adapter simulator --count 120
echo.
python -m sensor_gateway status
pause


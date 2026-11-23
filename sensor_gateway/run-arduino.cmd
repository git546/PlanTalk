@echo off
setlocal
cd /d "%~dp0\.."

if "%~1"=="" (
  echo Usage: sensor_gateway\run-arduino.cmd COM3
  echo Find the port with: python -m sensor_gateway ports
  exit /b 2
)

python -m sensor_gateway run --adapter serial --port "%~1" --baud 9600

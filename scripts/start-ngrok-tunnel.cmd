@echo off
REM Starts an ngrok tunnel to the local WebhookReceiver (port 5088).
REM Prerequisite: WebhookReceiver (EXE or python) already on http://127.0.0.1:5088
REM
REM Usage:
REM   scripts\start-ngrok-tunnel.cmd

where ngrok >nul 2>&1
if errorlevel 1 (
  echo ngrok not found on PATH. Install: choco install ngrok
  echo Then: ngrok config add-authtoken YOUR_TOKEN
  exit /b 1
)

echo Starting ngrok http tunnel to http://127.0.0.1:5088 ...
echo Web UI / status: http://127.0.0.1:4040
echo.
ngrok http 127.0.0.1:5088 --log=stdout

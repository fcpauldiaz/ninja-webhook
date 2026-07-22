@echo off
REM Starts a Cloudflare quick tunnel to the local WebhookReceiver (port 5088).
REM Prerequisite: Python webhook_receiver already running on http://127.0.0.1:5088
REM
REM Usage:
REM   scripts\start-cloudflare-tunnel.cmd

set EXE=%~dp0..\tools\cloudflared.exe
if not exist "%EXE%" (
  echo cloudflared.exe not found at tools\cloudflared.exe
  echo Download: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
  exit /b 1
)

echo Starting Cloudflare quick tunnel to http://127.0.0.1:5088 ...
echo Make sure: cd webhook_receiver ^&^& python main.py
echo Watch this window for the https://....trycloudflare.com URL
echo.
"%EXE%" tunnel --url http://127.0.0.1:5088 --no-autoupdate

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'Install FFmpeg with libass and add it to PATH.' }
py -3 -m venv .venv
& .venv\Scripts\python.exe -m pip install -r requirements.txt
& .venv\Scripts\python.exe scripts\configure.py
Write-Host 'Start with: .venv\Scripts\python.exe scripts\run_bridge.py'

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$bundledPython = 'C:\Users\bhara\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path '.venv')) { & $bundledPython -m venv .venv; & .\.venv\Scripts\python.exe -m pip install -r requirements.txt }
& .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8013

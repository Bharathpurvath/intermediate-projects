$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$python = Join-Path $backend '.venv\Scripts\python.exe'
$api = Start-Process -PassThru -FilePath $python -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port','8004') -WorkingDirectory $backend -RedirectStandardOutput (Join-Path $logs 'backend.log') -RedirectStandardError (Join-Path $logs 'backend-error.log') -WindowStyle Hidden
$web = Start-Process -PassThru -FilePath $env:ComSpec -ArgumentList @('/d','/s','/c','npm run dev') -WorkingDirectory $frontend -RedirectStandardOutput (Join-Path $logs 'frontend.log') -RedirectStandardError (Join-Path $logs 'frontend-error.log') -WindowStyle Hidden
@{ backend = $api.Id; frontend = $web.Id } | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $logs 'processes.json')
Start-Sleep -Seconds 3
Start-Process 'http://localhost:5177'
Write-Host 'Bugboard is starting at http://localhost:5177'

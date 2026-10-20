$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root 'logs\processes.json'
if (Test-Path $pidFile) {
  $ids = Get-Content $pidFile -Raw | ConvertFrom-Json
  foreach ($id in @($ids.backend, $ids.frontend)) { & taskkill.exe /PID ([int]$id) /T /F 2>$null | Out-Null }
  Remove-Item $pidFile -Force
}
Write-Host 'People Ops servers stopped.'

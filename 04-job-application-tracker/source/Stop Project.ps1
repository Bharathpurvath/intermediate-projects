$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root 'logs\processes.json'
if (Test-Path $pidFile) {
  $ids = Get-Content $pidFile -Raw | ConvertFrom-Json
  foreach ($id in @($ids.backend, $ids.frontend)) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
  Remove-Item $pidFile -Force
}
Write-Host 'Next Chapter servers stopped.'

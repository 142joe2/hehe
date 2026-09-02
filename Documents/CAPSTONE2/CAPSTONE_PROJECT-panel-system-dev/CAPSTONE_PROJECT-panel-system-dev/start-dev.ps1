param(
  [int]$Port = 8000,
  [switch]$NoMigrate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CAUFA Portal — DEV Server (runserver)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any server already bound to the target port (avoids "port in use")
try {
  $procs = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
  if ($procs) {
    Write-Host "[*] Freeing port $Port..." -ForegroundColor Yellow
    $procs.OwningProcess | Sort-Object -Unique | ForEach-Object {
      Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
  }
} catch { }

Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VenvActivate) {
  . $VenvActivate
  Write-Host "  -> Virtual env activated." -ForegroundColor Green
} else {
  Write-Host "  -> Virtual env not found at $VenvActivate" -ForegroundColor Red
  exit 1
}

if (-not $NoMigrate) {
  Write-Host "[2/3] Applying database migrations..." -ForegroundColor Yellow
  & $VenvPython "$ProjectRoot\manage.py" migrate 2>&1
  if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> Migrations applied." -ForegroundColor Green
  } else {
    Write-Host "  -> Migration failed. Check errors above." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "[2/3] Skipping migrations (-NoMigrate)." -ForegroundColor Gray
}

Write-Host "[3/3] Starting Django runserver (django-browser-reload active)..." -ForegroundColor Yellow
Write-Host "  -> Edits to .html/.js/.css/.py refresh the browser automatically." -ForegroundColor Gray
Write-Host "  -> Ctrl+C to stop." -ForegroundColor Gray
& $VenvPython "$ProjectRoot\manage.py" runserver "127.0.0.1:$Port" --noreload=0

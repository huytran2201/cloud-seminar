# start_demo.ps1 - Build monitoring services, then run the interactive demonstration.
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "AIOps & Cloud Monitoring Demo - Interactive Runner" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "[1/2] Building services and opening monitoring tabs..." -ForegroundColor Yellow

$buildScript = Join-Path $PSScriptRoot 'build.ps1'
$powerShellExe = Join-Path $PSHOME 'powershell.exe'
& $powerShellExe -NoProfile -ExecutionPolicy Bypass -File $buildScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build or service startup failed." -ForegroundColor Red
    Read-Host "Press [Enter] to exit"
    exit $LASTEXITCODE
}
# 2. Launch interactive demo
Write-Host ""
Write-Host "STARTING SRE DEMONSTRATION WORKFLOW:" -ForegroundColor Cyan
$pythonCommand = $null
$pythonArguments = @()
$pythonCandidates = @(
    @{ Command = (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"); Arguments = @() },
    @{ Command = "py"; Arguments = @("-3.13") },
    @{ Command = "py"; Arguments = @() },
    @{ Command = "python"; Arguments = @() }
)

foreach ($candidate in $pythonCandidates) {
    if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
        continue
    }
    $checkArguments = @($candidate.Arguments) + @("-c", "import requests")
    $null = & $candidate.Command @checkArguments 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonCommand = $candidate.Command
        $pythonArguments = @($candidate.Arguments)
        break
    }
}

if (-not $pythonCommand) {
    Write-Host "[ERROR] No Python interpreter with the 'requests' package was found." -ForegroundColor Red
    Write-Host "Install requests in your Python 3.10+ environment, then run this script again." -ForegroundColor Yellow
    Write-Host "Example: py -m pip install requests" -ForegroundColor Yellow
    Read-Host "Press [Enter] to exit"
    exit 1
}

Write-Host "  [INFO] Running demo with $pythonCommand $($pythonArguments -join ' ')" -ForegroundColor Cyan
& $pythonCommand @pythonArguments run_demo.py --interactive

# 3. Cleanup prompt
Write-Host ""
$choice = Read-Host "Do you want to stop the Docker containers now? (y/n, default: n)"
if ($choice -eq "y" -or $choice -eq "Y") {
    Write-Host "Stopping containers..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "[OK] All services stopped safely." -ForegroundColor Green
} else {
    Write-Host "Containers remain running in background at http://localhost:3000" -ForegroundColor Cyan
    Write-Host "To stop them later, run: docker-compose down" -ForegroundColor DarkGray
}

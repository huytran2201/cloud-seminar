# ========================================================================
# start_demo.ps1 - 1-Click Master Runner for AIOps Cloud Demo
# Workflow: Verify Docker -> Start Containers -> Wait Healthy -> Open Monitoring Pages -> Run Demo
# ========================================================================
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "AIOps & Cloud Monitoring Demo - 1-Click Master Runner" -ForegroundColor Cyan
Write-Host "Workflow: Docker Services -> Monitoring Pages -> Interactive Demo" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Docker
Write-Host "[1/4] Checking Docker daemon status..." -ForegroundColor Yellow
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker is not running or not installed!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop, wait for it to run, then re-execute this script." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press [Enter] to exit"
    exit 1
}

Write-Host "  [OK] Docker engine is running." -ForegroundColor Green

# 2. Launch 4 Microservices via Docker Compose
Write-Host ""
Write-Host "[2/4] Starting 6 services (App, AI Detector, Prometheus, Alertmanager, Receiver, Grafana)..." -ForegroundColor Yellow
docker-compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start docker-compose!" -ForegroundColor Red
    Read-Host "Press [Enter] to exit"
    exit 1
}

$receiverBinding = docker-compose port alert-receiver 8081
if ($LASTEXITCODE -ne 0 -or -not $receiverBinding) {
    Write-Host "[ERROR] Could not determine the Alert Receiver host port." -ForegroundColor Red
    Read-Host "Press [Enter] to exit"
    exit 1
}
$receiverPort = ($receiverBinding.Trim() -split ":")[-1]
$receiverUrl = "http://localhost:$receiverPort"
Write-Host "  [INFO] Alert Receiver is available at $receiverUrl" -ForegroundColor Cyan

# 3. Wait for services healthy
Write-Host ""
Write-Host "[3/4] Waiting for services to become healthy..." -ForegroundColor Yellow
$healthChecks = @(
    @{ Name = "Application"; Url = "http://localhost:8000/health" },
    @{ Name = "Prometheus"; Url = "http://localhost:9090/-/healthy" },
    @{ Name = "AI Detector"; Url = "http://localhost:8001/health" },
    @{ Name = "Alertmanager"; Url = "http://localhost:9093/-/healthy" },
    @{ Name = "Alert Receiver"; Url = "$receiverUrl/health" },
    @{ Name = "Grafana"; Url = "http://localhost:3000/api/health" }
)
$healthDeadline = [DateTime]::UtcNow.AddSeconds(45)
try {
    Add-Type -AssemblyName System.Net.Http -ErrorAction Stop
    $httpClient = [System.Net.Http.HttpClient]::new()
    $httpClient.Timeout = [TimeSpan]::FromSeconds(3)
} catch {
    Write-Host "[ERROR] Could not initialize the HTTP health checker: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press [Enter] to exit"
    exit 1
}
$ready = $false
$unhealthyServices = @()

$retryDelayMs = 1000
while ([DateTime]::UtcNow -lt $healthDeadline) {
    $roundTasks = @(
        foreach ($check in $healthChecks) {
            $httpClient.GetAsync($check.Url)
        }
    )

    try { [void][System.Threading.Tasks.Task]::WaitAll([System.Threading.Tasks.Task[]]$roundTasks, 3000) } catch {}

    $unhealthyServices = @()
    for ($i = 0; $i -lt $healthChecks.Count; $i++) {
        $task = $roundTasks[$i]
        if ($task.Status -eq [System.Threading.Tasks.TaskStatus]::RanToCompletion) {
            $response = $task.Result
            if (-not $response.IsSuccessStatusCode) {
                $unhealthyServices += "$($healthChecks[$i].Name) (HTTP $([int]$response.StatusCode))"
            }
            $response.Dispose()
        } else {
            $unhealthyServices += $healthChecks[$i].Name
        }
    }

    if ($unhealthyServices.Count -eq 0) {
        $ready = $true
        break
    }

    Write-Host -NoNewline "." -ForegroundColor DarkGray
    Start-Sleep -Milliseconds $retryDelayMs
}
$httpClient.Dispose()
Write-Host ""

if ($ready) {
    Write-Host "  [OK] Application, monitoring and alerting services are healthy." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Still waiting on: $($unhealthyServices -join ', '). Proceeding anyway..." -ForegroundColor Yellow
}

# 4. Open monitoring pages
Write-Host ""
Write-Host "[4/4] Opening monitoring pages in your default browser..." -ForegroundColor Green
Write-Host "  Grafana:        http://localhost:3000"
Write-Host "  Prometheus:     http://localhost:9090/alerts"
Write-Host "  Alertmanager:   http://localhost:9093/#/alerts"
Write-Host "  Alert Receiver: $receiverUrl"
Start-Process "http://localhost:3000"
Start-Process "http://localhost:9090/alerts"
Start-Process "http://localhost:9093/#/alerts"
Start-Process $receiverUrl
Start-Sleep -Seconds 2

# 5. Launch interactive demo
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

# 6. Cleanup prompt
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

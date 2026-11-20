# Build and start the monitoring stack, wait for its web services, then open dashboards.
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "AIOps Cloud Monitoring - Build and Open Dashboards" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

Write-Host "[1/3] Checking Docker daemon..." -ForegroundColor Yellow
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Desktop is not running. Start it, then run build.bat again." -ForegroundColor Red
    exit 1
}

Write-Host "[2/3] Building and starting services..." -ForegroundColor Yellow
docker-compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose failed to build or start the services." -ForegroundColor Red
    exit 1
}

$receiverBinding = docker-compose port alert-receiver 8081
if ($LASTEXITCODE -ne 0 -or -not $receiverBinding) {
    Write-Host "[ERROR] Could not determine the Alert Receiver host port." -ForegroundColor Red
    exit 1
}
$receiverPort = ($receiverBinding.Trim() -split ":")[-1]
$receiverUrl = "http://localhost:$receiverPort"

Write-Host "[3/3] Waiting for services, then opening monitoring pages..." -ForegroundColor Yellow
$healthChecks = @(
    @{ Name = "Application"; Url = "http://localhost:8000/health" },
    @{ Name = "Prometheus"; Url = "http://localhost:9090/-/healthy" },
    @{ Name = "AI Detector"; Url = "http://localhost:8001/health" },
    @{ Name = "Alertmanager"; Url = "http://localhost:9093/-/healthy" },
    @{ Name = "Alert Receiver"; Url = "$receiverUrl/health" },
    @{ Name = "Grafana"; Url = "http://localhost:3000/api/health" }
)
$healthDeadline = [DateTime]::UtcNow.AddSeconds(60)
Add-Type -AssemblyName System.Net.Http -ErrorAction Stop
$httpClient = [System.Net.Http.HttpClient]::new()
$httpClient.Timeout = [TimeSpan]::FromSeconds(3)
$ready = $false
$unhealthyServices = @()

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
    Start-Sleep -Seconds 1
}
$httpClient.Dispose()
Write-Host ""

if ($ready) {
    Write-Host "[OK] All application and monitoring services are healthy." -ForegroundColor Green
} else {
    Write-Host "[WARN] Timed out waiting for: $($unhealthyServices -join ', '). Opening pages anyway." -ForegroundColor Yellow
}

Write-Host "Grafana:        http://localhost:3000" -ForegroundColor Cyan
Write-Host "Prometheus:     http://localhost:9090/alerts" -ForegroundColor Cyan
Write-Host "Alertmanager:   http://localhost:9093/#/alerts" -ForegroundColor Cyan
Write-Host "Alert Receiver: $receiverUrl" -ForegroundColor Cyan
Start-Process "http://localhost:3000"
Start-Process "http://localhost:9090/alerts"
Start-Process "http://localhost:9093/#/alerts"
Start-Process $receiverUrl

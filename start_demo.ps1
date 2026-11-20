# ========================================================================
# start_demo.ps1 - 1-Click Master Runner for AIOps Cloud Demo
# Workflow: Verify Docker -> Start Containers -> Wait Healthy -> Open Grafana -> Run Demo
# ========================================================================
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "AIOps & Cloud Monitoring Demo - 1-Click Master Runner" -ForegroundColor Cyan
Write-Host "Workflow: Docker Services -> Open Grafana Browser -> Interactive Demo" -ForegroundColor Cyan
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

# 3. Wait for services healthy
Write-Host ""
Write-Host "[3/4] Waiting for services to become healthy..." -ForegroundColor Yellow
$maxRetries = 25
$ready = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $appResp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        $promResp = Invoke-WebRequest -Uri "http://localhost:9090/-/healthy" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        $aiResp = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        $alertmanagerResp = Invoke-WebRequest -Uri "http://localhost:9093/-/healthy" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        $receiverResp = Invoke-WebRequest -Uri "http://localhost:8081/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        
        if ($appResp.StatusCode -eq 200 -and $promResp.StatusCode -eq 200 -and $aiResp.StatusCode -eq 200 -and $alertmanagerResp.StatusCode -eq 200 -and $receiverResp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
    Write-Host -NoNewline "." -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
}
Write-Host ""

if ($ready) {
    Write-Host "  [OK] Application, monitoring and alerting services are healthy." -ForegroundColor Green
} else {
    Write-Host "  [WARN] Proceeding with connection..." -ForegroundColor Yellow
}

# 4. Open Grafana Dashboard
Write-Host ""
Write-Host "[4/4] Opening Grafana Dashboard in browser (http://localhost:3000)..." -ForegroundColor Green
Start-Process "http://localhost:3000"
Start-Process "http://localhost:8081"
Start-Sleep -Seconds 2

# 5. Launch interactive demo
Write-Host ""
Write-Host "STARTING SRE DEMONSTRATION WORKFLOW:" -ForegroundColor Cyan
python run_demo.py --interactive

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

# Setup HerbGPT as Windows Service using NSSM
# This script must be run as Administrator

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again."
    pause
    exit 1
}

# Configuration
$serviceName = "HerbGPT"
$nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
$pythonPath = (Get-Command python).Source
$scriptPath = "c:\Herb Project\LM-Open-Rag\main.py"
$workingDir = "c:\Herb Project\LM-Open-Rag"

Write-Host "Setting up HerbGPT Windows Service..." -ForegroundColor Cyan

# Remove existing service if it exists
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Removing existing service..." -ForegroundColor Yellow
    & $nssmPath stop $serviceName
    & $nssmPath remove $serviceName confirm
    Start-Sleep -Seconds 2
}

# Install service
Write-Host "Installing service..." -ForegroundColor Green
& $nssmPath install $serviceName $pythonPath "`"$scriptPath`""

# Set working directory
Write-Host "Configuring service..." -ForegroundColor Green
& $nssmPath set $serviceName AppDirectory "`"$workingDir`""

# Set environment variables
& $nssmPath set $serviceName AppEnvironmentExtra OLLAMA_EMBEDDING_MODEL=mxbai-embed-large OLLAMA_BASE_URL=http://localhost:11434

# Set to restart on failure
& $nssmPath set $serviceName AppExit Default Restart
& $nssmPath set $serviceName AppRestartDelay 5000

# Set startup type to automatic
& $nssmPath set $serviceName Start SERVICE_AUTO_START

# Set log files
& $nssmPath set $serviceName AppStdout "`"$workingDir\logs\service-output.log`""
& $nssmPath set $serviceName AppStderr "`"$workingDir\logs\service-error.log`""

# Rotate logs
& $nssmPath set $serviceName AppStdoutCreationDisposition 4
& $nssmPath set $serviceName AppStderrCreationDisposition 4

# Start service
Write-Host "Starting service..." -ForegroundColor Green
& $nssmPath start $serviceName

# Wait a moment
Start-Sleep -Seconds 3

# Check status
$status = & $nssmPath status $serviceName
Write-Host ""
Write-Host "Service Status: $status" -ForegroundColor Cyan

if ($status -like "*RUNNING*") {
    Write-Host ""
    Write-Host "SUCCESS! HerbGPT service is now running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The service will:" -ForegroundColor Yellow
    Write-Host "  - Start automatically when Windows boots"
    Write-Host "  - Restart automatically if it crashes"
    Write-Host "  - Run in the background even when you're not logged in"
    Write-Host ""
    Write-Host "Access your app at: http://localhost:8010" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Yellow
    Write-Host "  View logs:     Get-Content '$workingDir\logs\service-output.log' -Tail 50 -Wait"
    Write-Host "  Stop service:  & '$nssmPath' stop $serviceName"
    Write-Host "  Start service: & '$nssmPath' start $serviceName"
    Write-Host "  Service GUI:   services.msc"
} else {
    Write-Host ""
    Write-Host "WARNING: Service may not have started correctly." -ForegroundColor Red
    Write-Host "Check logs at: $workingDir\logs\service-error.log" -ForegroundColor Yellow
}

Write-Host ""
pause

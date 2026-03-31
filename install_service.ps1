# Install HerbGPT as a Windows Service using NSSM
# Download NSSM from: https://nssm.cc/download

# Configuration
$serviceName = "HerbGPT"
$pythonPath = (Get-Command python).Source
$scriptPath = "c:\Herb Project\LM-Open-Rag\main.py"
$workingDir = "c:\Herb Project\LM-Open-Rag"

# Install NSSM if not already installed
# Download from https://nssm.cc/release/nssm-2.24.zip and extract to C:\nssm

$nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"

if (-not (Test-Path $nssmPath)) {
    Write-Host "NSSM not found. Please download from https://nssm.cc/download"
    Write-Host "Extract to C:\nssm\"
    exit 1
}

# Install service
& $nssmPath install $serviceName $pythonPath $scriptPath

# Set working directory
& $nssmPath set $serviceName AppDirectory $workingDir

# Set environment variables
& $nssmPath set $serviceName AppEnvironmentExtra OLLAMA_EMBEDDING_MODEL=mxbai-embed-large OLLAMA_BASE_URL=http://localhost:11434

# Set to restart on failure
& $nssmPath set $serviceName AppExit Default Restart
& $nssmPath set $serviceName AppRestartDelay 5000

# Set log files
& $nssmPath set $serviceName AppStdout "$workingDir\logs\service-output.log"
& $nssmPath set $serviceName AppStderr "$workingDir\logs\service-error.log"

# Start service
& $nssmPath start $serviceName

Write-Host "Service installed and started successfully!"
Write-Host "To manage: services.msc or 'nssm edit $serviceName'"

# Restart HerbGPT RAG Server
# This script stops any running Python processes and starts the server fresh

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Restarting HerbGPT RAG Server" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop any running Python processes in this directory
Write-Host "Step 1: Stopping any running server processes..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*Herb Project*" -or 
    $_.MainWindowTitle -like "*main.py*"
}

if ($pythonProcesses) {
    Write-Host "Found $($pythonProcesses.Count) Python process(es) to stop" -ForegroundColor Yellow
    $pythonProcesses | ForEach-Object {
        Write-Host "  Stopping process ID: $($_.Id)" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "✓ Processes stopped" -ForegroundColor Green
} else {
    Write-Host "✓ No running processes found" -ForegroundColor Green
}

Write-Host ""

# Step 2: Set environment variables
Write-Host "Step 2: Setting environment variables..." -ForegroundColor Yellow
$env:OLLAMA_EMBEDDING_MODEL = "mxbai-embed-large"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
Write-Host "✓ Environment configured" -ForegroundColor Green

Write-Host ""

# Step 3: Start the server
Write-Host "Step 3: Starting server..." -ForegroundColor Yellow
Write-Host "  Using Ollama embeddings (mxbai-embed-large - 1024 dimensions)" -ForegroundColor Gray
Write-Host "  Server will start on http://localhost:8000" -ForegroundColor Gray
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Server Starting - Press Ctrl+C to stop" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Start the server
python main.py

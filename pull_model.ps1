# Pull Ollama model with progress display
$modelName = "qwen2.5:14b"
Write-Host "Starting download of $modelName..." -ForegroundColor Cyan

$uri = "http://localhost:11434/api/pull"
$body = @{
    name = $modelName
    stream = $true
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri $uri -Method Post -Body $body -ContentType "application/json" -UseBasicParsing
    
    # Parse streaming response
    $lines = $response.Content -split "`n"
    foreach ($line in $lines) {
        if ($line.Trim()) {
            $json = $line | ConvertFrom-Json
            if ($json.status) {
                Write-Host $json.status -ForegroundColor Green
            }
            if ($json.completed -and $json.total) {
                $percent = [math]::Round(($json.completed / $json.total) * 100, 2)
                Write-Host "Progress: $percent% ($($json.completed)/$($json.total) bytes)" -ForegroundColor Yellow
            }
        }
    }
    
    Write-Host "`nModel downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# Create a Windows Scheduled Task to run HerbGPT on startup
# This script must be run as Administrator

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again."
    pause
    exit 1
}

$taskName = "HerbGPT Server"
$pythonPath = (Get-Command python).Source
$scriptPath = "c:\Herb Project\LM-Open-Rag\main.py"
$workingDir = "c:\Herb Project\LM-Open-Rag"

Write-Host "Creating scheduled task for HerbGPT..." -ForegroundColor Cyan

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create action with environment variables
$envVars = "OLLAMA_EMBEDDING_MODEL=mxbai-embed-large;OLLAMA_BASE_URL=http://localhost:11434"
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $workingDir

# Create trigger (at startup)
$trigger = New-ScheduledTaskTrigger -AtStartup

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -StartWhenAvailable

# Create principal (run as SYSTEM)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Register task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

# Set environment variables (requires editing the task XML)
$task = Get-ScheduledTask -TaskName $taskName
$task.Actions[0].Execute = "cmd.exe"
$task.Actions[0].Arguments = "/c set OLLAMA_EMBEDDING_MODEL=mxbai-embed-large && set OLLAMA_BASE_URL=http://localhost:11434 && `"$pythonPath`" `"$scriptPath`""
$task | Set-ScheduledTask | Out-Null

Write-Host ""
Write-Host "SUCCESS! Scheduled task created!" -ForegroundColor Green
Write-Host ""
Write-Host "The task will:" -ForegroundColor Yellow
Write-Host "  - Start automatically when Windows boots"
Write-Host "  - Restart automatically if it fails (up to 3 times)"
Write-Host "  - Run in the background"
Write-Host ""

# Start the task now
Write-Host "Starting task now..." -ForegroundColor Green
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

# Check if it's running
$taskInfo = Get-ScheduledTask -TaskName $taskName
Write-Host ""
Write-Host "Task Status: $($taskInfo.State)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access your app at: http://localhost:8010" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View in Task Scheduler: taskschd.msc"
Write-Host "  Stop task:   Stop-ScheduledTask -TaskName '$taskName'"
Write-Host "  Start task:  Start-ScheduledTask -TaskName '$taskName'"
Write-Host "  Remove task: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host ""
pause

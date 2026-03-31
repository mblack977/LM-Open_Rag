# Create a Windows Scheduled Task to run HerbGPT on startup
# Run this script as Administrator

$taskName = "HerbGPT Server"
$scriptPath = "c:\Herb Project\LM-Open-Rag\start_with_ollama.ps1"

# Create action
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""

# Create trigger (at startup)
$trigger = New-ScheduledTaskTrigger -AtStartup

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force

Write-Host "Scheduled task '$taskName' created successfully!"
Write-Host "The server will start automatically on system boot."
Write-Host "To manage: taskschd.msc"

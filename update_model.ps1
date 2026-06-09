# Update .env file to use qwen2.5:32b
$envFile = "c:\Herb Project\LM-Open-Rag\.env"
$content = Get-Content $envFile -Raw
$content = $content -replace 'LM_STUDIO_MODEL=qwen2\.5:7b', 'LM_STUDIO_MODEL=qwen2.5:32b'
Set-Content $envFile -Value $content
Write-Host "Updated .env file to use qwen2.5:32b" -ForegroundColor Green

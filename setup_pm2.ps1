# Install and setup PM2 for HerbGPT
# PM2 is a production process manager for Node.js applications
# It can also manage Python applications

Write-Host "Installing PM2..."

# Check if Node.js is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is not installed. Please install from https://nodejs.org/"
    exit 1
}

# Install PM2 globally
npm install -g pm2

# Create logs directory
New-Item -ItemType Directory -Force -Path "c:\Herb Project\LM-Open-Rag\logs"

# Start the application
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on Windows boot
pm2 startup

Write-Host ""
Write-Host "PM2 setup complete!"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  pm2 list          - Show running processes"
Write-Host "  pm2 logs herbgpt  - View logs"
Write-Host "  pm2 restart herbgpt - Restart server"
Write-Host "  pm2 stop herbgpt  - Stop server"
Write-Host "  pm2 monit         - Monitor CPU/Memory"

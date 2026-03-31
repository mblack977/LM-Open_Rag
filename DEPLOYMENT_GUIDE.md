# HerbGPT Deployment Guide

This guide explains how to keep your HerbGPT server running persistently on Windows.

## Options (Ranked by Ease of Use)

### Option 1: Docker Compose (RECOMMENDED - Already Configured)

**Pros:**
- ✅ Already configured in your project
- ✅ Auto-restarts on failure
- ✅ Starts on system boot
- ✅ Isolated environment
- ✅ Easy to manage

**Setup:**
```powershell
# Start all services (Qdrant, Ollama, HerbGPT)
docker-compose up -d

# View logs
docker-compose logs -f rag-api

# Stop services
docker-compose down

# Restart just the HerbGPT service
docker-compose restart rag-api
```

**Auto-start on Windows boot:**
1. Open Docker Desktop settings
2. Go to "General"
3. Enable "Start Docker Desktop when you log in"
4. Services will auto-start with Docker

---

### Option 2: Windows Task Scheduler (SIMPLEST)

**Pros:**
- ✅ No additional software needed
- ✅ Built into Windows
- ✅ Starts on system boot

**Setup:**
```powershell
# Run as Administrator
.\create_scheduled_task.ps1
```

**Manage:**
- Open Task Scheduler (`taskschd.msc`)
- Find "HerbGPT Server" task
- Right-click to Run/Stop/Disable

---

### Option 3: PM2 Process Manager

**Pros:**
- ✅ Great monitoring tools
- ✅ Easy log management
- ✅ Auto-restart on crash

**Requirements:**
- Node.js installed

**Setup:**
```powershell
# Install PM2 and start server
.\setup_pm2.ps1

# Useful commands
pm2 list              # Show status
pm2 logs herbgpt      # View logs
pm2 restart herbgpt   # Restart
pm2 stop herbgpt      # Stop
pm2 monit             # Monitor resources
```

---

### Option 4: Windows Service (NSSM)

**Pros:**
- ✅ Runs as true Windows service
- ✅ Most stable
- ✅ Runs even when not logged in

**Requirements:**
- Download NSSM from https://nssm.cc/download
- Extract to `C:\nssm\`

**Setup:**
```powershell
# Run as Administrator
.\install_service.ps1

# Manage
services.msc  # Open Services manager
# Find "HerbGPT" service
```

---

## Current Server Status

Check if server is running:
```powershell
# Check Python processes
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# Test server
curl http://localhost:8010
```

## Manual Start (Development)

For development/testing:
```powershell
.\start_with_ollama.ps1
```

---

## Recommended Setup

**For Production/Daily Use:**
Use **Docker Compose** (Option 1) - it's already configured and most reliable.

**For Development:**
Use manual start or PM2 for easy restarts and log viewing.

---

## Troubleshooting

**Server not accessible:**
1. Check if server is running: `Get-Process python`
2. Check port 8010: `netstat -ano | findstr :8010`
3. Check logs in `logs/` folder

**Auto-start not working:**
- Docker: Ensure Docker Desktop starts on login
- Task Scheduler: Check task is enabled in `taskschd.msc`
- PM2: Run `pm2 startup` and follow instructions
- NSSM: Check service status in `services.msc`

**Server crashes:**
- Check logs in `logs/` folder
- Ensure Ollama is running
- Ensure Qdrant is running
- Check environment variables are set

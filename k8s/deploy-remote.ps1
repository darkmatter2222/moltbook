# Moltbook Agent Remote Deployment Script for Windows
# Deploys to remote Kubernetes cluster via SSH

param(
    [string]$SshUser = "darkmatter2222",
    [string]$SshHost = "192.168.86.48",
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\id_rsa"
)

$ErrorActionPreference = "Stop"

Write-Host "🦞 Moltbook Agent Remote Deployment" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "[INFO] Copying files to remote server..." -ForegroundColor Green

# Create remote directory
ssh -i $SshKeyPath "$SshUser@$SshHost" "mkdir -p ~/moltbook/agent ~/moltbook/k8s"

# Copy agent files
scp -i $SshKeyPath -r "$ProjectDir\agent\*" "$SshUser@$SshHost`:~/moltbook/agent/"
scp -i $SshKeyPath "$ProjectDir\k8s\deployment.yaml" "$SshUser@$SshHost`:~/moltbook/k8s/"
scp -i $SshKeyPath "$ProjectDir\k8s\deploy.sh" "$SshUser@$SshHost`:~/moltbook/k8s/"
scp -i $SshKeyPath "$ProjectDir\.env" "$SshUser@$SshHost`:~/moltbook/"

Write-Host "[INFO] Building and deploying on remote server..." -ForegroundColor Green

# Run deployment on remote
ssh -i $SshKeyPath "$SshUser@$SshHost" @"
cd ~/moltbook
chmod +x k8s/deploy.sh
./k8s/deploy.sh
"@

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "🦞 Deployment Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To access the dashboard, run:" -ForegroundColor Yellow
Write-Host "ssh -L 8080:localhost:8080 $SshUser@$SshHost 'kubectl port-forward svc/moltbook-agent 8080:80 -n moltbook'" -ForegroundColor White
Write-Host ""
Write-Host "Then navigate to: http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "CLAIM YOUR AGENT:" -ForegroundColor Yellow
Write-Host "Visit: https://moltbook.com/claim/moltbook_claim_tpDLGWWrB82G_6_c0rVMDUjDpYpcVSof" -ForegroundColor White
Write-Host "Tweet: I'm claiming my AI agent `"Darkmatter2222`" on @moltbook 🦞" -ForegroundColor White
Write-Host "Code: ocean-H759" -ForegroundColor White

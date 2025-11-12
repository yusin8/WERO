#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$Region,
  [string]$ServiceName = 'ask-gemini'
)

$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Write-Host "[deploy] Using source: $root\server" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $root 'server\main.py'))) {
  throw "server/main.py not found at project root: $root"
}
if (-not (Test-Path (Join-Path $root 'server\requirements.txt'))) {
  throw "server/requirements.txt not found at project root: $root"
}

Write-Host "[deploy] Deploying Cloud Run service '$ServiceName'..." -ForegroundColor Cyan
gcloud run deploy $ServiceName `
  --project $ProjectId `
  --region $Region `
  --platform managed `
  --source "$root\server" `
  --runtime python311 `
  --entry-point ask_gemini `
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest `
  --allow-unauthenticated

Write-Host "[deploy] Describing service URL..." -ForegroundColor Cyan
$url = gcloud run services describe $ServiceName --region $Region --project $ProjectId --format "value(status.url)"
Write-Host "[deploy] Service URL: $url" -ForegroundColor Green


#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$Region,
  [string]$FunctionName = 'ask-gemini',
  [int]$MinInstances = 0
)

$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Write-Host "[deploy-fn] Using source: $root" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $root 'server\main.py'))) {
  throw "server/main.py not found at project root: $root"
}
if (-not (Test-Path (Join-Path $root 'server\requirements.txt'))) {
  throw "server/requirements.txt not found at project root: $root"
}

Write-Host "[deploy-fn] Deploying Cloud Functions Gen2 '$FunctionName'..." -ForegroundColor Cyan
gcloud functions deploy $FunctionName `
  --project $ProjectId `
  --region $Region `
  --gen2 `
  --runtime python311 `
  --source "$root\server" `
  --entry-point ask_gemini `
  --trigger-http `
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest `
  --allow-unauthenticated

if ($MinInstances -gt 0) {
  Write-Host "[deploy-fn] Updating min instances to $MinInstances..." -ForegroundColor Cyan
  gcloud functions deploy $FunctionName `
    --project $ProjectId `
    --region $Region `
    --gen2 `
    --runtime python311 `
    --source "$root\server" `
    --entry-point ask_gemini `
    --trigger-http `
    --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest `
    --allow-unauthenticated `
    --min-instances $MinInstances
}

Write-Host "[deploy-fn] Describing function URL..." -ForegroundColor Cyan
$url = gcloud functions describe $FunctionName --region $Region --project $ProjectId --format "value(serviceConfig.uri)"
Write-Host "[deploy-fn] Function URL: $url" -ForegroundColor Green

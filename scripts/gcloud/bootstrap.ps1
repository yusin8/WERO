#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$Region,
  [Parameter(Mandatory=$true)] [string]$Zone
)

Write-Host "[bootstrap] Setting gcloud config..." -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null
gcloud config set run/region $Region | Out-Null
gcloud config set compute/region $Region | Out-Null
gcloud config set compute/zone $Zone | Out-Null

Write-Host "[bootstrap] Enabling required services..." -ForegroundColor Cyan
$services = @(
  'run.googleapis.com',
  'artifactregistry.googleapis.com',
  'cloudbuild.googleapis.com',
  'secretmanager.googleapis.com',
  'iam.googleapis.com',
  'cloudfunctions.googleapis.com',
  'pubsub.googleapis.com'
)
gcloud services enable $services --project $ProjectId

Write-Host "[bootstrap] Done." -ForegroundColor Green


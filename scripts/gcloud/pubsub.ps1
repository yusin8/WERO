#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [string]$TopicId = 'voice-bridge',
  [string]$SubscriptionId = 'voice-bridge-b'
)

Write-Host "[pubsub] Ensuring topic '$TopicId'..." -ForegroundColor Cyan
gcloud pubsub topics describe $TopicId --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
  gcloud pubsub topics create $TopicId --project $ProjectId
}

Write-Host "[pubsub] Ensuring subscription '$SubscriptionId'..." -ForegroundColor Cyan
gcloud pubsub subscriptions describe $SubscriptionId --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
  gcloud pubsub subscriptions create $SubscriptionId --topic $TopicId --project $ProjectId
}

Write-Host "[pubsub] Done." -ForegroundColor Green


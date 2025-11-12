#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$SecretName,
  [Parameter(Mandatory=$true)] [string]$SecretValue
)

Write-Host "[secret] Ensuring secret '$SecretName' exists..." -ForegroundColor Cyan
gcloud secrets describe $SecretName --project $ProjectId 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud secrets create $SecretName --replication-policy automatic --project $ProjectId
}

Write-Host "[secret] Adding new secret version..." -ForegroundColor Cyan
$tmp = New-TemporaryFile
Set-Content -NoNewline -Path $tmp -Value $SecretValue
gcloud secrets versions add $SecretName --data-file $tmp --project $ProjectId | Out-Null
Remove-Item $tmp -Force

Write-Host "[secret] Granting Secret Access to default compute service account..." -ForegroundColor Cyan
$projNum = gcloud projects describe $ProjectId --format "value(projectNumber)"
$computeSA = "$projNum-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$computeSA" `
  --role roles/secretmanager.secretAccessor | Out-Null

Write-Host "[secret] Done." -ForegroundColor Green


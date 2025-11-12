#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$Region,
  [Parameter(Mandatory=$true)] [string]$Zone,
  [string]$FunctionName = 'ask-gemini',
  [int]$MinInstances = 0
)

$ErrorActionPreference = 'Stop'

function Info($msg){ Write-Host $msg -ForegroundColor Cyan }
function Ok($msg){ Write-Host $msg -ForegroundColor Green }
function Warn($msg){ Write-Host $msg -ForegroundColor Yellow }
function Err($msg){ Write-Host $msg -ForegroundColor Red }

Info "[1/7] 부트스트랩: 프로젝트/리전/존 + 필수 API"
scripts\gcloud\bootstrap.ps1 -ProjectId $ProjectId -Region $Region -Zone $Zone

Info "[2/7] Secret Manager: GEMINI_API_KEY 저장"
$KEY = Read-Host -Prompt "Enter GEMINI_API_KEY (따옴표 없이)"
scripts\gcloud\create-secret.ps1 -ProjectId $ProjectId -SecretName GEMINI_API_KEY -SecretValue $KEY

Info "[3/7] 함수 배포: $FunctionName (Gen2)"
if ($MinInstances -gt 0) {
  Warn "MinInstances=$MinInstances 로 콜드스타트 지연 완화"
}
scripts\gcloud\deploy-functions.ps1 -ProjectId $ProjectId -Region $Region -FunctionName $FunctionName -MinInstances $MinInstances

Info "[4/7] 함수 URL 조회"
$FUNC_URL = gcloud functions describe $FunctionName --region $Region --project $ProjectId --format "value(serviceConfig.uri)"
Ok "Function URL: $FUNC_URL"

Info "[5/7] Pub/Sub 토픽/구독 생성"
scripts\gcloud\pubsub.ps1 -ProjectId $ProjectId

Info "[6/7] 클라이언트 의존성 확인"
if (-not (Test-Path ".venv")) {
  Warn "가상환경 생성 중 (.venv)"; python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install -U pip setuptools wheel | Out-Null
pip install -r clients\requirements.txt

Info "[7/7] 다음 단계 (복사하여 새 창에 붙여 실행)"
Write-Host "B 창 (구독/재생):" -ForegroundColor Magenta
Write-Host ("`$env:GOOGLE_APPLICATION_CREDENTIALS=`"C:\\경로\\서비스계정.json`"; `$env:GCP_PROJECT=`"{0}`"; `$env:VOICE_SUB=`"voice-bridge-b`"; `$env:FUNCTION_URL=`"{1}`"; python clients\b_subscribe_tts.py" -f $ProjectId,$FUNC_URL)
Write-Host "A 창 (녹음/발행):" -ForegroundColor Magenta
Write-Host ("`$env:GOOGLE_APPLICATION_CREDENTIALS=`"C:\\경로\\서비스계정.json`"; `$env:GCP_PROJECT=`"{0}`"; `$env:VOICE_TOPIC=`"voice-bridge`"; `$env:RECORD_SECONDS=`"3`"; python clients\a_capture_publish.py" -f $ProjectId)

Ok "All done. 즐거운 대화 되세요!"


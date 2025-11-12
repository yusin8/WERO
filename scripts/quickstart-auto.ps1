#Requires -Version 5
param(
  [Parameter(Mandatory=$true)] [string]$ProjectId,
  [Parameter(Mandatory=$true)] [string]$Region,
  [Parameter(Mandatory=$true)] [string]$Zone,
  [string]$FunctionName = 'ask-gemini',
  [int]$MinInstances = 0,
  [string]$ServiceAccountJson = '',
  [string]$TtsVoice = 'ko-KR-Standard-A',
  [double]$SpeakingRate = 1.0,
  [double]$Pitch = 0.0,
  [int]$SampleRate = 22050,
  [int]$RecordSeconds = 3
)

$ErrorActionPreference = 'Stop'
function Info($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){ Write-Host $m -ForegroundColor Green }
function Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Err($m){ Write-Host $m -ForegroundColor Red }

$projRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $projRoot

Info "[1/9] 부트스트랩: 프로젝트/리전/존 + 필수 API"
scripts\gcloud\bootstrap.ps1 -ProjectId $ProjectId -Region $Region -Zone $Zone

Info "[2/9] Secret Manager: GEMINI_API_KEY 저장"
$key = Read-Host -Prompt "Enter GEMINI_API_KEY (따옴표 없이)"
scripts\gcloud\create-secret.ps1 -ProjectId $ProjectId -SecretName GEMINI_API_KEY -SecretValue $key

Info "[3/9] 함수 배포: $FunctionName (Gen2)"
if ($MinInstances -gt 0) { Warn "MinInstances=$MinInstances 로 콜드스타트 지연 완화" }
scripts\gcloud\deploy-functions.ps1 -ProjectId $ProjectId -Region $Region -FunctionName $FunctionName -MinInstances $MinInstances

Info "[4/9] 함수 URL 조회"
$funcUrl = gcloud functions describe $FunctionName --region $Region --project $ProjectId --format "value(serviceConfig.uri)"
Ok "Function URL: $funcUrl"

Info "[5/9] Pub/Sub 토픽/구독 생성"
scripts\gcloud\pubsub.ps1 -ProjectId $ProjectId

Info "[6/9] 가상환경/의존성"
if (-not (Test-Path ".venv")) { Warn "가상환경 생성 중 (.venv)"; python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install -U pip setuptools wheel | Out-Null
pip install -r clients\requirements.txt

Info "[7/9] Service Account JSON 경로 확인"
if ([string]::IsNullOrWhiteSpace($ServiceAccountJson)) {
  $ServiceAccountJson = Read-Host -Prompt "Enter path to Service Account JSON (예: C:\\Users\\...\\key.json)"
}
if (-not (Test-Path $ServiceAccountJson)) { throw "ServiceAccountJson not found: $ServiceAccountJson" }

Info "[8/9] B 창(구독/재생) 실행"
$bContent = @"


$host.UI.RawUI.WindowTitle = 'We_robot - B (구독/재생)'
cd "$projRoot"
. .\.venv\Scripts\Activate.ps1
$env:GOOGLE_APPLICATION_CREDENTIALS = "$ServiceAccountJson"
$env:GCP_PROJECT = "$ProjectId"
$env:VOICE_SUB = "voice-bridge-b"
$env:FUNCTION_URL = "$funcUrl"
$env:TTS_VOICE = "$TtsVoice"
$env:TTS_SPEAKING_RATE = "$SpeakingRate"
$env:TTS_PITCH = "$Pitch"
$env:TTS_SAMPLE_RATE = "$SampleRate"
python clients\b_subscribe_tts.py
"@
$bFile = New-TemporaryFile
Set-Content -Path $bFile -Value $bContent -Encoding UTF8
Start-Process -FilePath powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","`"$bFile`""

Info "[9/9] A 창(녹음/발행) 실행"
$aContent = @"


$host.UI.RawUI.WindowTitle = 'We_robot - A (녹음/발행)'
cd "$projRoot"
. .\.venv\Scripts\Activate.ps1
$env:GOOGLE_APPLICATION_CREDENTIALS = "$ServiceAccountJson"
$env:GCP_PROJECT = "$ProjectId"
$env:VOICE_TOPIC = "voice-bridge"
$env:RECORD_SECONDS = "$RecordSeconds"
python clients\a_capture_publish.py
"@
$aFile = New-TemporaryFile
Set-Content -Path $aFile -Value $aContent -Encoding UTF8
Start-Process -FilePath powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","`"$aFile`""

Ok "모든 준비가 완료되었습니다. 새로 열린 두 창에서 동작을 확인하세요."


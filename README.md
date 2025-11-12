# We_robot: Voice Q&A Bridge (A → B)

A 컴퓨터에서 음성을 입력하면, B 컴퓨터에서 답변을 “소리”로 재생하는 구성을 제공합니다.
- A: 음성 녹음 → STT → 텍스트를 Pub/Sub로 발행
- B: Pub/Sub 구독 → LLM HTTP 함수 호출 → TTS → 스피커 출력
- 서버: Google Cloud Functions Gen2(HTTP)

## 폴더 구조
- `server/` — Cloud Functions Gen2 HTTP 엔드포인트(`ask_gemini`)
- `clients/` — A/B 클라이언트
- `scripts/gcloud/` — gcloud 배포/리소스 스크립트

---

## 복붙용 전체 셋업 스크립트 (PowerShell)

아래를 순서대로 PowerShell에 그대로 붙여 넣어 실행하세요. 중간에 API 키만 직접 입력합니다.

```powershell
# 0) 변수/경로
$PROJECT="we-robot-466007"; $REGION="asia-northeast3"; $ZONE="asia-northeast3-a"; $SERVICE="ask-gemini"
cd C:\Users\ADMIN\Desktop\_\We_robot

# 1) SDK 로그인 (최초 1회)
gcloud auth login

# 2) 부트스트랩(프로젝트/리전/존 + 필수 API)
scripts\gcloud\bootstrap.ps1 -ProjectId $PROJECT -Region $REGION -Zone $ZONE

# 3) Secret Manager에 Gemini API 키 저장 (프롬프트에 키 입력)
$KEY = Read-Host -Prompt "Enter GEMINI_API_KEY (따옴표 없이)"   
AIzaSyBPpdF_-Ky37g7wGrYnidndnoDmnXj5s48
scripts\gcloud\create-secret.ps1 -ProjectId $PROJECT -SecretName GEMINI_API_KEY -SecretValue $KEY

# 4) 서버 배포 (콜드스타트 줄이려면 -MinInstances 1 추가 가능)
scripts\gcloud\deploy-functions.ps1 -ProjectId $PROJECT -Region $REGION -FunctionName $SERVICE # -MinInstances 1

# 5) 함수 URL 확인
$FUNC_URL = gcloud functions describe $SERVICE --region $REGION --project $PROJECT --format "value(serviceConfig.uri)"; $FUNC_URL

# 6) Pub/Sub 리소스 생성 (토픽/구독)
scripts\gcloud\pubsub.ps1 -ProjectId $PROJECT

# 7) (선택) 현재 세션에 B 클라이언트용 환경설정
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\ADMIN\\Downloads\\we-robot-466007-f56ff246ab8b.json"
$env:GCP_PROJECT=$PROJECT; $env:VOICE_SUB="voice-bridge-b"; $env:FUNCTION_URL=$FUNC_URL

# 8) (선택) 현재 세션에 A 클라이언트용 환경설정
# $env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\ADMIN\\Downloads\\we-robot-466007-f56ff246ab8b.json"
# $env:GCP_PROJECT=$PROJECT; $env:VOICE_TOPIC="voice-bridge"; $env:RECORD_SECONDS="3"

# 9) (선택) 클라이언트 의존성 설치/업데이트
python -m venv .venv; . .\.venv\Scripts\Activate.ps1; pip install -U pip setuptools wheel; pip install -r clients\requirements.txt

# 10) (선택) 테스트 호출
Invoke-RestMethod -Method Post -Uri $FUNC_URL -ContentType 'application/json' -Body '{"prompt":"안녕?"}'
```

컬러 출력과 프롬프트가 있는 통합 스크립트도 제공합니다:

```powershell
scripts\quickstart.ps1 -ProjectId we-robot-466007 -Region asia-northeast3 -Zone asia-northeast3-a -FunctionName ask-gemini
```

---

## B(구독/재생) 빠른 실행
```powershell
cd C:\Users\ADMIN\Desktop\_\We_robot
. .\.venv\Scripts\Activate.ps1
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\ADMIN\\Downloads\\we-robot-466007-f56ff246ab8b.json"
$env:GCP_PROJECT="we-robot-466007"; $env:VOICE_SUB="voice-bridge-b"; $env:FUNCTION_URL="<함수 URL>"

# 음성 톤/속도 조절 (선택)
$env:TTS_VOICE="ko-KR-Standard-A"; $env:TTS_SPEAKING_RATE="1.05"; $env:TTS_PITCH="0.0"; $env:TTS_SAMPLE_RATE="22050"

python clients\b_subscribe_tts.py
```

## A(녹음/발행) 빠른 실행
```powershell
cd C:\Users\ADMIN\Desktop\_\We_robot
. .\.venv\Scripts\Activate.ps1
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\ADMIN\\Downloads\\we-robot-466007-f56ff246ab8b.json"
$env:GCP_PROJECT="we-robot-466007"; $env:VOICE_TOPIC="voice-bridge"; $env:RECORD_SECONDS="3"

python clients\a_capture_publish.py
```

---

## 참고/문제 해결
- 서버 엔드포인트는 POST JSON `{ "prompt": "..." }` 를 받습니다.
- 400 'prompt' 오류는 브라우저 GET으로 접근했을 때 발생 — POST로 보내세요.
- 인증 오류: `GOOGLE_APPLICATION_CREDENTIALS` 경로가 실제 서비스계정 JSON인지 확인.
- 음성 문제: Windows 사운드 설정에서 입력/출력 기본 장치 확인.
- TTS 톤/속도: `TTS_VOICE`, `TTS_SPEAKING_RATE`, `TTS_PITCH`, `TTS_SAMPLE_RATE`로 조절.

서버 프롬프트(손주→70세 어르신 공손 말투)는 `server/main.py`에 반영되어 있습니다.

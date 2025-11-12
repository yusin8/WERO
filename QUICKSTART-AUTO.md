# Quickstart (Auto) — We_robot

자동형 퀵스타트 스크립트(`scripts/quickstart-auto.ps1`) 사용 가이드입니다. 이 스크립트는 부트스트랩 → 시크릿 저장 → 배포 → 함수 URL 조회 → Pub/Sub 생성 → 가상환경 설치 → A/B 두 창 실행까지 자동으로 처리합니다.

## 요구 사항
- Windows PowerShell 5+
- Google Cloud SDK 설치 및 로그인 가능 상태
- 프로젝트 권한(Owner/Editor 권장)
- 서비스 계정 키(JSON) 파일 경로

## 기본 사용법
```powershell
cd C:\Users\ADMIN\Desktop\_\We_robot
scripts\quickstart-auto.ps1 `
  -ProjectId we-robot-466007 `
  -Region asia-northeast3 `
  -Zone asia-northeast3-a `
  -FunctionName ask-gemini `
  -MinInstances 1 `
  -ServiceAccountJson "C:\Users\ADMIN\Downloads\we-robot-466007-f56ff246ab8b.json" `
  -TtsVoice "ko-KR-Standard-A" `
  -SpeakingRate 1.05 `
  -Pitch 0.0 `
  -SampleRate 22050 `
  -RecordSeconds 3
```

실행 중 프롬프트에 `GEMINI_API_KEY`를 입력하라는 메시지가 나오면, 따옴표 없이 정확히 붙여 넣으세요.

## 파라미터 설명
- `-ProjectId` GCP 프로젝트 ID (필수)
- `-Region` 함수/리소스 리전 (필수)
- `-Zone` 기본 존 (필수)
- `-FunctionName` 배포되는 함수 이름 (기본: `ask-gemini`)
- `-MinInstances` 함수 최소 인스턴스(콜드스타트 완화, 기본 0)
- `-ServiceAccountJson` 서비스 계정 키 파일 경로(필수 권장; 미지정 시 프롬프트 입력)
- TTS 관련(선택):
  - `-TtsVoice` 음성(기본 `ko-KR-Standard-A`)
  - `-SpeakingRate` 말속도(기본 1.0)
  - `-Pitch` 톤(기본 0.0)
  - `-SampleRate` 샘플 레이트 Hz(기본 22050)
- A(녹음) 관련(선택):
  - `-RecordSeconds` 녹음 길이(기본 3초)

## 스크립트가 수행하는 일
1) gcloud 프로젝트/리전/존 설정, 필수 API 활성화
2) Secret Manager에 `GEMINI_API_KEY` 저장(프롬프트 입력 값)
3) Cloud Functions Gen2 배포(옵션: 최소 인스턴스 유지)
4) 함수 URL 조회 및 표시
5) Pub/Sub `voice-bridge`(토픽) / `voice-bridge-b`(구독) 생성
6) `.venv` 가상환경 및 클라이언트 의존성 설치
7) PowerShell 창 2개 자동 실행
   - B: 구독/재생(토픽 수신 → LLM 호출 → TTS 재생)
   - A: 녹음/발행(마이크 → STT → Pub/Sub 발행)

## 실행 후 확인
- "We_robot - B (구독/재생)" 창이 `Listening...`을 출력
- "We_robot - A (녹음/발행)" 창에서 녹음 후 발행
- B 창에서 "Received: ..." → 답변 음성 재생
- 중지: 각 창에서 `Ctrl + C`

## 문제 해결
- 자격 증명 오류: `-ServiceAccountJson` 경로가 실제 JSON 키인지 확인
- API 권한 오류: 프로젝트에서 Owner/Editor 또는 Service Usage Admin 필요
- "prompt" 400 오류: 함수는 POST JSON만 허용(브라우저 GET 불가)
- 오디오 문제: Windows 사운드 설정에서 입력/출력 기본 장치 확인
- 키 오류: 시크릿 입력 시 따옴표/공백 포함하지 않기(필요 시 새 버전 추가 후 재배포)

## 수동 모드와 병행
자동 스크립트를 원치 않는 경우, `README.md`의 수동 절차(복붙용 명령 포함)를 사용하세요. 두 방식은 함께 공존합니다.

We_robot 실행 가이드 (A/B 환경변수 + 실행 명령)

개요
- A: 마이크로 말하기 → STT → Pub/Sub 발행
- B: Pub/Sub 구독 → LLM 함수 호출 → TTS로 스피커 출력

사전 준비(공통, PowerShell)
- 폴더: C:\Users\ADMIN\Desktop\_\We_robot
- 가상환경 생성/활성화 후 의존성 설치
  - python -m venv .venv
  - . .\.venv\Scripts\Activate.ps1
  - pip install -r clients\requirements.txt
- Pub/Sub 리소스(최초 1회): scripts\gcloud\pubsub.ps1 -ProjectId we-robot-466007

서버(LLM 함수) URL 확인 방법
- $FUNC_URL = gcloud functions describe ask-gemini --region asia-northeast3 --project we-robot-466007 --format "value(serviceConfig.uri)"
- echo $FUNC_URL

A 컴퓨터(녹음/발행) 환경변수 + 실행
- 필수
  - $env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\ADMIN\Desktop\_\We_robot\we-robot-466007-f56ff246ab8b.json"
  - $env:GCP_PROJECT="we-robot-466007"
  - $env:VOICE_TOPIC="voice-bridge"
- 선택
  - $env:RECORD_SECONDS="5"   # 기본 5초, 지연 줄이려면 2~3 추천
- 실행
  - python clients\a_capture_publish.py
- 관련 파일
  - We_robot/clients/a_capture_publish.py:1

B 컴퓨터(구독/재생) 환경변수 + 실행
- 필수
  - $env:GOOGLE_APPLICATION_CREDENTIALS="C:\Users\ADMIN\Desktop\_\We_robot\we-robot-466007-f56ff246ab8b.json"
  - $env:GCP_PROJECT="we-robot-466007"
  - $env:VOICE_SUB="voice-bridge-b"
  - $env:FUNCTION_URL="<함수 URL>"  # 위 ‘서버 URL 확인 방법’으로 조회한 값
- 선택(음성 톤/속도)
  - $env:TTS_VOICE="ko-KR-Standard-A"   # 다른 한국어 음성으로 변경 가능
  - $env:TTS_SPEAKING_RATE="1.0"        # 0.8~1.2 사이 미세 조정
  - $env:TTS_PITCH="0.0"                # -6.0 ~ +6.0
  - $env:TTS_SAMPLE_RATE="22050"        # 16000/22050/24000 등
- 실행
  - python clients\b_subscribe_tts.py
- 관련 파일
  - We_robot/clients/b_subscribe_tts.py:1

빠른 동작 확인(마이크 없이)
- gcloud pubsub topics publish voice-bridge --message "테스트 메시지입니다"
- B 창에서 수신/합성 음성이 재생되면 정상

지연(레이턴시) 줄이는 팁
- A에서 녹음 길이를 2~3초로 축소: $env:RECORD_SECONDS="3"
- Cloud Functions 콜드스타트 완화(선택):
  - scripts\gcloud\deploy-functions.ps1 -ProjectId we-robot-466007 -Region asia-northeast3 -FunctionName ask-gemini -MinInstances 1

손주 말투(70세 어르신 대상) 프롬프트 반영 위치
- We_robot/server/main.py:15

트러블슈팅
- 인증 오류: GOOGLE_APPLICATION_CREDENTIALS 경로가 실제 JSON 키 파일인지 확인
- B 시작 로그에 FUNCTION_URL이 빈 값이면 설정 후 같은 창에서 재실행
- 오디오 문제: Windows 사운드 설정에서 입력/출력 기본 장치 확인
- 권한 부족(구독/합성): 프로젝트에서 해당 서비스계정에 Pub/Sub Subscriber, Text-to-Speech User 권한 부여

참고 스크립트(선택)
- 배포/설정 스크립트: We_robot/scripts/gcloud/ 아래
- 서버 엔드포인트 코드: We_robot/server/main.py:1

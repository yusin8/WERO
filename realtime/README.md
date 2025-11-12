# Realtime (Raspberry Pi ↔ PC) over WebSocket

목표: 라즈베리 파이는 마이크/스피커만 담당하고, PC가 STT → LLM → TTS 처리를 수행한 뒤 오디오로 응답을 돌려줍니다.

구성
- PC(배치형): `realtime/server_ws.py` — 고정 길이 발화용(WebSocket)
- PC(스트리밍): `realtime/server_ws_stream.py` — 스트리밍 인식(WebSocket)
- Pi(배치형): `realtime/client_pi_ws.py` — 고정 길이 발화(3초 등)
- Pi(스트리밍): `realtime/client_pi_vad_ws.py` — webrtcvad 기반 침묵감지로 즉시 종료

요구 사항
- 공통(Python 3.10+ 권장)
  - PC(Windows): `pip install -r realtime/requirements-pc.txt`  ← webrtcvad 미포함
  - Pi(Linux/ARM): `pip install -r realtime/requirements-pi.txt`  ← webrtcvad 포함
- PC: Google Cloud 자격 증명(서비스계정 JSON), Speech/TTS API 사용 권한, 함수 URL(또는 직접 LLM 호출)
- Pi: PortAudio(사운드), 기본 마이크/스피커 설정

PC(서버) 설정 — 배치형 또는 스트리밍 중 택1
1) 의존성 설치
```powershell
cd C:\Users\ADMIN\Desktop\_\We_robot
. .\.venv\Scripts\Activate.ps1
pip install -r realtime\requirements-pc.txt
```
2) 환경 변수
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\\Users\\ADMIN\\Downloads\\we-robot-466007-f56ff246ab8b.json"
$env:FUNCTION_URL=(gcloud functions describe ask-gemini --region asia-northeast3 --project we-robot-466007 --format "value(serviceConfig.uri)")
# (선택) TTS 보정
$env:TTS_VOICE="ko-KR-Standard-A"; $env:TTS_SPEAKING_RATE="1.0"; $env:TTS_PITCH="0.0"; $env:TTS_SAMPLE_RATE="22050"
```
3A) 서버 실행(배치형, 포트 8765)
```powershell
python realtime\server_ws.py
# 방화벽 허용 필요 시 8765 인바운드 허용
```
3B) 서버 실행(스트리밍형, 포트 8766)
```powershell
python realtime\server_ws_stream.py
# 방화벽 허용 필요 시 8766 인바운드 허용
```

Raspberry Pi(클라이언트) 설정 — 배치형 또는 스트리밍 중 택1
1) 사운드/파이썬 준비(한 번)
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv libportaudio2
python3 -m venv ~/we_robot_venv
source ~/we_robot_venv/bin/activate
pip install -r /path/to/We_robot/realtime/requirements-pi.txt
```
2A) 환경 변수(배치형)
```bash
export WS_SERVER="ws://<PC_LAN_IP>:8765"   # 예: ws://192.168.0.10:8765
export CAP_RATE=16000
export RECORD_SECONDS=3
```
3A) 실행(배치형)
```bash
python /path/to/We_robot/realtime/client_pi_ws.py
```

2B) 환경 변수(스트리밍)
```bash
export WS_SERVER="ws://<PC_LAN_IP>:8766"
export CAP_RATE=16000
export FRAME_MS=20
export VAD_AGGRESSIVENESS=2
export VAD_START_FRAMES=5
export VAD_END_FRAMES=10
```
3B) 실행(스트리밍)
```bash
python /path/to/We_robot/realtime/client_pi_vad_ws.py
```

동작
1) Pi: 3초 녹음 → PCM 전송
2) PC: STT(ko-KR) → Cloud Function(LLM) 호출 → TTS(ko-KR) PCM 생성
3) Pi: 응답 PCM 수신/재생

지연 줄이기 팁
- 스트리밍(3B) 사용: 발화 종료 즉시 인식 완료 → LLM/TTS 진행
- 배치형은 RECORD_SECONDS를 2~3초로 유지
- PC 함수 MinInstances로 콜드스타트 완화(README.md 참고)

보안/네트워크
- 동일 LAN 환경 가정. 외부 노출 시 TLS/WSS, 방화벽/포트포워딩, 토큰 인증 추가 권장

참고(Windows에서 webrtcvad 설치 에러 시)
- webrtcvad는 C 확장 빌드가 필요합니다. Windows에서 테스트 용도로 설치하려면 “Microsoft C++ Build Tools”가 필요합니다.
- 본 프로젝트에서는 VAD는 라즈베리 파이에서만 사용하므로, PC(Windows)에서는 `requirements-pc.txt`로 설치해 webrtcvad를 생략하세요.

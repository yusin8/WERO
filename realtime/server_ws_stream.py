import os
import asyncio
import base64
import json
import time
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
import requests
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as tts


HOST = os.environ.get("WS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WS_PORT", "8766"))  # use a different port than non-streaming
FUNCTION_URL = os.environ.get("FUNCTION_URL", "")


async def _safe_send(websocket, payload: dict):
    try:
        await websocket.send(json.dumps(payload))
    except (ConnectionClosed, ConnectionClosedOK):
        return


async def handle_connection(websocket):
    # Per-utterance state (VAD로 조기 종료되지만 STT는 배치 인식 사용)
    buffer: Optional[bytearray] = None
    rate_hz: int = 16000
    try:
        async for message in websocket:
            data = json.loads(message)
            mtype = data.get("type")

            if mtype == "begin_utt":
                rate_hz = int(data.get("rate", 16000))
                buffer = bytearray()
                await _safe_send(websocket, {"type": "ack", "ok": True})

            elif mtype == "audio_chunk":
                if buffer is None:
                    await _safe_send(websocket, {"type": "error", "error": "no_active_utterance"})
                    continue
                pcm_b64 = data.get("pcm_base64")
                if not pcm_b64:
                    continue
                buffer.extend(base64.b64decode(pcm_b64))

            elif mtype == "end_utt":
                if buffer is None or len(buffer) == 0:
                    await _safe_send(websocket, {"type": "stt", "text": "", "error": "no_speech"})
                    continue
                # 성능 측정을 위해 타이머 시작
                t0 = time.perf_counter()
                audio_len_bytes = len(buffer)
                audio_sec = audio_len_bytes / (2 * max(1, rate_hz))  # int16 mono
                # 배치 인식으로 즉시 처리
                try:
                    stt_client = speech.SpeechClient()
                    cfg = speech.RecognitionConfig(
                        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                        language_code="ko-KR",
                        sample_rate_hertz=rate_hz,
                        enable_automatic_punctuation=True,
                    )
                    audio_in = speech.RecognitionAudio(content=bytes(buffer))
                    stt_resp = stt_client.recognize(config=cfg, audio=audio_in)
                    stt_text = stt_resp.results[0].alternatives[0].transcript.strip() if stt_resp.results else ""
                except Exception as e:
                    print(f"[server-stream] STT error: {e}")
                    await _safe_send(websocket, {"type": "error", "error": f"stt_failed: {e}"})
                    buffer = None
                    continue
                t1 = time.perf_counter()
                stt_ms = int((t1 - t0) * 1000)
                buffer = None
                if not stt_text:
                    await _safe_send(websocket, {"type": "stt", "text": "", "error": "no_speech"})
                    continue

                # LLM call
                if not FUNCTION_URL:
                    await _safe_send(websocket, {"type": "error", "error": "FUNCTION_URL not set"})
                    continue
                try:
                    r = requests.post(FUNCTION_URL, json={"prompt": stt_text}, timeout=60)
                    r.raise_for_status()
                    llm = r.json().get("response", "")
                except Exception as e:
                    print(f"[server-stream] LLM call error: {e}")
                    await _safe_send(websocket, {"type": "error", "error": f"llm_call_failed: {e}"})
                    continue
                if not llm:
                    await _safe_send(websocket, {"type": "error", "error": "empty_llm_response"})
                    continue
                t2 = time.perf_counter()
                llm_ms = int((t2 - t1) * 1000)

                # TTS
                try:
                    tts_client = tts.TextToSpeechClient()
                    input_text = tts.SynthesisInput(text=llm)
                    voice = tts.VoiceSelectionParams(
                        language_code="ko-KR", name=os.environ.get("TTS_VOICE", "ko-KR-Standard-A")
                    )
                    sample_rate = int(os.environ.get("TTS_SAMPLE_RATE", "22050"))
                    speaking_rate = float(os.environ.get("TTS_SPEAKING_RATE", "1.0"))
                    pitch = float(os.environ.get("TTS_PITCH", "0.0"))
                    audio_cfg = tts.AudioConfig(
                        audio_encoding=tts.AudioEncoding.LINEAR16,
                        sample_rate_hertz=sample_rate,
                        speaking_rate=speaking_rate,
                        pitch=pitch,
                    )
                    tts_resp = tts_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_cfg)
                    pcm_out = tts_resp.audio_content
                except Exception as e:
                    print(f"[server-stream] TTS error: {e}")
                    await _safe_send(websocket, {"type": "error", "error": f"tts_failed: {e}"})
                    continue
                t3 = time.perf_counter()
                tts_ms = int((t3 - t2) * 1000)
                total_ms = int((t3 - t0) * 1000)
                print(
                    f"[perf] audio={audio_sec:.2f}s stt={stt_ms}ms llm={llm_ms}ms tts={tts_ms}ms total={total_ms}ms"
                )

                await _safe_send(
                    websocket,
                    {
                        "type": "audio_reply",
                        "stt_text": stt_text,
                        "llm_text": llm,
                        "rate": sample_rate,
                        "pcm_base64": base64.b64encode(pcm_out).decode("ascii"),
                        "metrics": {
                            "audio_sec": round(audio_sec, 2),
                            "stt_ms": stt_ms,
                            "llm_ms": llm_ms,
                            "tts_ms": tts_ms,
                            "total_ms": total_ms,
                        },
                    },
                )

            else:
                await _safe_send(websocket, {"type": "error", "error": f"unknown_type:{mtype}"})
    except (ConnectionClosed, ConnectionClosedOK):
        # client closed socket; do not spam stack traces
        return


async def main():
    async with websockets.serve(handle_connection, HOST, PORT, max_size=10_000_000):
        print(f"[server-stream] listening on ws://{HOST}:{PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

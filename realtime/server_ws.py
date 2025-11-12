import os
import asyncio
import base64
import json
from typing import Dict, Any

import numpy as np
import websockets
import requests
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as tts


HOST = os.environ.get("WS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WS_PORT", "8765"))
FUNCTION_URL = os.environ.get("FUNCTION_URL", "")


async def handle_connection(websocket: websockets.WebSocketServerProtocol):
    async for message in websocket:
        try:
            data = json.loads(message)
            if data.get("type") != "audio":
                await websocket.send(json.dumps({"type": "error", "error": "invalid message type"}))
                continue

            sr = int(data.get("rate", 16000))
            pcm_b64 = data.get("pcm_base64")
            if not pcm_b64:
                await websocket.send(json.dumps({"type": "error", "error": "missing pcm_base64"}))
                continue

            audio_bytes = base64.b64decode(pcm_b64)

            # 1) STT (non-streaming for short utterances)
            stt_client = speech.SpeechClient()
            audio_cfg = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="ko-KR",
                sample_rate_hertz=sr,
                enable_automatic_punctuation=True,
            )
            audio_in = speech.RecognitionAudio(content=audio_bytes)
            stt_resp = stt_client.recognize(config=audio_cfg, audio=audio_in)
            if not stt_resp.results:
                await websocket.send(json.dumps({"type": "stt", "text": "", "error": "no_speech"}))
                continue
            text_in = stt_resp.results[0].alternatives[0].transcript.strip()

            # 2) LLM (use Cloud Function URL if provided)
            if not FUNCTION_URL:
                await websocket.send(json.dumps({"type": "error", "error": "FUNCTION_URL not set"}))
                continue
            r = requests.post(FUNCTION_URL, json={"prompt": text_in}, timeout=60)
            r.raise_for_status()
            llm = r.json().get("response", "")
            if not llm:
                await websocket.send(json.dumps({"type": "error", "error": "empty_llm_response"}))
                continue

            # 3) TTS → LINEAR16 PCM
            tts_client = tts.TextToSpeechClient()
            input_text = tts.SynthesisInput(text=llm)
            voice = tts.VoiceSelectionParams(language_code="ko-KR", name=os.environ.get("TTS_VOICE", "ko-KR-Standard-A"))
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

            await websocket.send(json.dumps({
                "type": "audio_reply",
                "stt_text": text_in,
                "llm_text": llm,
                "rate": sample_rate,
                "pcm_base64": base64.b64encode(pcm_out).decode("ascii"),
            }))

        except Exception as e:
            await websocket.send(json.dumps({"type": "error", "error": str(e)}))


async def main():
    async with websockets.serve(handle_connection, HOST, PORT, max_size=10_000_000):
        print(f"[server] listening on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())


import os
import asyncio
import base64
import json
from typing import AsyncIterator, Optional

import websockets
import requests
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as tts


HOST = os.environ.get("WS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WS_PORT", "8766"))  # use a different port than non-streaming
FUNCTION_URL = os.environ.get("FUNCTION_URL", "")


async def _run_streaming_recognize(
    cfg: speech.RecognitionConfig,
    audio_queue: "asyncio.Queue[Optional[bytes]]",
):
    client = speech.SpeechClient()

    def req_iter():
        # first, config
        s_cfg = speech.StreamingRecognitionConfig(
            config=cfg,
            interim_results=True,
            single_utterance=False,
        )
        yield speech.StreamingRecognizeRequest(streaming_config=s_cfg)
        # then audio chunks until sentinel
        while True:
            chunk = asyncio.run_coroutine_threadsafe(audio_queue.get(), asyncio.get_event_loop()).result()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    responses = client.streaming_recognize(req_iter())
    final_text = ""
    for resp in responses:
        for res in resp.results:
            if res.is_final and res.alternatives:
                final_text = res.alternatives[0].transcript
    return final_text.strip()


async def handle_connection(websocket: websockets.WebSocketServerProtocol):
    # Per-utterance state
    audio_q: Optional[asyncio.Queue] = None
    recog_task: Optional[asyncio.Task] = None

    async for message in websocket:
        data = json.loads(message)
        mtype = data.get("type")

        if mtype == "begin_utt":
            rate = int(data.get("rate", 16000))
            cfg = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="ko-KR",
                sample_rate_hertz=rate,
                enable_automatic_punctuation=True,
            )
            audio_q = asyncio.Queue()
            # launch recognizer in background thread via to_thread
            recog_task = asyncio.create_task(asyncio.to_thread(_blocking_streaming, cfg, audio_q))
            await websocket.send(json.dumps({"type": "ack", "ok": True}))

        elif mtype == "audio_chunk":
            if audio_q is None:
                await websocket.send(json.dumps({"type": "error", "error": "no_active_utterance"}))
                continue
            pcm_b64 = data.get("pcm_base64")
            if not pcm_b64:
                continue
            await audio_q.put(base64.b64decode(pcm_b64))

        elif mtype == "end_utt":
            if audio_q is None or recog_task is None:
                await websocket.send(json.dumps({"type": "error", "error": "no_active_utterance"}))
                continue
            await audio_q.put(None)
            # wait STT result
            stt_text = await recog_task
            audio_q = None
            recog_task = None

            if not stt_text:
                await websocket.send(json.dumps({"type": "stt", "text": "", "error": "no_speech"}))
                continue

            # LLM call
            if not FUNCTION_URL:
                await websocket.send(json.dumps({"type": "error", "error": "FUNCTION_URL not set"}))
                continue
            try:
                r = requests.post(FUNCTION_URL, json={"prompt": stt_text}, timeout=60)
                r.raise_for_status()
                llm = r.json().get("response", "")
            except Exception as e:
                await websocket.send(json.dumps({"type": "error", "error": f"llm_call_failed: {e}"}))
                continue
            if not llm:
                await websocket.send(json.dumps({"type": "error", "error": "empty_llm_response"}))
                continue

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
                await websocket.send(json.dumps({"type": "error", "error": f"tts_failed: {e}"}))
                continue

            await websocket.send(
                json.dumps(
                    {
                        "type": "audio_reply",
                        "stt_text": stt_text,
                        "llm_text": llm,
                        "rate": sample_rate,
                        "pcm_base64": base64.b64encode(pcm_out).decode("ascii"),
                    }
                )
            )

        else:
            await websocket.send(json.dumps({"type": "error", "error": f"unknown_type:{mtype}"}))


def _blocking_streaming(cfg: speech.RecognitionConfig, audio_q: "asyncio.Queue[Optional[bytes]]") -> str:
    # run in a worker thread (called via asyncio.to_thread)
    client = speech.SpeechClient()

    def req_iter():
        s_cfg = speech.StreamingRecognitionConfig(
            config=cfg,
            interim_results=True,
            single_utterance=False,
        )
        yield speech.StreamingRecognizeRequest(streaming_config=s_cfg)
        loop = asyncio.new_event_loop()
        try:
            while True:
                # use queue.get_nowait with small sleep
                try:
                    item = audio_q.get_nowait()
                except asyncio.QueueEmpty:
                    # small sleep to reduce CPU
                    import time

                    time.sleep(0.01)
                    continue
                if item is None:
                    break
                yield speech.StreamingRecognizeRequest(audio_content=item)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    responses = client.streaming_recognize(req_iter())
    final_text = ""
    for resp in responses:
        for res in resp.results:
            if res.is_final and res.alternatives:
                final_text = res.alternatives[0].transcript
    return final_text.strip()


async def main():
    async with websockets.serve(handle_connection, HOST, PORT, max_size=10_000_000):
        print(f"[server-stream] listening on ws://{HOST}:{PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())


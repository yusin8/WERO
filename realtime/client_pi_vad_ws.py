import os
import sys
import time
import base64
import json
import collections

import numpy as np
import sounddevice as sd
import websockets
import webrtcvad


WS_SERVER = os.environ.get("WS_SERVER", "ws://<PC_IP>:8766")
RATE = int(os.environ.get("CAP_RATE", "16000"))
FRAME_MS = int(os.environ.get("FRAME_MS", "20"))
VAD_AGGR = int(os.environ.get("VAD_AGGRESSIVENESS", "2"))  # 0..3
START_VOICE_FRAMES = int(os.environ.get("VAD_START_FRAMES", "5"))
END_SILENCE_FRAMES = int(os.environ.get("VAD_END_FRAMES", "10"))


def frame_bytes(samples: np.ndarray) -> bytes:
    return samples.astype(np.int16).tobytes()


def iter_frames(block_q):
    while True:
        b = block_q.popleft() if block_q else None
        if b is None:
            yield None
            break
        yield b


async def run_session():
    frame_len = int(RATE * FRAME_MS / 1000)
    vad = webrtcvad.Vad(VAD_AGGR)
    block_q = collections.deque()
    speaking = False
    voiced_count = 0
    silence_count = 0

    def callback(indata, frames, time_info, status):
        if status:
            pass
        block = bytes(indata)  # bytes length = frames * 2 (int16)
        # ensure exact frame size; if device blocksize differs, buffer slice
        block_q.append(block)
        return None

    # Use RawInputStream to get int16 bytes
    with sd.RawInputStream(samplerate=RATE, blocksize=frame_len, dtype='int16', channels=1, callback=callback):
        async with websockets.connect(WS_SERVER, max_size=10_000_000) as ws:
            t_start = time.perf_counter()
            # wait for voice start
            while True:
                if not block_q:
                    await asyncio.sleep(0.005)
                    continue
                block = block_q.popleft()
                is_voiced = vad.is_speech(block, RATE)
                voiced_count = voiced_count + 1 if is_voiced else 0
                if voiced_count >= START_VOICE_FRAMES:
                    speaking = True
                    # begin utterance
                    await ws.send(json.dumps({"type": "begin_utt", "rate": RATE}))
                    # send the frames already in buffer (including this one)
                    await ws.send(json.dumps({"type": "audio_chunk", "pcm_base64": base64.b64encode(block).decode("ascii")}))
                    break

            # stream until silence tail
            silence_count = 0
            while speaking:
                if not block_q:
                    await asyncio.sleep(0.005)
                    continue
                block = block_q.popleft()
                await ws.send(json.dumps({"type": "audio_chunk", "pcm_base64": base64.b64encode(block).decode("ascii")}))
                if vad.is_speech(block, RATE):
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count >= END_SILENCE_FRAMES:
                        speaking = False
                        await ws.send(json.dumps({"type": "end_utt"}))
                        break

            # wait reply
            reply = await ws.recv()
            data = json.loads(reply)
            if data.get("type") != "audio_reply":
                print("[pi-stream] error:", data)
                return 2
            print("[pi-stream] STT:", data.get("stt_text"))
            print("[pi-stream] LLM:", data.get("llm_text"))
            m = data.get("metrics") or {}
            if m:
                print(
                    f"[pi-stream] metrics server: audio={m.get('audio_sec','?')}s, stt={m.get('stt_ms','?')}ms, llm={m.get('llm_ms','?')}ms, tts={m.get('tts_ms','?')}ms, total={m.get('total_ms','?')}ms"
                )
            t_end = time.perf_counter()
            print(f"[pi-stream] metrics client: rtt={int((t_end - t_start)*1000)}ms")
            rate = int(data.get("rate", RATE))
            pcm = base64.b64decode(data.get("pcm_base64", ""))
            arr = np.frombuffer(pcm, dtype=np.int16)
            sd.play(arr, samplerate=rate, blocking=True)
            return 0


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(run_session())
    except KeyboardInterrupt:
        sys.exit(0)

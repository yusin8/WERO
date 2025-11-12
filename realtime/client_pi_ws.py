import os
import sys
import json
import base64
import asyncio
from typing import Tuple

import numpy as np
import sounddevice as sd
import websockets


SERVER = os.environ.get("WS_SERVER", "ws://<PC_IP>:8765")
CAP_RATE = int(os.environ.get("CAP_RATE", "16000"))
RECORD_SECONDS = float(os.environ.get("RECORD_SECONDS", "3"))


def record_block(seconds: float, rate: int) -> bytes:
    print(f"[pi] Recording {seconds}s @ {rate}Hz (mono)...")
    audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="int16")
    sd.wait()
    return audio.astype("int16").tobytes()


def play_pcm(pcm: bytes, rate: int):
    arr = np.frombuffer(pcm, dtype=np.int16)
    sd.play(arr, samplerate=rate, blocking=True)


async def run_once():
    async with websockets.connect(SERVER, max_size=10_000_000) as ws:
        raw = record_block(RECORD_SECONDS, CAP_RATE)
        msg = {
            "type": "audio",
            "rate": CAP_RATE,
            "pcm_base64": base64.b64encode(raw).decode("ascii"),
        }
        await ws.send(json.dumps(msg))
        print("[pi] Sent audio; waiting for reply...")
        reply = await ws.recv()
        data = json.loads(reply)
        if data.get("type") != "audio_reply":
            print("[pi] error:", data)
            return 2
        print("[pi] STT:", data.get("stt_text"))
        print("[pi] LLM:", data.get("llm_text"))
        pcm_b = base64.b64decode(data.get("pcm_base64", ""))
        rate = int(data.get("rate", 22050))
        play_pcm(pcm_b, rate)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run_once()))
    except KeyboardInterrupt:
        sys.exit(0)


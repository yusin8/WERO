import os
import sys
import tempfile
import wave
from typing import Optional

import requests
import numpy as np
import sounddevice as sd
from google.cloud import pubsub_v1
from google.cloud import texttospeech_v1 as tts


PROJECT_ID = os.environ.get("GCP_PROJECT", "we-robot-466007")
SUBSCRIPTION_ID = os.environ.get("VOICE_SUB", "voice-bridge-b")
FUNCTION_URL = os.environ.get("FUNCTION_URL", "")
TTS_VOICE = os.environ.get("TTS_VOICE", "ko-KR-Standard-A")
TTS_SPEAKING_RATE = float(os.environ.get("TTS_SPEAKING_RATE", "1.0"))
TTS_PITCH = float(os.environ.get("TTS_PITCH", "0.0"))
TTS_SAMPLE_RATE = int(os.environ.get("TTS_SAMPLE_RATE", "22050"))


def call_llm(prompt: str) -> Optional[str]:
    if not FUNCTION_URL:
        print("[B] FUNCTION_URL is not set.")
        return None
    try:
        r = requests.post(FUNCTION_URL, json={"prompt": prompt}, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("response")
    except Exception as e:
        print(f"[B] LLM call failed: {e}")
        return None


def tts_to_pcm(text: str, sample_rate: int) -> np.ndarray:
    client = tts.TextToSpeechClient()
    input_text = tts.SynthesisInput(text=text)
    voice = tts.VoiceSelectionParams(language_code="ko-KR", name=TTS_VOICE)
    audio_cfg = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        speaking_rate=TTS_SPEAKING_RATE,
        pitch=TTS_PITCH,
    )
    resp = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_cfg)
    # resp.audio_content is raw 16-bit PCM (mono) per LINEAR16
    pcm = np.frombuffer(resp.audio_content, dtype=np.int16)
    return pcm

def play_pcm(pcm: np.ndarray, sample_rate: int):
    sd.play(pcm, samplerate=sample_rate, blocking=True)


def main():
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("ERROR: Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON.")
        return 1

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    print(f"[B] Listening on {sub_path} -> {FUNCTION_URL}")

    def callback(message: pubsub_v1.subscriber.message.Message):
        try:
            text = message.data.decode("utf-8").strip()
            print(f"[B] Received: {text}")
            answer = call_llm(text)
            if not answer:
                print("[B] No answer; nack")
                message.nack()
                return
            print(f"[B] Answer: {answer}")
            pcm = tts_to_pcm(answer, sample_rate=TTS_SAMPLE_RATE)
            play_pcm(pcm, TTS_SAMPLE_RATE)
            message.ack()
        except Exception as e:
            print(f"[B] Error handling message: {e}")
            message.nack()

    streaming_pull_future = subscriber.subscribe(sub_path, callback=callback)
    print("[B] Waiting for messages... Press Ctrl+C to stop.")
    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        streaming_pull_future.result(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())

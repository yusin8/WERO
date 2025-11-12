import os
import sys
from typing import Tuple

import numpy as np
import sounddevice as sd
from google.cloud import speech_v1 as speech
from google.cloud import pubsub_v1


TOPIC_ID = os.environ.get("VOICE_TOPIC", "voice-bridge")
PROJECT_ID = os.environ.get("GCP_PROJECT", "we-robot-466007")


def record_audio(seconds: int = 5, sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
    print(f"[A] Recording {seconds}s at {sample_rate}Hz (mono)... Press Ctrl+C to cancel")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    return audio.flatten(), sample_rate


def transcribe(audio: np.ndarray, sample_rate: int) -> str:
    client = speech.SpeechClient()
    audio_bytes = audio.tobytes()
    audio_cfg = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code="ko-KR",
        sample_rate_hertz=sample_rate,
        enable_automatic_punctuation=True,
    )
    audio_in = speech.RecognitionAudio(content=audio_bytes)
    print("[A] Transcribing...")
    resp = client.recognize(config=audio_cfg, audio=audio_in)
    if not resp.results:
        return ""
    return resp.results[0].alternatives[0].transcript.strip()


def publish_text(project_id: str, topic_id: str, text: str) -> str:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    future = publisher.publish(topic_path, data=text.encode("utf-8"), source=b"A")
    msg_id = future.result(timeout=30)
    return msg_id


def main():
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("ERROR: Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON.")
        return 1

    seconds = int(os.environ.get("RECORD_SECONDS", "5"))
    audio, sr = record_audio(seconds=seconds)
    text = transcribe(audio, sr)
    if not text:
        print("[A] No speech recognized.")
        return 2
    print(f"[A] Recognized: {text}")
    msg_id = publish_text(PROJECT_ID, TOPIC_ID, text)
    print(f"[A] Published message id: {msg_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


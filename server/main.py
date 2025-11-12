import os
import functions_framework
import requests
from flask import jsonify

# Lazy init sentinel
initialized = False
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


@functions_framework.http
def ask_gemini(request):
    global initialized

    if not initialized:
        try:
            if not os.environ.get("GEMINI_API_KEY"):
                raise ValueError("GEMINI_API_KEY is not set (Secret Manager)")
            initialized = True
        except Exception as e:
            return jsonify({"error": f"Initialization failed: {e}"}), 500

    payload = request.get_json(silent=True) or {}
    if "prompt" not in payload:
        return jsonify({"error": "요청 본문에 'prompt'가 필요합니다."}), 400

    prompt = payload["prompt"]
    persona_prompt = (
        f"당신은 손주입니다. 70세 어르신에게 말하듯 공손하고 또박또박, "
        f"쉬운 한국어로 한두 문장 안에서 짧고 명확하게 답하세요. "
        f"어려운 용어와 이모지는 피하고 존댓말을 사용하세요. 질문: {prompt}"
    )

    try:
        key = os.environ["GEMINI_API_KEY"]
        url = f"{API_ENDPOINT}?key={key}"
        body = {"contents": [{"parts": [{"text": persona_prompt}]}]}
        r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if not text:
            return jsonify({"error": "Empty response from model"}), 502
        return jsonify({"response": text})
    except Exception as e:
        try:
            detail = r.text  # type: ignore
        except Exception:
            detail = str(e)
        return jsonify({"error": "Gemini API 요청 오류", "detail": detail}), 500

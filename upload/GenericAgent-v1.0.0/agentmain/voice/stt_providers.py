"""STT Providers — Speech-to-Text provider implementations.

Extracted from :mod:`agentmain.voice_avatar` (task 3.1.3) so that STT
implementations can be tested and extended independently.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger("agentmain.voice.stt_providers")


def transcribe_groq(audio_data: bytes, api_key: str = "", language: str = "fr") -> str:
    """Transcribe via Groq Whisper API (GRATUIT, 30 req/min)."""
    try:
        import requests
        api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            logger.debug("Pas de cle Groq — fallback Pollinations")
            return transcribe_pollinations(audio_data, language=language)

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        data = {"model": "whisper-large-v3", "language": language.split("-")[0]}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("text", "")
        logger.warning("Groq STT erreur %d: %s", resp.status_code, resp.text[:200])
        return ""
    except ImportError:
        return "[requests non installe]"


def transcribe_pollinations(audio_data: bytes, language: str = "fr") -> str:
    """Transcribe via Pollinations API (GRATUIT, illimite)."""
    try:
        import requests
        url = "https://text.pollinations.ai/openai/audio/transcriptions"
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        data = {"model": "whisper-1", "language": language.split("-")[0]}
        resp = requests.post(url, files=files, data=data, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("text", "")
        return ""
    except ImportError:
        return "[requests non installe]"


def transcribe_google(audio_data: bytes, api_key: str, language: str = "fr-FR") -> str:
    """Transcribe via Google Speech-to-Text REST API (payant)."""
    try:
        import requests
        audio_b64 = base64.b64encode(audio_data).decode()
        url = "https://speech.googleapis.com/v1/speech:recognize"
        headers = {"x-goog-api-key": api_key}
        payload = {
            "config": {
                "encoding": "LINEAR16",
                "sampleRateHertz": 16000,
                "languageCode": language,
            },
            "audio": {"content": audio_b64},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                alternatives = results[0].get("alternatives", [])
                if alternatives:
                    return alternatives[0].get("transcript", "")
        return ""
    except ImportError:
        return "[requests non installe]"


def transcribe_openai(audio_data: bytes, api_key: str, language: str = "fr") -> str:
    """Transcribe via OpenAI Whisper API (payant)."""
    try:
        import requests
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        data = {"model": "whisper-1", "language": language.split("-")[0]}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("text", "")
        return ""
    except ImportError:
        return "[requests non installe]"


def transcribe_whisper_local(audio_data: bytes) -> str:
    """Transcribe via Whisper local (GRATUIT, requires GPU)."""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_data)
        return result.get("text", "")
    except ImportError:
        return "[Whisper non installe - pip install openai-whisper]"

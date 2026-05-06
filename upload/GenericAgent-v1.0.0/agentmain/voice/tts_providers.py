"""TTS Providers — Text-to-Speech provider implementations.

Extracted from :mod:`agentmain.voice_avatar` (task 3.1.3) so that TTS
implementations can be tested and extended independently.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger("agentmain.voice.tts_providers")

# Voice models by language (for Edge TTS)
EDGE_VOICES = {
    "fr-FR": {
        "female": "fr-FR-DeniseNeural",
        "male": "fr-FR-HenriNeural",
        "anime": "fr-FR-DeniseNeural",
    },
    "en-US": {
        "female": "en-US-JennyNeural",
        "male": "en-US-GuyNeural",
        "anime": "en-US-AriaNeural",
    },
    "zh-CN": {
        "female": "zh-CN-XiaoxiaoNeural",
        "male": "zh-CN-YunxiNeural",
        "anime": "zh-CN-XiaoyiNeural",
    },
    "ja-JP": {
        "female": "ja-JP-NanamiNeural",
        "male": "ja-JP-KeitaNeural",
        "anime": "ja-JP-NanamiNeural",
    },
}


def synthesize_edge(text: str, voice_id: str = "", voice_style: str = "anime",
                    language: str = "fr-FR") -> bytes:
    """Synthesize via Microsoft Edge TTS (GRATUIT, 400+ voix)."""
    try:
        import edge_tts

        if voice_id:
            selected_voice = voice_id
        else:
            voices_for_lang = EDGE_VOICES.get(language, EDGE_VOICES["en-US"])
            style_key = voice_style if voice_style in voices_for_lang else "anime"
            selected_voice = voices_for_lang.get(style_key, voices_for_lang["female"])

        communicate = edge_tts.Communicate(text[:5000], selected_voice)
        audio_buffer = io.BytesIO()
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def _synth():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _synth())
                future.result(timeout=30)
        else:
            asyncio.run(_synth())

        audio_bytes = audio_buffer.getvalue()
        if audio_bytes:
            logger.debug("Edge TTS : %d bytes generes (voix=%s)", len(audio_bytes), selected_voice)
        return audio_bytes

    except ImportError:
        logger.warning("edge-tts non installe — fallback Pollinations TTS")
        return synthesize_pollinations(text, voice_id, voice_style)
    except Exception as e:
        logger.error("Edge TTS erreur : %s", e)
        return b""


def synthesize_voicevox(text: str, voice_id: str = "", voice_style: str = "anime") -> bytes:
    """Synthesize via VOICEVOX Engine (GRATUIT, local, voix anime japonaise)."""
    try:
        import requests
        anime_speakers = {"anime": 1, "zundamon": 2, "tsumugi": 3, "ritsu": 8}
        speaker_id = anime_speakers.get(voice_style, 1)

        url = f"http://localhost:50021/audio_query?text={text[:5000]}&speaker={speaker_id}"
        resp = requests.post(url, timeout=10)
        if resp.status_code == 200:
            query = resp.json()
            synth_url = f"http://localhost:50021/synthesis?speaker={speaker_id}"
            synth_resp = requests.post(synth_url, json=query, timeout=30)
            if synth_resp.status_code == 200:
                return synth_resp.content
        return b""
    except ImportError:
        return b""
    except Exception as e:
        logger.debug("VOICEVOX non disponible (local:50021) : %s", e)
        return b""


def synthesize_pollinations(text: str, voice_id: str = "", voice_style: str = "anime") -> bytes:
    """Synthesize via Pollinations TTS (GRATUIT, illimite)."""
    try:
        import requests
        url = "https://text.pollinations.ai/openai/audio/speech"
        payload = {
            "model": "tts-1",
            "input": text[:4096],
            "voice": voice_id or "alloy",
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.content
        return b""
    except ImportError:
        return b""


def synthesize_google(text: str, api_key: str, voice_id: str = "",
                      language: str = "fr-FR") -> bytes:
    """Synthesize via Google Cloud TTS (payant)."""
    try:
        import requests
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        headers = {"x-goog-api-key": api_key}
        payload = {
            "input": {"text": text[:5000]},
            "voice": {"languageCode": language, "name": voice_id if voice_id and voice_id != "default" else f"{language}-Standard-A"},
            "audioConfig": {"audioEncoding": "LINEAR16"},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            audio_b64 = resp.json().get("audioContent", "")
            if audio_b64:
                return base64.b64decode(audio_b64)
        return b""
    except ImportError:
        return b""


def synthesize_openai(text: str, api_key: str, voice_id: str = "") -> bytes:
    """Synthesize via OpenAI TTS API (payant)."""
    try:
        import requests
        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"model": "tts-1", "input": text[:4096], "voice": voice_id or "alloy"}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.content
        return b""
    except ImportError:
        return b""


def synthesize_elevenlabs(text: str, api_key: str = "", voice_id: str = "") -> bytes:
    """Synthesize via ElevenLabs TTS (~10k chars/mois gratuit)."""
    try:
        import requests
        api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            return b""
        vid = voice_id or "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
        headers = {"xi-api-key": api_key}
        payload = {"text": text[:5000], "model_id": "eleven_monolingual_v1"}
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.content
        return b""
    except ImportError:
        return b""

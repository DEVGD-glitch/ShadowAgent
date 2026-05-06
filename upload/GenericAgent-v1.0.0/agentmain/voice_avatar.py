"""GenericAgent v0.6.0 — Voice & Avatar Pipeline : STT/TTS/VRM + VRoid Hub.

Facade module — re-exports from extracted sub-modules:

  - :mod:`agentmain.voice.stt_providers` — STT provider implementations
  - :mod:`agentmain.voice.tts_providers` — TTS provider implementations
  - :mod:`agentmain.voice.avatar_controller` — VRM/VRoid avatar controller

This file retains the top-level enums, constants, :class:`VoicePipeline`,
:class:`LLMVoiceClient`, and :class:`VADProcessor` for backward
compatibility.  Import paths like ``from agentmain.voice_avatar import
VoicePipeline`` continue to work unchanged.

Architecture inspiree de AIAvatarKit (uezo/aiavatarkit) :
  - Pipeline VAD -> STT -> LLM -> TTS -> Avatar complet
  - Provider-agnostic avec support providers GRATUITS
  - Avatar VRM/VRoid avec rendu client-side (Three.js + @pixiv/three-vrm)
  - Lip-sync base sur l'analyse audio (RMS + spectral centroid)
  - Expressions faciales via tags [face:joy] dans la reponse LLM
  - Interruption (barge-in) pour conversation naturelle
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Sequence, Tuple

logger = logging.getLogger("ga.agentmain.voice_avatar")

# Re-export extracted sub-modules for convenience
from agentmain.voice.stt_providers import (
    transcribe_groq,
    transcribe_pollinations,
    transcribe_google,
    transcribe_openai,
    transcribe_whisper_local,
)
from agentmain.voice.tts_providers import (
    synthesize_edge,
    synthesize_voicevox,
    synthesize_pollinations as _synthesize_pollinations_tts,
    synthesize_google as _synthesize_google_tts,
    synthesize_openai as _synthesize_openai_tts,
    synthesize_elevenlabs,
    EDGE_VOICES,
)
from agentmain.voice.avatar_controller import AvatarController


# ══════════════════════════════════════════════════════════════════════════════
#  Providers STT/TTS — Enums
# ══════════════════════════════════════════════════════════════════════════════

class STTProvider(Enum):
    """Fournisseurs de Speech-to-Text."""
    GROQ = "groq"
    POLLINATIONS = "pollinations"
    GOOGLE = "google"
    OPENAI = "openai"
    AZURE = "azure"
    LOCAL_WHISPER = "local_whisper"


class TTSProvider(Enum):
    """Fournisseurs de Text-to-Speech."""
    EDGE = "edge"
    VOICEVOX = "voicevox"
    POLLINATIONS = "pollinations"
    GOOGLE = "google"
    OPENAI = "openai"
    AZURE = "azure"
    ELEVENLABS = "elevenlabs"


class LLMVoiceProvider(Enum):
    """Fournisseurs LLM pour le pipeline vocal (gratuits prioritairement)."""
    POLLINATIONS = "pollinations"
    GROQ = "groq"
    UNCLOSEAI = "uncloseai"
    DEEPINFRA = "deepinfra"
    OPENROUTER = "openrouter"
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL_OLLAMA = "ollama"


# ══════════════════════════════════════════════════════════════════════════════
#  Modeles de voix et modeles LLM gratuits
# ══════════════════════════════════════════════════════════════════════════════

POLLINATIONS_MODELS = [
    "gemini-2.5-flash", "gpt-4o", "gpt-4o-mini", "mistral", "llama",
    "qwen-coder", "deepseek", "command-r",
]

GROQ_MODELS = [
    "llama-4-scout-17b-16e-instruct", "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768", "gemma2-9b-it",
]


# ══════════════════════════════════════════════════════════════════════════════
#  VoicePipeline — Pipeline vocal provider-agnostic
# ══════════════════════════════════════════════════════════════════════════════

class VoicePipeline:
    """Pipeline vocal provider-agnostic pour STT et TTS.

    Delegates STT/TTS calls to the extracted provider functions in
    :mod:`agentmain.voice.stt_providers` and
    :mod:`agentmain.voice.tts_providers`.
    """

    def __init__(self, stt_provider: STTProvider = STTProvider.GROQ,
                 tts_provider: TTSProvider = TTSProvider.EDGE,
                 api_key: str = "",
                 language: str = "fr-FR") -> None:
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self._api_key = api_key
        self._language = language
        self._stt_config: Dict[str, Any] = {"language": language}
        self._tts_config: Dict[str, Any] = {"language": language, "voice_style": "anime"}
        logger.info("VoicePipeline initialise (STT=%s, TTS=%s, lang=%s)",
                     stt_provider.value, tts_provider.value, language)

    def transcribe(self, audio_data: bytes) -> str:
        """Transcrit l'audio en texte."""
        logger.debug("Transcription audio (%d bytes)", len(audio_data))
        lang = self._language.split("-")[0]
        dispatch = {
            STTProvider.GROQ: lambda: transcribe_groq(audio_data, self._api_key, lang),
            STTProvider.POLLINATIONS: lambda: transcribe_pollinations(audio_data, lang),
            STTProvider.GOOGLE: lambda: transcribe_google(audio_data, self._api_key, self._language),
            STTProvider.OPENAI: lambda: transcribe_openai(audio_data, self._api_key, lang),
            STTProvider.LOCAL_WHISPER: lambda: transcribe_whisper_local(audio_data),
        }
        handler = dispatch.get(self.stt_provider, lambda: transcribe_groq(audio_data, self._api_key, lang))
        return handler()

    def synthesize(self, text: str, voice_id: str = "", voice_style: str = "") -> bytes:
        """Synthetise le texte en audio."""
        style = voice_style or self._tts_config.get("voice_style", "anime")
        logger.debug("Synthese TTS (%d caracteres, style=%s)", len(text), style)
        dispatch = {
            TTSProvider.EDGE: lambda: synthesize_edge(text, voice_id, style, self._language),
            TTSProvider.VOICEVOX: lambda: synthesize_voicevox(text, voice_id, style),
            TTSProvider.POLLINATIONS: lambda: _synthesize_pollinations_tts(text, voice_id, style),
            TTSProvider.GOOGLE: lambda: _synthesize_google_tts(text, self._api_key, voice_id, self._language),
            TTSProvider.OPENAI: lambda: _synthesize_openai_tts(text, self._api_key, voice_id),
            TTSProvider.ELEVENLABS: lambda: synthesize_elevenlabs(text, self._api_key, voice_id),
        }
        handler = dispatch.get(self.tts_provider, lambda: synthesize_edge(text, voice_id, style, self._language))
        return handler()

    def set_stt_provider(self, provider: STTProvider) -> None:
        self.stt_provider = provider
        logger.info("STT provider change : %s", provider.value)

    def set_tts_provider(self, provider: TTSProvider) -> None:
        self.tts_provider = provider
        logger.info("TTS provider change : %s", provider.value)


# ══════════════════════════════════════════════════════════════════════════════
#  LLMVoiceClient — Client LLM pour le pipeline vocal (providers gratuits)
# ══════════════════════════════════════════════════════════════════════════════

class LLMVoiceClient:
    """Client LLM optimise pour le pipeline vocal avec providers gratuits."""

    def __init__(self, provider: LLMVoiceProvider = LLMVoiceProvider.POLLINATIONS,
                 api_key: str = "", model: str = "") -> None:
        self.provider = provider
        self._api_key = api_key
        self._model = model
        self._conversation: List[Dict[str, str]] = []
        self._system_prompt = "Tu es un assistant anime cute et serviable. Reponds de maniere concise et mignonne."
        logger.info("LLMVoiceClient initialise (provider=%s)", provider.value)

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def set_personality(self, personality: str) -> None:
        """Definit la personnalite de l'avatar anime."""
        personalities = {
            "waifu": "Tu es une waifu anime affectueuse et devouee. Tu t'adresses a l'utilisateur avec des termes mignons. Tu es toujours attentionnee et bienveillante.",
            "tsundere": "Tu es une tsundere anime. Tu es d'abord froide et denies tes sentiments, mais tu montres ta douceur par moments. Utilise des expressions comme 'B-baka!' ou 'C'est pas comme si je tenais a toi...'",
            "kuudere": "Tu es une kuudere anime. Tu es calme, stoique et reservee. Tu parles peu mais tes mots sont pleins de sens. Tu montres tes emotions subtilement.",
            "dandere": "Tu es une dandere anime. Tu es timide et reservee au debut, mais tu deviens tres affectueuse une fois que tu connais quelqu'un. Tu rougis souvent.",
            "genki": "Tu es une genki girl anime! Tu es energetique, joyeuse et toujours positive! Tu parles avec beaucoup d'enthousiasme et d'exclamation!",
            "oneesan": "Tu es une oneesan anime. Tu es mature, elegante et protectrice. Tu traites l'utilisateur avec douceur et sagesse, comme une grande sour.",
            "loli": "Tu es un personnage anime petite et mignonne. Tu parles avec une voix aigue et utilises des onomatopees. Tu es curieuse et espiègle.",
        }
        self._system_prompt = personalities.get(personality, personalities["waifu"])

    def chat(self, user_message: str) -> str:
        """Envoie un message et retourne la reponse."""
        self._conversation.append({"role": "user", "content": user_message})
        dispatch = {
            LLMVoiceProvider.POLLINATIONS: self._chat_pollinations,
            LLMVoiceProvider.GROQ: self._chat_groq,
            LLMVoiceProvider.UNCLOSEAI: self._chat_uncloseai,
            LLMVoiceProvider.DEEPINFRA: self._chat_deepinfra,
            LLMVoiceProvider.OPENROUTER: self._chat_openrouter,
            LLMVoiceProvider.GOOGLE: self._chat_google,
            LLMVoiceProvider.OPENAI: self._chat_openai,
            LLMVoiceProvider.ANTHROPIC: self._chat_anthropic,
            LLMVoiceProvider.LOCAL_OLLAMA: self._chat_ollama,
        }
        handler = dispatch.get(self.provider, self._chat_pollinations)
        response = handler(user_message)
        self._conversation.append({"role": "assistant", "content": response})
        return response

    def clear_history(self) -> None:
        self._conversation.clear()

    # ── LLM Implementations ──────────────────────────────────────────────

    def _chat_pollinations(self, message: str) -> str:
        try:
            import requests
            model = self._model or "openai"
            url = f"https://text.pollinations.ai/openai/chat/completions"
            payload = {"model": model, "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur Pollinations]"
        except ImportError:
            return "[requests non installe]"

    def _chat_groq(self, message: str) -> str:
        try:
            import requests
            api_key = self._api_key or os.environ.get("GROQ_API_KEY", "")
            if not api_key:
                return self._chat_pollinations(message)
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": self._model or "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur Groq]"
        except ImportError:
            return "[requests non installe]"

    def _chat_uncloseai(self, message: str) -> str:
        try:
            import requests
            url = "https://uncloseai.com/v1/chat/completions"
            payload = {"model": self._model or "hermes-3-llama-3.1-8b", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur UncloseAI]"
        except ImportError:
            return "[requests non installe]"

    def _chat_deepinfra(self, message: str) -> str:
        try:
            import requests
            api_key = self._api_key or os.environ.get("DEEPINFRA_API_KEY", "")
            url = "https://api.deepinfra.com/v1/openai/chat/completions"
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {"model": self._model or "meta-llama/Meta-Llama-3.1-8B-Instruct", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur DeepInfra]"
        except ImportError:
            return "[requests non installe]"

    def _chat_openrouter(self, message: str) -> str:
        try:
            import requests
            api_key = self._api_key or os.environ.get("OPENROUTER_API_KEY", "")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {"model": self._model or "meta-llama/llama-3.1-8b-instruct:free", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur OpenRouter]"
        except ImportError:
            return "[requests non installe]"

    def _chat_google(self, message: str) -> str:
        try:
            import requests
            api_key = self._api_key or os.environ.get("GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model or 'gemini-2.5-flash'}:generateContent"
            headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": m["content"]} for m in [{"role": "user", "content": self._system_prompt + "\n\n" + message}]]}]}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                candidates = resp.json().get("candidates", [])
                if candidates:
                    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return "[Erreur Google]"
        except ImportError:
            return "[requests non installe]"

    def _chat_openai(self, message: str) -> str:
        try:
            import requests
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self._api_key}"}
            payload = {"model": self._model or "gpt-4o-mini", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "max_tokens": 500}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return "[Erreur OpenAI]"
        except ImportError:
            return "[requests non installe]"

    def _chat_anthropic(self, message: str) -> str:
        try:
            import requests
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            payload = {"model": self._model or "claude-sonnet-4-20250514", "max_tokens": 500, "system": self._system_prompt, "messages": self._conversation[-10:]}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                content = resp.json().get("content", [])
                if content:
                    return content[0].get("text", "")
            return "[Erreur Anthropic]"
        except ImportError:
            return "[requests non installe]"

    def _chat_ollama(self, message: str) -> str:
        try:
            import requests
            url = "http://localhost:11434/api/chat"
            payload = {"model": self._model or "llama3", "messages": [{"role": "system", "content": self._system_prompt}] + self._conversation[-10:], "stream": False}
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "")
            return "[Erreur Ollama]"
        except ImportError:
            return "[requests non installe]"
        except Exception:
            return "[Ollama non disponible sur localhost:11434]"


# ══════════════════════════════════════════════════════════════════════════════
#  VADProcessor — Voice Activity Detection
# ══════════════════════════════════════════════════════════════════════════════

class VADProcessor:
    """Detecteur d'activite vocale (Voice Activity Detection).

    Supporte deux modes :
      - RMS : Simple calcul d'amplitude (pas de dependance)
      - Silero : Modele deep learning (plus precis, pip install silero-vad)
    """

    def __init__(self, silence_threshold: float = 0.01,
                 min_speech_duration: float = 0.3,
                 use_silero: bool = False) -> None:
        self.silence_threshold = silence_threshold
        self.min_speech_duration = min_speech_duration
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._silero_model = None
        if use_silero:
            self._init_silero()
        logger.info("VADProcessor initialise (threshold=%.3f, min_duration=%.1fs, silero=%s)",
                     silence_threshold, min_speech_duration, use_silero)

    def _init_silero(self):
        try:
            import torch
            self._silero_model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True,
            )
            logger.info("Silero VAD charge avec succes")
        except ImportError:
            logger.info("PyTorch non installe — fallback au VAD RMS")
        except Exception as e:
            logger.debug("Silero VAD non disponible : %s", e)

    def detect_speech(self, audio_chunk: bytes, sample_rate: int = 16000,
                      sample_width: int = 2) -> bool:
        if not audio_chunk:
            return False
        if self._silero_model is not None:
            return self._detect_silero(audio_chunk, sample_rate)
        return self._detect_rms(audio_chunk, sample_rate, sample_width)

    def _detect_silero(self, audio_chunk: bytes, sample_rate: int) -> bool:
        try:
            import torch
            import numpy as np
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            tensor = torch.from_numpy(audio_array)
            speech_prob = self._silero_model(tensor, sample_rate).item()
            is_speech = speech_prob > 0.5
            if is_speech and not self._is_speaking:
                self._speech_start_time = time.monotonic()
                self._is_speaking = True
            elif not is_speech and self._is_speaking:
                self._is_speaking = False
            return is_speech
        except Exception:
            return self._detect_rms(audio_chunk, sample_rate, 2)

    def _detect_rms(self, audio_chunk: bytes, sample_rate: int, sample_width: int) -> bool:
        try:
            num_samples = len(audio_chunk) // sample_width
            if num_samples == 0:
                return False
            total = 0
            for i in range(0, min(len(audio_chunk), sample_width * num_samples), sample_width):
                if sample_width == 2:
                    sample = struct.unpack_from("<h", audio_chunk, i)[0]
                    total += sample * sample
            rms = (total / num_samples) ** 0.5 / 32768.0
            is_speech = rms > self.silence_threshold
            if is_speech and not self._is_speaking:
                self._speech_start_time = time.monotonic()
                self._is_speaking = True
            elif not is_speech and self._is_speaking:
                self._is_speaking = False
            return is_speech
        except Exception as e:
            logger.debug("Erreur VAD : %s", e)
            return False

    def process_stream(self, audio_stream: Iterator[bytes],
                       sample_rate: int = 16000) -> Iterator[bytes]:
        for chunk in audio_stream:
            if self.detect_speech(chunk, sample_rate):
                yield chunk

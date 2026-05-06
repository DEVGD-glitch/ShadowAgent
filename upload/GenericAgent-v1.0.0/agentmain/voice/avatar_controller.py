"""Avatar Controller — VRM/VRoid avatar with lip-sync and expressions.

Extracted from :mod:`agentmain.voice_avatar` (task 3.1.3) so that avatar
logic can be tested and extended independently.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("agentmain.voice.avatar_controller")


class AvatarController:
    """Controleur d'avatar VRM/VRoid avec lip-sync et expressions.

    Architecture inspiree de AIAvatarKit :
      - Rendu VRM cote client (JavaScript + Three.js + @pixiv/three-vrm)
      - Le controleur Python envoie des commandes d'expression/animation
      - Lip-sync base sur l'analyse audio (RMS + spectral centroid)
      - Expressions via tags [face:joy] dans la reponse LLM

    Le rendu se fait dans un navigateur (ou webview) qui charge le fichier
    HTML/JS dedie dans assets/avatar_viewer.html. La communication se fait
    via WebSocket entre le serveur Python et le client navigateur.

    Attributes:
        avatar_path: Chemin vers le fichier VRM de l'avatar
        viewer_url: URL du viewer HTML (defaut: assets/avatar_viewer.html)
    """

    # Expressions VRM standard (BlendShape) — correspondance AIAvatarKit
    EXPRESSIONS = [
        "neutral", "happy", "angry", "sad", "surprised",
        "relaxed", "thinking", "blink", "blink_left", "blink_right",
        "aa", "ih", "ou", "ee", "oh",  # Visemes pour lip-sync
    ]

    # Correspondance nom d'expression -> nom VRM BlendShape
    EXPRESSION_MAP = {
        "happy": "Joy", "angry": "Angry", "sad": "Sorrow",
        "surprised": "Surprised", "relaxed": "Relaxed",
        "thinking": "Neutral", "neutral": "Neutral",
        "blink": "Blink", "blink_left": "Blink_L", "blink_right": "Blink_R",
        # Visemes
        "aa": "A", "ih": "I", "ou": "U", "ee": "E", "oh": "O",
    }

    # Correspondance tags LLM -> expression (style AIAvatarKit)
    TAG_MAP = {
        "joy": "happy", "smile": "happy", "laugh": "happy",
        "angry": "angry", "mad": "angry",
        "sad": "sad", "cry": "sad", "tears": "sad",
        "surprise": "surprised", "shock": "surprised",
        "think": "thinking", "hmm": "thinking",
        "relax": "relaxed", "calm": "relaxed",
        "neutral": "neutral",
    }

    def __init__(self, avatar_path: str = "") -> None:
        self.avatar_path = avatar_path
        self._current_expression = "neutral"
        self._available_avatars: List[Dict[str, str]] = []
        self._lip_sync_values: Dict[str, float] = {}
        self._ws_clients: List[Any] = []  # WebSocket clients
        logger.info("AvatarController initialise (avatar: %s)",
                     avatar_path or "aucun")

    def set_expression(self, expression_name: str) -> None:
        """Definit l'expression faciale de l'avatar."""
        if expression_name not in self.EXPRESSIONS:
            mapped = self.TAG_MAP.get(expression_name.lower())
            if mapped:
                expression_name = mapped
            else:
                logger.warning("Expression inconnue : %s", expression_name)
                return
        self._current_expression = expression_name
        self._broadcast({"type": "expression", "name": expression_name})
        logger.debug("Expression changee : %s", expression_name)

    def parse_expression_tags(self, text: str) -> Tuple[str, str]:
        """Extrait les tags d'expression [face:xxx] du texte LLM.

        Style AIAvatarKit : le LLM peut inserer [face:joy] dans sa reponse.

        Args:
            text: Texte de reponse du LLM

        Returns:
            Tuple (texte_nettoye, expression_trouvee)
        """
        pattern = r'\[face:(\w+)\]'
        matches = re.findall(pattern, text)
        clean_text = re.sub(pattern, '', text).strip()

        if matches:
            tag = matches[-1].lower()
            expression = self.TAG_MAP.get(tag, "neutral")
            return clean_text, expression
        return text, self._current_expression

    def set_lip_sync(self, viseme_data: Dict[str, float]) -> None:
        """Definit les valeurs de synchronisation labiale."""
        self._lip_sync_values = viseme_data
        self._broadcast({"type": "viseme", "data": viseme_data})

    def compute_lip_sync_from_audio(self, audio_data: bytes, sample_rate: int = 24000) -> Dict[str, float]:
        """Calcule les visemes a partir de donnees audio.

        Methode inspiree de AIAvatarKit LipSyncEngine :
          - RMS -> ouverture de la bouche
          - Spectral centroid -> forme de voyelle
        """
        import struct
        import numpy as np

        if not audio_data:
            return {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}

        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            if len(audio_array) == 0:
                return {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}

            # RMS -> mouth open amount
            rms = float(np.sqrt(np.mean(audio_array ** 2)))
            mouth_open = min(rms * 10.0, 1.0)

            # Spectral centroid -> vowel shape
            fft = np.fft.rfft(audio_array)
            magnitudes = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio_array), 1.0 / sample_rate)
            if magnitudes.sum() > 0:
                centroid = float(np.sum(freqs * magnitudes) / np.sum(magnitudes))
            else:
                centroid = 0.0

            # Map centroid to viseme blend
            if centroid < 800:
                visemes = {"aa": mouth_open, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
            elif centroid < 1500:
                visemes = {"aa": 0.0, "ih": mouth_open, "ou": 0.0, "ee": 0.0, "oh": 0.0}
            elif centroid < 2500:
                visemes = {"aa": 0.0, "ih": 0.0, "ou": mouth_open, "ee": 0.0, "oh": 0.0}
            elif centroid < 3500:
                visemes = {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": mouth_open, "oh": 0.0}
            else:
                visemes = {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": mouth_open}

            return visemes
        except ImportError:
            logger.debug("numpy non disponible pour lip-sync")
            return {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
        except Exception as e:
            logger.debug("Erreur lip-sync : %s", e)
            return {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}

    def _broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSocket clients."""
        import json
        data = json.dumps(message)
        dead = []
        for ws in self._ws_clients:
            try:
                ws.send(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_clients.remove(ws)

    @property
    def current_expression(self) -> str:
        return self._current_expression

    def register_ws_client(self, ws: Any) -> None:
        """Register a WebSocket client for avatar commands."""
        self._ws_clients.append(ws)

    def unregister_ws_client(self, ws: Any) -> None:
        """Unregister a WebSocket client."""
        try:
            self._ws_clients.remove(ws)
        except ValueError:
            pass

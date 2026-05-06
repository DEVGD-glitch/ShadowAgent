"""
Gestionnaire de streaming pour les réponses LLM.

Extrait de la classe ChatPanel (qtapp.py) lors de la refonte modulaire
(Phase 3). Ce module isole toute la logique de gestion de la file
d'affichage, de l'état de streaming et du cycle send/stop, afin de
découpler le traitement des données du rendu Qt.

Le ``StreamHandler`` fonctionne selon un motif à callbacks : la couche
UI (ChatPanel) fournit des fonctions appelées respectivement à chaque
chunk reçu, à la fin du stream, et pour les événements spéciaux
(tool_call, tool_result, thinking). Aucune dépendance Qt directe n'est
nécessaire — seule la logique pure de coordination est implémentée ici.

Phase 7 : Ajout du support pour les événements tool_call, tool_result,
thinking_start et thinking_end.
"""
from __future__ import annotations

import queue
import logging
from typing import Optional, Callable

from frontends.qt.utils import _build_prompt_with_uploads

logger = logging.getLogger(__name__)


class StreamHandler:
    """Gestionnaire de streaming pour les réponses LLM.

    Centralise l'état et la logique liés au streaming des réponses de
    l'agent : démarrage, interrogation de la file d'affichage, arrêt et
    suivi du texte accumulé. La communication avec la couche UI se fait
    exclusivement via les callbacks.

    Attributes
    ----------
    _display_queue : Optional[queue.Queue]
        File d'affichage retournée par ``agent.put_task()``.
    _streaming_text : str
        Texte accumulé au fil du streaming.
    _is_streaming : bool
        Indique si un stream est actuellement en cours.
    """

    # Fréquence de polling par défaut (ms). Le propriétaire du timer
    # peut utiliser cette constante comme intervalle de référence.
    POLL_INTERVAL_MS: int = 40

    def __init__(
        self,
        on_stream_chunk: Callable[[str], None],
        on_stream_done: Callable[[str, bool], None],
        on_tool_call: Optional[Callable[[dict], None]] = None,
        on_tool_result: Optional[Callable[[dict], None]] = None,
        on_thinking_start: Optional[Callable[[dict], None]] = None,
        on_thinking_end: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """
        Parameters
        ----------
        on_stream_chunk : Callable[[str], None]
            Callback appelé pour chaque chunk de streaming.
        on_stream_done : Callable[[str, bool], None]
            Callback appelé quand le streaming est terminé.
            Le second argument ``is_interrupted`` vaut ``True`` quand
            l'utilisateur a arrêté le stream manuellement.
        on_tool_call : Callable[[dict], None] | None
            Callback appelé quand un appel d'outil est détecté.
            Le dict contient : {'name': str, 'args': dict, 'id': str}
        on_tool_result : Callable[[dict], None] | None
            Callback appelé quand un résultat d'outil est reçu.
            Le dict contient : {'id': str, 'status': str, 'data': Any}
        on_thinking_start : Callable[[dict], None] | None
            Callback appelé quand le raisonnement commence.
        on_thinking_end : Callable[[dict], None] | None
            Callback appelé quand le raisonnement se termine.
            Le dict peut contenir : {'duration': float, 'content': str}
        """
        self._display_queue: Optional[queue.Queue] = None
        self._streaming_text: str = ""
        self._is_streaming: bool = False
        self._on_stream_chunk: Callable[[str], None] = on_stream_chunk
        self._on_stream_done: Callable[[str, bool], None] = on_stream_done
        self._on_tool_call: Optional[Callable[[dict], None]] = on_tool_call
        self._on_tool_result: Optional[Callable[[dict], None]] = on_tool_result
        self._on_thinking_start: Optional[Callable[[dict], None]] = on_thinking_start
        self._on_thinking_end: Optional[Callable[[dict], None]] = on_thinking_end

    # ── Propriétés ──────────────────────────────────────────────────────────

    @property
    def is_streaming(self) -> bool:
        """Indique si un stream LLM est en cours."""
        return self._is_streaming

    @property
    def streaming_text(self) -> str:
        """Texte accumulé pendant le stream en cours."""
        return self._streaming_text

    # ── Démarrage du stream ─────────────────────────────────────────────────

    def start_stream(
        self,
        agent: object,
        prompt: str,
        files: list[dict],
    ) -> None:
        """Démarre un stream LLM avec le prompt et les fichiers joints."""
        full_prompt, _, _ = _build_prompt_with_uploads(prompt, files)
        self._streaming_text = ""
        self._is_streaming = True
        self._display_queue = agent.put_task(full_prompt, source="user")
        logger.debug("Stream démarré — file d'affichage créée")

    # ── Polling de la file ──────────────────────────────────────────────────

    def poll_queue(self) -> list[dict]:
        """Interroge la file d'affichage et retourne les éléments disponibles.

        Items supportés :
        - ``{'next': str}`` — chunk de progression
        - ``{'done': str}`` — texte final
        - ``{'tool_call': dict}`` — appel d'outil (Phase 7)
        - ``{'tool_result': dict}`` — résultat d'outil (Phase 7)
        - ``{'thinking_start': dict}`` — début de raisonnement (Phase 7)
        - ``{'thinking_end': dict}`` — fin de raisonnement (Phase 7)
        """
        if self._display_queue is None:
            return []

        items: list[dict] = []

        try:
            while True:
                item = self._display_queue.get_nowait()
                items.append(item)

                # ── Chunk de progression ──
                if "next" in item:
                    self._streaming_text = item["next"]
                    try:
                        self._on_stream_chunk(self._streaming_text)
                    except Exception:
                        logger.exception("Erreur dans le callback on_stream_chunk")

                # ── Fin du stream ──
                if "done" in item:
                    final_text: str = item["done"]
                    self._streaming_text = final_text
                    self._is_streaming = False
                    self._display_queue = None
                    try:
                        self._on_stream_done(final_text, is_interrupted=False)
                    except Exception:
                        logger.exception("Erreur dans le callback on_stream_done")
                    logger.debug("Stream terminé — texte final reçu")
                    break

                # ── Phase 7 : Tool call event ──
                if "tool_call" in item and self._on_tool_call:
                    try:
                        self._on_tool_call(item["tool_call"])
                    except Exception:
                        logger.exception("Erreur dans le callback on_tool_call")

                # ── Phase 7 : Tool result event ──
                if "tool_result" in item and self._on_tool_result:
                    try:
                        self._on_tool_result(item["tool_result"])
                    except Exception:
                        logger.exception("Erreur dans le callback on_tool_result")

                # ── Phase 7 : Thinking start event ──
                if "thinking_start" in item and self._on_thinking_start:
                    try:
                        self._on_thinking_start(item["thinking_start"])
                    except Exception:
                        logger.exception("Erreur dans le callback on_thinking_start")

                # ── Phase 7 : Thinking end event ──
                if "thinking_end" in item and self._on_thinking_end:
                    try:
                        self._on_thinking_end(item["thinking_end"])
                    except Exception:
                        logger.exception("Erreur dans le callback on_thinking_end")

        except queue.Empty:
            pass

        return items

    # ── Arrêt du stream ─────────────────────────────────────────────────────

    def stop_stream(self, agent: object) -> None:
        """Arrête le stream en cours de force.

        Marque le message comme interrompu (``is_interrupted=True``)
        afin que la couche UI puisse l'afficher différemment et que
        l'historique l'exclue du contexte envoyé au LLM.
        """
        if not self._is_streaming:
            logger.debug("stop_stream appelé mais aucun stream en cours")
            return

        try:
            agent.abort()
        except Exception:
            logger.exception("Erreur lors de l'abandon de l'agent")

        self._is_streaming = False
        self._display_queue = None

        final_text = self._streaming_text or "(Arrêté)"
        try:
            self._on_stream_done(final_text, is_interrupted=True)
        except Exception:
            logger.exception("Erreur dans le callback on_stream_done (stop)")

        logger.debug("Stream arrêté manuellement")

    # ── Réinitialisation ────────────────────────────────────────────────────

    def reset(self) -> None:
        """Réinitialise l'état du gestionnaire sans appeler les callbacks."""
        self._display_queue = None
        self._streaming_text = ""
        self._is_streaming = False
        logger.debug("StreamHandler réinitialisé")

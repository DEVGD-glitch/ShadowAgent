"""Système de métriques pour le suivi des appels LLM.

Ce module fournit un singleton :class:`Metrics` permettant de collecter
des statistiques sur les appels LLM : tokens consommés, latences,
compteurs d'erreurs et de requêtes.  Toutes les opérations sont
thread-safe.

Il inclut également le gestionnaire de contexte :class:`MetricsTimer`
pour mesurer automatiquement la latence d'un appel LLM.

Aucune dépendance externe n'est requise au-delà de la bibliothèque
standard.

Public API
----------
Metrics, MetricsTimer
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Any

# Maximum number of latency samples retained per model.
# Older entries are discarded automatically (ring buffer).
MAX_LATENCIES: int = 10_000


# ---------------------------------------------------------------------------
# Métriques — Singleton
# ---------------------------------------------------------------------------

class Metrics:
    """Singleton de collecte de métriques pour les appels LLM.

    Cette classe centralise le suivi des tokens, des latences, des erreurs
    et des requêtes.  Elle est thread-safe et accessible globalement via
    :meth:`Metrics.instance`.

    Examples
    --------
    >>> m = Metrics.instance()
    >>> m.increment_tokens("claude-3-opus", input_tokens=100, output_tokens=50)
    >>> m.record_llm_latency("claude-3-opus", 1.5)
    >>> m.increment_errors("LLMConnectionError")
    >>> m.increment_requests("/v1/chat/completions")
    >>> m.get_summary()
    {'tokens': {...}, 'latency': {...}, 'errors': {...}, 'requests': {...}}
    """

    _instance: Metrics | None = None
    _instance_lock: threading.Lock = threading.Lock()

    # -------------------------------------------------------------------
    # Accès singleton
    # -------------------------------------------------------------------

    @classmethod
    def instance(cls) -> Metrics:
        """Renvoie l'instance unique de :class:`Metrics`.

        La première appel crée l'instance ; les appels suivants
        renvoient la même instance.

        Returns
        -------
        Metrics
            L'instance singleton.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # -------------------------------------------------------------------
    # Constructeur
    # -------------------------------------------------------------------

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()

        # Tokens : {model: {"input": int, "output": int}}
        self._tokens: dict[str, dict[str, int]] = {}

        # Latences : {model: deque([latency_seconds, ...], maxlen=MAX_LATENCIES)}
        self._latencies: dict[str, collections.deque[float]] = {}

        # Erreurs : {error_type: count}
        self._errors: dict[str, int] = {}

        # Requêtes : {endpoint: count}
        self._requests: dict[str, int] = {}

    # -------------------------------------------------------------------
    # Tokens
    # -------------------------------------------------------------------

    def increment_tokens(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Incrémente les compteurs de tokens pour un modèle donné.

        Parameters
        ----------
        model : str
            Nom du modèle LLM (ex. ``"claude-3-opus"``).
        input_tokens : int
            Nombre de tokens d'entrée à ajouter. Valeur par défaut : 0.
        output_tokens : int
            Nombre de tokens de sortie à ajouter. Valeur par défaut : 0.
        """
        with self._lock:
            if model not in self._tokens:
                self._tokens[model] = {"input": 0, "output": 0}
            self._tokens[model]["input"] += input_tokens
            self._tokens[model]["output"] += output_tokens

    def get_tokens(self, model: str) -> dict[str, int]:
        """Renvoie les compteurs de tokens pour un modèle.

        Parameters
        ----------
        model : str
            Nom du modèle.

        Returns
        -------
        dict[str, int]
            Dictionnaire avec les clés ``"input"`` et ``"output"``.
            Si le modèle n'existe pas, renvoie ``{"input": 0, "output": 0}``.
        """
        with self._lock:
            return dict(self._tokens.get(model, {"input": 0, "output": 0}))

    # -------------------------------------------------------------------
    # Latences LLM
    # -------------------------------------------------------------------

    def record_llm_latency(self, model: str, latency_seconds: float) -> None:
        """Enregistre une mesure de latence pour un appel LLM.

        Parameters
        ----------
        model : str
            Nom du modèle LLM.
        latency_seconds : float
            Durée de l'appel en secondes. Doit être >= 0.
        """
        if latency_seconds < 0:
            raise ValueError("latency_seconds doit être >= 0")
        with self._lock:
            if model not in self._latencies:
                self._latencies[model] = collections.deque(maxlen=MAX_LATENCIES)
            self._latencies[model].append(latency_seconds)

    def get_latency_stats(self, model: str) -> dict[str, float | None]:
        """Renvoie les statistiques de latence pour un modèle.

        Parameters
        ----------
        model : str
            Nom du modèle.

        Returns
        -------
        dict[str, float | None]
            Dictionnaire avec les clés ``"count"``, ``"total"``,
            ``"avg"``, ``"min"``, ``"max"``.
            Si aucune mesure n'existe, toutes les valeurs sont ``None``
            sauf ``"count"`` qui vaut 0.
        """
        with self._lock:
            latencies = self._latencies.get(model, [])
            if not latencies:
                return {
                    "count": 0,
                    "total": None,
                    "avg": None,
                    "min": None,
                    "max": None,
                }
            return {
                "count": len(latencies),
                "total": sum(latencies),
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
            }

    # -------------------------------------------------------------------
    # Erreurs
    # -------------------------------------------------------------------

    def increment_errors(self, error_type: str) -> None:
        """Incrémente le compteur d'erreurs pour un type donné.

        Parameters
        ----------
        error_type : str
            Type d'erreur (ex. ``"LLMConnectionError"``).
        """
        with self._lock:
            self._errors[error_type] = self._errors.get(error_type, 0) + 1

    def get_error_count(self, error_type: str) -> int:
        """Renvoie le nombre d'erreurs pour un type donné.

        Parameters
        ----------
        error_type : str
            Type d'erreur.

        Returns
        -------
        int
            Nombre d'erreurs enregistrées pour ce type. 0 si absent.
        """
        with self._lock:
            return self._errors.get(error_type, 0)

    # -------------------------------------------------------------------
    # Requêtes
    # -------------------------------------------------------------------

    def increment_requests(self, endpoint: str) -> None:
        """Incrémente le compteur de requêtes pour un endpoint donné.

        Parameters
        ----------
        endpoint : str
            Endpoint de l'API (ex. ``"/v1/chat/completions"``).
        """
        with self._lock:
            self._requests[endpoint] = self._requests.get(endpoint, 0) + 1

    def get_request_count(self, endpoint: str) -> int:
        """Renvoie le nombre de requêtes pour un endpoint.

        Parameters
        ----------
        endpoint : str
            Endpoint de l'API.

        Returns
        -------
        int
            Nombre de requêtes. 0 si absent.
        """
        with self._lock:
            return self._requests.get(endpoint, 0)

    # -------------------------------------------------------------------
    # Résumé et réinitialisation
    # -------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """Renvoie un résumé complet de toutes les métriques.

        Returns
        -------
        dict[str, Any]
            Dictionnaire contenant les sections suivantes :

            - ``"tokens"`` : ``{model: {"input": int, "output": int}}``
            - ``"latency"`` : ``{model: {"count": int, "total": float, "avg": float, "min": float, "max": float}}``
            - ``"errors"`` : ``{error_type: int}``
            - ``"requests"`` : ``{endpoint: int}``
        """
        with self._lock:
            tokens_summary: dict[str, dict[str, int]] = {}
            for model, counts in self._tokens.items():
                tokens_summary[model] = dict(counts)

            latency_summary: dict[str, dict[str, Any]] = {}
            for model, latencies in self._latencies.items():
                if latencies:
                    latency_summary[model] = {
                        "count": len(latencies),
                        "total": sum(latencies),
                        "avg": sum(latencies) / len(latencies),
                        "min": min(latencies),
                        "max": max(latencies),
                    }
                else:
                    latency_summary[model] = {
                        "count": 0,
                        "total": None,
                        "avg": None,
                        "min": None,
                        "max": None,
                    }

            return {
                "tokens": tokens_summary,
                "latency": latency_summary,
                "errors": dict(self._errors),
                "requests": dict(self._requests),
            }

    def reset(self) -> None:
        """Réinitialise toutes les métriques.

        Supprime tous les compteurs de tokens, latences, erreurs et requêtes.
        """
        with self._lock:
            self._tokens.clear()
            self._latencies.clear()
            self._errors.clear()
            self._requests.clear()


# ---------------------------------------------------------------------------
# MetricsTimer — Gestionnaire de contexte
# ---------------------------------------------------------------------------

class MetricsTimer:
    """Gestionnaire de contexte pour mesurer la latence d'un appel LLM.

    À la sortie du bloc ``with``, la latence est automatiquement
    enregistrée dans le singleton :class:`Metrics`.

    Parameters
    ----------
    model : str
        Nom du modèle LLM dont on mesure la latence.

    Examples
    --------
    >>> with MetricsTimer("claude-3-opus") as timer:
    ...     result = llm_call()
    >>> timer.elapsed
    1.234
    """

    def __init__(self, model: str) -> None:
        self._model: str = model
        self._start: float = 0.0
        self._elapsed: float = 0.0

    @property
    def elapsed(self) -> float:
        """Durée écoulée en secondes depuis l'entrée dans le bloc ``with``.

        Si le bloc n'est pas encore terminé, renvoie le temps écoulé
        jusqu'à présent.  Après la sortie, renvoie la durée totale.

        Returns
        -------
        float
            Durée en secondes.
        """
        if self._elapsed > 0:
            return self._elapsed
        return time.monotonic() - self._start

    def __enter__(self) -> MetricsTimer:
        """Entre dans le bloc de mesure de latence."""
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Sort du bloc et enregistre la latence dans les métriques."""
        self._elapsed = time.monotonic() - self._start
        Metrics.instance().record_llm_latency(self._model, self._elapsed)


# ---------------------------------------------------------------------------
# Symboles publics
# ---------------------------------------------------------------------------

__all__ = [
    "Metrics",
    "MetricsTimer",
]

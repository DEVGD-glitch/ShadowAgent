"""Circuit breaker pour les appels LLM.

Ce module implémente un circuit breaker qui protège le système contre
les pannes en cascade lors d'appels répétés à un service LLM défaillant.
Le circuit breaker possède trois états :

- **CLOSED** : fonctionnement normal, les appels passent librement.
  Les échecs sont comptés ; si le seuil est atteint, le circuit s'ouvre.
- **OPEN** : le circuit est ouvert, tous les appels échouent immédiatement
  en levant :class:`LLMConnectionError`.  Après un délai de récupération,
  le circuit passe en état HALF_OPEN.
- **HALF_OPEN** : un nombre limité d'appels de test est autorisé.
  Si l'un réussit, le circuit se referme ; si le quota est épuisé
  sans succès, le circuit s'ouvre à nouveau.

Toutes les opérations sont thread-safe grâce à un verrou interne.

Public API
----------
CircuitBreaker, CircuitState
"""

from __future__ import annotations

import enum
import threading
import time
from typing import Any, Callable, TypeVar

try:
    from exceptions import LLMConnectionError
except ImportError:
    LLMConnectionError = type("LLMConnectionError", (Exception,), {})  # type: ignore[misc,assignment]

F = TypeVar("F", bound=Callable[..., Any])

# Lazy import for event_bus — avoid circular imports at module level
_event_bus_module = None

def _get_event_bus():
    """Lazily import and return the global event bus, or None if unavailable."""
    global _event_bus_module
    if _event_bus_module is not None:
        return _event_bus_module
    try:
        from agentmain.event_bus import get_event_bus
        _event_bus_module = get_event_bus
        return _event_bus_module
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Énumération des états du circuit breaker
# ---------------------------------------------------------------------------

class CircuitState(enum.Enum):
    """États possibles du circuit breaker.

    Attributes
    ----------
    CLOSED : str
        Le circuit est fermé — les appels passent normalement.
    OPEN : str
        Le circuit est ouvert — les appels sont rejetés immédiatement.
    HALF_OPEN : str
        Le circuit est semi-ouvert — quelques appels de test sont autorisés.
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Circuit breaker pour protéger les appels LLM contre les pannes en cascade.

    Parameters
    ----------
    failure_threshold : int
        Nombre d'échecs consécutifs nécessaire pour ouvrir le circuit.
        Valeur par défaut : 5.
    recovery_timeout : float
        Délai en secondes avant de passer de l'état OPEN à HALF_OPEN.
        Valeur par défaut : 60.0.
    half_open_max_calls : int
        Nombre maximal d'appels de test autorisés en état HALF_OPEN.
        Valeur par défaut : 1.

    Examples
    --------
    >>> cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
    >>> cb.state
    <CircuitState.CLOSED: 'closed'>
    >>> result = cb.call(my_llm_function, "hello")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        provider_name: str = "unknown",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold doit être >= 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout doit être >= 0")
        if half_open_max_calls < 1:
            raise ValueError("half_open_max_calls doit être >= 1")

        self._failure_threshold: int = failure_threshold
        self._recovery_timeout: float = recovery_timeout
        self._half_open_max_calls: int = half_open_max_calls
        self._provider_name: str = provider_name

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._half_open_call_count: int = 0
        self._last_failure_time: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    # -------------------------------------------------------------------
    # Propriétés
    # -------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Renvoie l'état actuel du circuit breaker.

        Si le circuit est OPEN et que le délai de récupération est écoulé,
        cette propriété provoque la transition vers HALF_OPEN.

        Returns
        -------
        CircuitState
            L'état courant du circuit breaker.
        """
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_threshold(self) -> int:
        """Seuil d'échecs consécutifs pour ouvrir le circuit."""
        return self._failure_threshold

    @property
    def recovery_timeout(self) -> float:
        """Délai de récupération en secondes avant passage en HALF_OPEN."""
        return self._recovery_timeout

    @property
    def half_open_max_calls(self) -> int:
        """Nombre maximal d'appels de test en état HALF_OPEN."""
        return self._half_open_max_calls

    @property
    def failure_count(self) -> int:
        """Nombre d'échecs consécutifs actuel."""
        with self._lock:
            return self._failure_count

    # -------------------------------------------------------------------
    # Méthode principale : call
    # -------------------------------------------------------------------

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Exécute *func* à travers le circuit breaker.

        - En état **CLOSED** : appelle *func* normalement. En cas de succès,
          le compteur d'échecs est remis à zéro. En cas d'exception,
          l'échec est enregistré et le circuit peut s'ouvrir.
        - En état **OPEN** : lève immédiatement :class:`LLMConnectionError`.
        - En état **HALF_OPEN** : autorise un nombre limité d'appels de test.
          Un succès referme le circuit ; un échec le rouvre.

        Parameters
        ----------
        func : Callable[..., Any]
            La fonction à appeler (typiquement un appel LLM).
        *args : Any
            Arguments positionnels passés à *func*.
        **kwargs : Any
            Arguments nommés passés à *func*.

        Returns
        -------
        Any
            Le résultat de *func(*args, **kwargs)*.

        Raises
        ------
        LLMConnectionError
            Si le circuit est OPEN ou si le quota HALF_OPEN est épuisé.
        """
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                raise LLMConnectionError(
                    "Circuit breaker est OPEN — appel rejeté immédiatement",
                    details={"state": self._state.value},
                )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_call_count >= self._half_open_max_calls:
                    raise LLMConnectionError(
                        "Circuit breaker en HALF_OPEN — quota d'appels de test épuisé",
                        details={
                            "state": self._state.value,
                            "half_open_call_count": self._half_open_call_count,
                            "half_open_max_calls": self._half_open_max_calls,
                        },
                    )
                self._half_open_call_count += 1

        # Exécution hors du verrou pour ne pas bloquer les autres threads
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self.record_failure()
            raise

        self.record_success()
        return result

    # -------------------------------------------------------------------
    # Enregistrement des résultats
    # -------------------------------------------------------------------

    def record_success(self) -> None:
        """Enregistre un appel réussi.

        En état CLOSED, remet le compteur d'échecs à zéro.
        En état HALF_OPEN, referme le circuit.
        """
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Enregistre un échec d'appel.

        En état CLOSED, incrémente le compteur d'échecs ; si le seuil
        est atteint, le circuit s'ouvre.
        En état HALF_OPEN, le circuit s'ouvre immédiatement.
        """
        with self._lock:
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self._failure_threshold:
                    self._transition_to_open()

    # -------------------------------------------------------------------
    # Réinitialisation
    # -------------------------------------------------------------------

    def reset(self) -> None:
        """Réinitialise le circuit breaker à l'état CLOSED.

        Remet à zéro tous les compteurs et l'horodatage du dernier échec.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_call_count = 0
            self._last_failure_time = 0.0

    # -------------------------------------------------------------------
    # Transitions internes
    # -------------------------------------------------------------------

    def _transition_to_open(self) -> None:
        """Fait passer le circuit à l'état OPEN."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._half_open_call_count = 0
        self._emit_state_change(old_state, CircuitState.OPEN)

    def _transition_to_closed(self) -> None:
        """Fait passer le circuit à l'état CLOSED."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_call_count = 0
        self._emit_state_change(old_state, CircuitState.CLOSED)

    def _maybe_transition_to_half_open(self) -> None:
        """Vérifie si le circuit doit passer de OPEN à HALF_OPEN.

        Cette méthode est appelée sous le verrou. Si le délai de
        récupération est écoulé depuis le dernier échec, le circuit
        passe en HALF_OPEN.
        """
        if self._state != CircuitState.OPEN:
            return
        if self._last_failure_time == 0.0:
            return
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self._recovery_timeout:
            old_state = self._state
            self._state = CircuitState.HALF_OPEN
            self._half_open_call_count = 0
            self._emit_state_change(old_state, CircuitState.HALF_OPEN)

    def _emit_state_change(self, old_state: CircuitState, new_state: CircuitState) -> None:
        """Emit a state change event via the event bus (if available).

        This method is called under the lock, so the event bus call
        must be non-blocking.  We schedule the emit in a separate
        thread to avoid any risk of deadlock.
        """
        try:
            bus = _get_event_bus()
            if bus is not None:
                import datetime
                event_data = {
                    "provider": getattr(self, "_provider_name", "unknown"),
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "failure_count": self._failure_count,
                }
                # Use a helper to emit — this must not deadlock under _lock
                import threading
                threading.Thread(
                    target=lambda: bus().emit("circuit_breaker.state_change", event_data),
                    daemon=True,
                ).start()
        except Exception:
            pass  # Event bus emission is best-effort


# ---------------------------------------------------------------------------
# Symboles publics
# ---------------------------------------------------------------------------

__all__ = [
    "CircuitBreaker",
    "CircuitState",
]

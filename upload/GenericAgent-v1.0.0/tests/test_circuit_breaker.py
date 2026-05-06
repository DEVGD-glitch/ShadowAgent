"""Tests unitaires pour le module circuit_breaker.

Couvre les transitions d'état, les seuils de déclenchement,
la sécurité des threads et l'intégration avec des appels LLM simulés.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from circuit_breaker import CircuitBreaker, CircuitState


# ══════════════════════════════════════════════════════════════════════
# Transitions d'état
# ══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerStates:
    """Tests pour les transitions d'état CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_initial_state_is_closed(self) -> None:
        """Le circuit breaker démarre en état CLOSED."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_closed_to_open_on_failure_threshold(self) -> None:
        """Le circuit passe de CLOSED à OPEN après failure_threshold échecs."""
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_to_half_open_after_recovery(self) -> None:
        """Le circuit passe de OPEN à HALF_OPEN après le recovery_timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self) -> None:
        """Le circuit passe de HALF_OPEN à CLOSED après un succès."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self) -> None:
        """Le circuit passe de HALF_OPEN à OPEN après un échec."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_call(self) -> None:
        """En état OPEN, call() lève LLMConnectionError."""
        from exceptions import LLMConnectionError
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        with pytest.raises(LLMConnectionError):
            cb.call(lambda: "hello")


# ══════════════════════════════════════════════════════════════════════
# Seuils de déclenchement
# ══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerThresholds:
    """Tests pour les seuils de déclenchement et le recovery timeout."""

    def test_default_failure_threshold(self) -> None:
        """Le seuil d'échecs par défaut est 5."""
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5

    def test_custom_failure_threshold(self) -> None:
        """Un seuil personnalisé est respecté."""
        cb = CircuitBreaker(failure_threshold=10)
        assert cb.failure_threshold == 10

    def test_default_recovery_timeout(self) -> None:
        """Le recovery_timeout par défaut est 60 secondes."""
        cb = CircuitBreaker()
        assert cb.recovery_timeout == 60.0

    def test_custom_recovery_timeout(self) -> None:
        """Un recovery_timeout personnalisé est respecté."""
        cb = CircuitBreaker(recovery_timeout=30.0)
        assert cb.recovery_timeout == 30.0

    def test_half_open_max_calls_default(self) -> None:
        """Le nombre d'appels de test par défaut en HALF_OPEN est 1."""
        cb = CircuitBreaker()
        assert cb.half_open_max_calls == 1

    def test_half_open_max_calls_custom(self) -> None:
        """Un nombre personnalisé d'appels de test est respecté."""
        cb = CircuitBreaker(half_open_max_calls=3)
        assert cb.half_open_max_calls == 3

    def test_invalid_failure_threshold_raises(self) -> None:
        """Un failure_threshold < 1 lève ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)

    def test_invalid_recovery_timeout_raises(self) -> None:
        """Un recovery_timeout négatif lève ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(recovery_timeout=-1.0)

    def test_invalid_half_open_max_calls_raises(self) -> None:
        """Un half_open_max_calls < 1 lève ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(half_open_max_calls=0)

    def test_below_threshold_stays_closed(self) -> None:
        """Avec des échecs en dessous du seuil, le circuit reste CLOSED."""
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_exact_threshold_opens_circuit(self) -> None:
        """Exactement failure_threshold échecs ouvrent le circuit."""
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_recovery_timeout_not_elapsed_stays_open(self) -> None:
        """Avant le recovery_timeout, le circuit reste OPEN."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls_enforced(self) -> None:
        """En HALF_OPEN, au-delà du quota d'appels, LLMConnectionError est levée."""
        from exceptions import LLMConnectionError
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=1)
        cb.record_failure()
        time.sleep(0.15)
        # Premier appel de test autorisé
        result = cb.call(lambda: "ok")
        assert result == "ok"
        # Le circuit est maintenant CLOSED, on peut rappeler
        assert cb.state == CircuitState.CLOSED

    def test_half_open_multiple_test_calls(self) -> None:
        """En HALF_OPEN avec half_open_max_calls=2, deux appels de test sont possibles."""
        from exceptions import LLMConnectionError
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.15)
        # Premier appel de test — échoue
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        # Le circuit repasse en HALF_OPEN, deuxième appel de test
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


# ══════════════════════════════════════════════════════════════════════
# Sécurité des threads
# ══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerThreadSafety:
    """Tests pour la sécurité des accès concurrents."""

    def test_concurrent_failures(self) -> None:
        """Des échecs simultanés ne corrompent pas l'état du circuit breaker."""
        cb = CircuitBreaker(failure_threshold=500)
        errors: list[Exception] = []

        def fail():
            try:
                for _ in range(50):
                    cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert cb.failure_count == 200

    def test_concurrent_call_success(self) -> None:
        """Des appels concurrents réussis ne causent pas d'erreur."""
        cb = CircuitBreaker(failure_threshold=5)
        results: list[str] = []
        errors: list[Exception] = []

        def call_cb():
            try:
                r = cb.call(lambda: "ok")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_cb) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10

    def test_concurrent_state_reads(self) -> None:
        """Des lectures concurrentes de l'état ne causent pas d'erreur."""
        cb = CircuitBreaker(failure_threshold=5)
        states: list[CircuitState] = []
        errors: list[Exception] = []

        def read_state():
            try:
                states.append(cb.state)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_state) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(s == CircuitState.CLOSED for s in states)


# ══════════════════════════════════════════════════════════════════════
# Réinitialisation manuelle
# ══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerReset:
    """Tests pour la réinitialisation manuelle du circuit breaker."""

    def test_reset_from_open(self) -> None:
        """reset() ramène le circuit de OPEN à CLOSED."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_from_half_open(self) -> None:
        """reset() ramène le circuit de HALF_OPEN à CLOSED."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_clears_failure_count(self) -> None:
        """reset() remet le compteur d'échecs à zéro."""
        cb = CircuitBreaker(failure_threshold=10)
        for _ in range(5):
            cb.record_failure()
        assert cb.failure_count == 5
        cb.reset()
        assert cb.failure_count == 0

    def test_reset_allows_new_calls(self) -> None:
        """Après reset(), les appels passent à nouveau."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        cb.reset()
        result = cb.call(lambda: "works")
        assert result == "works"


# ══════════════════════════════════════════════════════════════════════
# Intégration avec des appels LLM simulés
# ══════════════════════════════════════════════════════════════════════

class TestCircuitBreakerIntegration:
    """Tests d'intégration avec des appels LLM simulés."""

    def test_successful_call(self) -> None:
        """Un appel réussi en état CLOSED renvoie le résultat."""
        cb = CircuitBreaker()
        result = cb.call(lambda: "hello")
        assert result == "hello"

    def test_call_with_args(self) -> None:
        """call() transmet les arguments positionnels et nommés."""
        cb = CircuitBreaker()

        def add(a: int, b: int) -> int:
            return a + b

        result = cb.call(add, 2, 3)
        assert result == 5

    def test_call_with_kwargs(self) -> None:
        """call() transmet les arguments nommés."""
        cb = CircuitBreaker()

        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = cb.call(greet, "Alice", greeting="Hi")
        assert result == "Hi, Alice!"

    def test_failed_call_records_failure(self) -> None:
        """Un appel qui lève une exception est compté comme échec."""
        cb = CircuitBreaker(failure_threshold=3)

        def failing_call() -> None:
            raise RuntimeError("LLM error")

        with pytest.raises(RuntimeError):
            cb.call(failing_call)
        assert cb.failure_count == 1

    def test_success_resets_failure_count(self) -> None:
        """Un appel réussi remet le compteur d'échecs à zéro."""
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.call(lambda: "ok")
        assert cb.failure_count == 0

    def test_open_circuit_raises_llm_connection_error(self) -> None:
        """En état OPEN, call() lève LLMConnectionError."""
        from exceptions import LLMConnectionError
        cb = CircuitBreaker(failure_threshold=1)

        def failing() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            cb.call(failing)
        # Le circuit est maintenant OPEN
        with pytest.raises(LLMConnectionError):
            cb.call(lambda: "hello")

    def test_half_open_successful_call_closes_circuit(self) -> None:
        """Un appel réussi en HALF_OPEN referme le circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failed_call_reopens_circuit(self) -> None:
        """Un appel échoué en HALF_OPEN rouvre le circuit."""
        from exceptions import LLMConnectionError
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        def failing() -> None:
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError):
            cb.call(failing)
        assert cb.state == CircuitState.OPEN

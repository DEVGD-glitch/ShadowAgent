"""Tests unitaires pour le module metrics.

Couvre le singleton Metrics, les compteurs de tokens, les latences,
les compteurs d'erreurs, le résumé, le gestionnaire de contexte
MetricsTimer et la sécurité des threads.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from metrics import Metrics, MetricsTimer


# ══════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════

class TestMetricsSingleton:
    """Tests pour le comportement singleton de Metrics."""

    def setup_method(self) -> None:
        """Réinitialise le singleton avant chaque test."""
        Metrics._instance = None

    def test_instance_returns_same_object(self) -> None:
        """instance() renvoie toujours le même objet."""
        m1 = Metrics.instance()
        m2 = Metrics.instance()
        assert m1 is m2

    def test_instance_is_metrics(self) -> None:
        """L'instance est de type Metrics."""
        m = Metrics.instance()
        assert isinstance(m, Metrics)

    def test_reset_clears_all(self) -> None:
        """reset() efface toutes les métriques."""
        m = Metrics.instance()
        m.increment_tokens("model", 100, 50)
        m.record_llm_latency("model", 1.0)
        m.increment_errors("TestError")
        m.increment_requests("/test")
        m.reset()
        assert m.get_tokens("model") == {"input": 0, "output": 0}
        assert m.get_error_count("TestError") == 0
        assert m.get_request_count("/test") == 0
        assert m.get_latency_stats("model")["count"] == 0

    def test_new_instance_after_reset_singleton(self) -> None:
        """Après réinitialisation du singleton, une nouvelle instance est créée."""
        m1 = Metrics.instance()
        Metrics._instance = None
        m2 = Metrics.instance()
        assert m1 is not m2


# ══════════════════════════════════════════════════════════════════════
# Compteurs de tokens
# ══════════════════════════════════════════════════════════════════════

class TestTokenCounter:
    """Tests pour les compteurs de tokens."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_increment_tokens(self) -> None:
        """increment_tokens() ajoute les tokens au modèle."""
        m = Metrics.instance()
        m.increment_tokens("claude-3-opus", input_tokens=100, output_tokens=50)
        tokens = m.get_tokens("claude-3-opus")
        assert tokens["input"] == 100
        assert tokens["output"] == 50

    def test_increment_accumulates(self) -> None:
        """Les increments de tokens s'accumulent."""
        m = Metrics.instance()
        m.increment_tokens("claude-3-opus", input_tokens=100, output_tokens=50)
        m.increment_tokens("claude-3-opus", input_tokens=200, output_tokens=100)
        tokens = m.get_tokens("claude-3-opus")
        assert tokens["input"] == 300
        assert tokens["output"] == 150

    def test_multiple_models(self) -> None:
        """Les tokens sont suivis séparément par modèle."""
        m = Metrics.instance()
        m.increment_tokens("claude-3-opus", input_tokens=100)
        m.increment_tokens("gpt-4", input_tokens=200)
        assert m.get_tokens("claude-3-opus")["input"] == 100
        assert m.get_tokens("gpt-4")["input"] == 200

    def test_unknown_model_returns_zero(self) -> None:
        """Un modèle inconnu renvoie des compteurs à zéro."""
        m = Metrics.instance()
        tokens = m.get_tokens("unknown-model")
        assert tokens == {"input": 0, "output": 0}

    def test_increment_default_zero(self) -> None:
        """Les tokens par défaut sont 0."""
        m = Metrics.instance()
        m.increment_tokens("model")
        tokens = m.get_tokens("model")
        assert tokens["input"] == 0
        assert tokens["output"] == 0


# ══════════════════════════════════════════════════════════════════════
# Latences LLM
# ══════════════════════════════════════════════════════════════════════

class TestLLMLatency:
    """Tests pour l'enregistrement des latences."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_record_latency(self) -> None:
        """record_llm_latency() enregistre une mesure."""
        m = Metrics.instance()
        m.record_llm_latency("claude-3-opus", 1.5)
        stats = m.get_latency_stats("claude-3-opus")
        assert stats["count"] == 1
        assert stats["avg"] == 1.5
        assert stats["min"] == 1.5
        assert stats["max"] == 1.5

    def test_latency_stats_multiple(self) -> None:
        """Les statistiques de latence sont correctes avec plusieurs mesures."""
        m = Metrics.instance()
        m.record_llm_latency("model", 1.0)
        m.record_llm_latency("model", 2.0)
        m.record_llm_latency("model", 3.0)
        stats = m.get_latency_stats("model")
        assert stats["count"] == 3
        assert stats["total"] == 6.0
        assert abs(stats["avg"] - 2.0) < 1e-9
        assert stats["min"] == 1.0
        assert stats["max"] == 3.0

    def test_latency_unknown_model(self) -> None:
        """Un modèle inconnu renvoie des statistiques à None."""
        m = Metrics.instance()
        stats = m.get_latency_stats("unknown")
        assert stats["count"] == 0
        assert stats["avg"] is None
        assert stats["min"] is None
        assert stats["max"] is None

    def test_negative_latency_raises(self) -> None:
        """Une latence négative lève ValueError."""
        m = Metrics.instance()
        with pytest.raises(ValueError):
            m.record_llm_latency("model", -0.1)

    def test_zero_latency(self) -> None:
        """Une latence de zéro est acceptée."""
        m = Metrics.instance()
        m.record_llm_latency("model", 0.0)
        stats = m.get_latency_stats("model")
        assert stats["count"] == 1
        assert stats["avg"] == 0.0

    def test_latency_per_model(self) -> None:
        """Les latences sont suivies séparément par modèle."""
        m = Metrics.instance()
        m.record_llm_latency("model-a", 1.0)
        m.record_llm_latency("model-b", 2.0)
        assert m.get_latency_stats("model-a")["avg"] == 1.0
        assert m.get_latency_stats("model-b")["avg"] == 2.0


# ══════════════════════════════════════════════════════════════════════
# Compteurs d'erreurs
# ══════════════════════════════════════════════════════════════════════

class TestErrorCounter:
    """Tests pour les compteurs d'erreurs."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_increment_errors(self) -> None:
        """increment_errors() incrémente le compteur."""
        m = Metrics.instance()
        m.increment_errors("LLMConnectionError")
        assert m.get_error_count("LLMConnectionError") == 1

    def test_increment_accumulates(self) -> None:
        """Les erreurs s'accumulent."""
        m = Metrics.instance()
        m.increment_errors("LLMConnectionError")
        m.increment_errors("LLMConnectionError")
        m.increment_errors("LLMConnectionError")
        assert m.get_error_count("LLMConnectionError") == 3

    def test_different_error_types(self) -> None:
        """Les types d'erreurs sont suivis séparément."""
        m = Metrics.instance()
        m.increment_errors("LLMConnectionError")
        m.increment_errors("LLMRateLimitError")
        m.increment_errors("LLMConnectionError")
        assert m.get_error_count("LLMConnectionError") == 2
        assert m.get_error_count("LLMRateLimitError") == 1

    def test_unknown_error_type_returns_zero(self) -> None:
        """Un type d'erreur inconnu renvoie 0."""
        m = Metrics.instance()
        assert m.get_error_count("UnknownError") == 0


# ══════════════════════════════════════════════════════════════════════
# Résumé des métriques
# ══════════════════════════════════════════════════════════════════════

class TestMetricsSummary:
    """Tests pour get_summary()."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_summary_format(self) -> None:
        """get_summary() renvoie un dictionnaire avec les clés attendues."""
        m = Metrics.instance()
        summary = m.get_summary()
        assert "tokens" in summary
        assert "latency" in summary
        assert "errors" in summary
        assert "requests" in summary

    def test_summary_includes_tokens(self) -> None:
        """Le résumé inclut les tokens."""
        m = Metrics.instance()
        m.increment_tokens("claude-3-opus", input_tokens=100, output_tokens=50)
        summary = m.get_summary()
        assert "claude-3-opus" in summary["tokens"]
        assert summary["tokens"]["claude-3-opus"]["input"] == 100
        assert summary["tokens"]["claude-3-opus"]["output"] == 50

    def test_summary_includes_latency(self) -> None:
        """Le résumé inclut les latences."""
        m = Metrics.instance()
        m.record_llm_latency("claude-3-opus", 1.5)
        summary = m.get_summary()
        assert "claude-3-opus" in summary["latency"]
        assert summary["latency"]["claude-3-opus"]["count"] == 1

    def test_summary_includes_errors(self) -> None:
        """Le résumé inclut les erreurs."""
        m = Metrics.instance()
        m.increment_errors("LLMConnectionError")
        summary = m.get_summary()
        assert "LLMConnectionError" in summary["errors"]
        assert summary["errors"]["LLMConnectionError"] == 1

    def test_summary_includes_requests(self) -> None:
        """Le résumé inclut les requêtes."""
        m = Metrics.instance()
        m.increment_requests("/v1/chat/completions")
        summary = m.get_summary()
        assert "/v1/chat/completions" in summary["requests"]
        assert summary["requests"]["/v1/chat/completions"] == 1

    def test_summary_after_reset(self) -> None:
        """Après reset(), le résumé est vide."""
        m = Metrics.instance()
        m.increment_tokens("model", 100, 50)
        m.record_llm_latency("model", 1.0)
        m.increment_errors("TestError")
        m.increment_requests("/test")
        m.reset()
        summary = m.get_summary()
        assert summary["tokens"] == {}
        assert summary["latency"] == {}
        assert summary["errors"] == {}
        assert summary["requests"] == {}


# ══════════════════════════════════════════════════════════════════════
# MetricsTimer
# ══════════════════════════════════════════════════════════════════════

class TestMetricsTimer:
    """Tests pour le gestionnaire de contexte MetricsTimer."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_timer_records_latency(self) -> None:
        """MetricsTimer enregistre la latence dans les métriques."""
        m = Metrics.instance()
        with MetricsTimer("claude-3-opus") as timer:
            time.sleep(0.01)
        stats = m.get_latency_stats("claude-3-opus")
        assert stats["count"] == 1
        assert stats["avg"] >= 0.01

    def test_timer_elapsed(self) -> None:
        """timer.elapsed contient la durée mesurée."""
        with MetricsTimer("model") as timer:
            time.sleep(0.01)
        assert timer.elapsed >= 0.01

    def test_timer_returns_self(self) -> None:
        """Le gestionnaire de contexte renvoie l'objet MetricsTimer."""
        with MetricsTimer("model") as timer:
            assert isinstance(timer, MetricsTimer)

    def test_timer_records_on_exception(self) -> None:
        """La latence est enregistrée même si une exception est levée."""
        m = Metrics.instance()
        with pytest.raises(ValueError):
            with MetricsTimer("model") as timer:
                time.sleep(0.01)
                raise ValueError("test error")
        stats = m.get_latency_stats("model")
        assert stats["count"] == 1

    def test_timer_multiple_uses(self) -> None:
        """Plusieurs utilisations du timer accumulent les mesures."""
        m = Metrics.instance()
        for _ in range(3):
            with MetricsTimer("model"):
                time.sleep(0.005)
        stats = m.get_latency_stats("model")
        assert stats["count"] == 3


# ══════════════════════════════════════════════════════════════════════
# Sécurité des threads
# ══════════════════════════════════════════════════════════════════════

class TestMetricsThreadSafety:
    """Tests pour la sécurité des accès concurrents."""

    def setup_method(self) -> None:
        Metrics._instance = None

    def test_concurrent_token_increments(self) -> None:
        """Des increments de tokens concurrents ne perdent pas de données."""
        m = Metrics.instance()
        errors: list[Exception] = []

        def inc_tokens():
            try:
                for _ in range(100):
                    m.increment_tokens("model", input_tokens=1, output_tokens=1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inc_tokens) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        tokens = m.get_tokens("model")
        assert tokens["input"] == 1000
        assert tokens["output"] == 1000

    def test_concurrent_error_increments(self) -> None:
        """Des increments d'erreurs concurrents ne perdent pas de données."""
        m = Metrics.instance()
        errors: list[Exception] = []

        def inc_errors():
            try:
                for _ in range(100):
                    m.increment_errors("TestError")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inc_errors) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert m.get_error_count("TestError") == 1000

    def test_concurrent_request_increments(self) -> None:
        """Des increments de requêtes concurrents ne perdent pas de données."""
        m = Metrics.instance()
        errors: list[Exception] = []

        def inc_requests():
            try:
                for _ in range(100):
                    m.increment_requests("/v1/chat/completions")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inc_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert m.get_request_count("/v1/chat/completions") == 1000

    def test_concurrent_latency_recording(self) -> None:
        """Des enregistrements de latence concurrents ne perdent pas de données."""
        m = Metrics.instance()
        errors: list[Exception] = []

        def record_latency():
            try:
                for _ in range(100):
                    m.record_llm_latency("model", 0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_latency) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = m.get_latency_stats("model")
        assert stats["count"] == 500

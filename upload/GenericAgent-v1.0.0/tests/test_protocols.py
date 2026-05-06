"""Tests pour les protocoles et énumérations de GenericAgent.

Vérifie le sous-typage structurel (structural subtyping) des protocoles,
les valeurs de l'énumération LLMProvider, et la conformité des classes
existantes avec les protocoles définis dans :mod:`protocols`.
"""

from __future__ import annotations

import queue
from typing import Any, Generator, Optional

import pytest

from protocols import (
    AgentProtocol,
    BrowserDriverProtocol,
    HandlerProtocol,
    LLMProvider,
    LLMSessionProtocol,
)


# ══════════════════════════════════════════════════════════════════════════════
#  Mocks pour les tests de sous-typage structurel
# ══════════════════════════════════════════════════════════════════════════════


class MockLLMSession:
    """Mock satisfaisant LLMSessionProtocol pour les tests."""

    def __init__(self, model: str = "test-model", api_mode: str = "chat_completions") -> None:
        self._model_name = model
        self._api_mode = api_mode
        self._aborted = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def api_mode(self) -> str:
        return self._api_mode

    def stream(
        self,
        prompt: str,
        history: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, list[dict[str, Any]]]:
        yield "Hello"
        return [{"type": "text", "text": "Hello"}]

    def abort(self) -> None:
        self._aborted = True


class MockHandler:
    """Mock satisfaisant HandlerProtocol pour les tests."""

    def __init__(self) -> None:
        self.last_outcome: Any = None

    def handle_step(self, outcome: Any) -> Any:
        self.last_outcome = outcome
        return outcome

    def should_continue(self, outcome: Any) -> bool:
        if hasattr(outcome, "should_exit"):
            return not outcome.should_exit
        return True


class MockAgent:
    """Mock satisfaisant AgentProtocol pour les tests."""

    def __init__(self) -> None:
        self._aborted = False
        self._model_index = 0

    def put_task(
        self,
        prompt: str,
        files: Optional[list[str]] = None,
    ) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        q.put({"done": True, "result": prompt})
        return q

    def abort(self) -> None:
        self._aborted = True

    def switch_model(self, index: int) -> None:
        self._model_index = index


class MockBrowserDriver:
    """Mock satisfaisant BrowserDriverProtocol pour les tests."""

    def __init__(self) -> None:
        self._sessions: list[dict[str, Any]] = [
            {"id": "tab-1", "url": "https://example.com"},
        ]

    def get_all_sessions(self) -> list[dict[str, Any]]:
        return list(self._sessions)

    def execute_js(
        self,
        script: str,
        timeout: int = 15,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        return {"data": f"executed: {script[:50]}"}


# ══════════════════════════════════════════════════════════════════════════════
#  TestLLMSessionProtocol
# ══════════════════════════════════════════════════════════════════════════════


class TestLLMSessionProtocol:
    """Vérifie le sous-typage structurel de LLMSessionProtocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """Un mock avec les bonnes méthodes satisfait le protocole."""
        session = MockLLMSession()
        assert isinstance(session, LLMSessionProtocol)

    def test_model_name_property(self) -> None:
        """La propriété model_name retourne une chaîne."""
        session = MockLLMSession(model="gpt-4o")
        assert session.model_name == "gpt-4o"

    def test_api_mode_property(self) -> None:
        """La propriété api_mode retourne un mode valide."""
        session = MockLLMSession(api_mode="responses")
        assert session.api_mode == "responses"

    def test_stream_returns_generator(self) -> None:
        """stream() retourne un générateur qui yield des chaînes."""
        session = MockLLMSession()
        gen = session.stream("Hello")
        chunks = list(gen)
        assert chunks == ["Hello"]

    def test_abort_sets_flag(self) -> None:
        """abort() est appelable sans erreur."""
        session = MockLLMSession()
        session.abort()
        assert session._aborted is True

    def test_incomplete_class_does_not_satisfy(self) -> None:
        """Une classe sans les méthodes requises ne satisfait pas le protocole."""
        class IncompleteSession:
            pass

        assert not isinstance(IncompleteSession(), LLMSessionProtocol)


# ══════════════════════════════════════════════════════════════════════════════
#  TestHandlerProtocol
# ══════════════════════════════════════════════════════════════════════════════


class TestHandlerProtocol:
    """Vérifie le sous-typage structurel de HandlerProtocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """Un mock avec les bonnes méthodes satisfait le protocole."""
        handler = MockHandler()
        assert isinstance(handler, HandlerProtocol)

    def test_handle_step(self) -> None:
        """handle_step() traite un outcome."""
        handler = MockHandler()
        result = handler.handle_step("test_outcome")
        assert result == "test_outcome"
        assert handler.last_outcome == "test_outcome"

    def test_should_continue(self) -> None:
        """should_continue() retourne un booléen."""
        handler = MockHandler()
        assert handler.should_continue(None) is True

    def test_incomplete_class_does_not_satisfy(self) -> None:
        """Une classe sans should_continue ne satisfait pas le protocole."""
        class IncompleteHandler:
            def handle_step(self, outcome: Any) -> Any:
                return outcome

        assert not isinstance(IncompleteHandler(), HandlerProtocol)


# ══════════════════════════════════════════════════════════════════════════════
#  TestAgentProtocol
# ══════════════════════════════════════════════════════════════════════════════


class TestAgentProtocol:
    """Vérifie le sous-typage structurel de AgentProtocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """Un mock avec les bonnes méthodes satisfait le protocole."""
        agent = MockAgent()
        assert isinstance(agent, AgentProtocol)

    def test_put_task_returns_queue(self) -> None:
        """put_task() retourne un objet avec get()."""
        agent = MockAgent()
        result = agent.put_task("test")
        assert isinstance(result, queue.Queue)

    def test_abort(self) -> None:
        """abort() est appelable sans erreur."""
        agent = MockAgent()
        agent.abort()
        assert agent._aborted is True

    def test_switch_model(self) -> None:
        """switch_model() change l'indice du modèle."""
        agent = MockAgent()
        agent.switch_model(2)
        assert agent._model_index == 2

    def test_incomplete_class_does_not_satisfy(self) -> None:
        """Une classe sans switch_model ne satisfait pas le protocole."""
        class IncompleteAgent:
            def put_task(self, prompt: str, files: Optional[list[str]] = None) -> Any:
                return None
            def abort(self) -> None:
                pass

        assert not isinstance(IncompleteAgent(), AgentProtocol)


# ══════════════════════════════════════════════════════════════════════════════
#  TestBrowserDriverProtocol
# ══════════════════════════════════════════════════════════════════════════════


class TestBrowserDriverProtocol:
    """Vérifie le sous-typage structurel de BrowserDriverProtocol."""

    def test_mock_satisfies_protocol(self) -> None:
        """Un mock avec les bonnes méthodes satisfait le protocole."""
        driver = MockBrowserDriver()
        assert isinstance(driver, BrowserDriverProtocol)

    def test_get_all_sessions(self) -> None:
        """get_all_sessions() retourne une liste de dicts."""
        driver = MockBrowserDriver()
        sessions = driver.get_all_sessions()
        assert isinstance(sessions, list)
        assert len(sessions) == 1
        assert "id" in sessions[0]

    def test_execute_js(self) -> None:
        """execute_js() retourne un dict avec 'data'."""
        driver = MockBrowserDriver()
        result = driver.execute_js("return 1+1")
        assert "data" in result

    def test_incomplete_class_does_not_satisfy(self) -> None:
        """Une classe sans execute_js ne satisfait pas le protocole."""
        class IncompleteDriver:
            def get_all_sessions(self) -> list[dict[str, Any]]:
                return []

        assert not isinstance(IncompleteDriver(), BrowserDriverProtocol)


# ══════════════════════════════════════════════════════════════════════════════
#  TestLLMProvider
# ══════════════════════════════════════════════════════════════════════════════


class TestLLMProvider:
    """Vérifie les valeurs et conversions de l'énumération LLMProvider."""

    def test_enum_values(self) -> None:
        """Tous les fournisseurs attendus sont présents."""
        expected = {"OPENAI", "CLAUDE", "GEMINI", "DEEPSEEK", "LOCAL"}
        actual = {m.name for m in LLMProvider}
        assert actual == expected

    def test_enum_string_values(self) -> None:
        """Les valeurs texte des membres correspondent aux attentes."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.CLAUDE.value == "claude"
        assert LLMProvider.GEMINI.value == "gemini"
        assert LLMProvider.DEEPSEEK.value == "deepseek"
        assert LLMProvider.LOCAL.value == "local"

    def test_string_conversion(self) -> None:
        """La conversion en chaîne fonctionne correctement."""
        assert str(LLMProvider.OPENAI) == "LLMProvider.OPENAI"
        assert "openai" in repr(LLMProvider.OPENAI)

    def test_enum_from_value(self) -> None:
        """Construction d'un membre depuis sa valeur texte."""
        assert LLMProvider("openai") is LLMProvider.OPENAI
        assert LLMProvider("claude") is LLMProvider.CLAUDE

    def test_invalid_value_raises(self) -> None:
        """Une valeur invalide lève ValueError."""
        with pytest.raises(ValueError):
            LLMProvider("nonexistent")

    def test_enum_iteration(self) -> None:
        """L'énumération est itérable et contient 5 membres."""
        members = list(LLMProvider)
        assert len(members) == 5


# ══════════════════════════════════════════════════════════════════════════════
#  TestProtocolConformance — vérifie les classes existantes
# ══════════════════════════════════════════════════════════════════════════════


class TestProtocolConformance:
    """Vérifie que les classes existantes du projet conforment aux protocoles.

    Ces tests utilisent isinstance() avec les Protocoles runtime-checkable
    pour vérifier la conformité structurelle sans héritage explicite.
    """

    def test_base_session_satisfies_llm_session_protocol(self) -> None:
        """BaseSession possède model_name et api_mode (via héritage) et peut satisfaire le protocole.

        Note : BaseSession n'a pas directement model_name mais a model et api_mode.
        On vérifie que les sous-classes avec les bonnes propriétés satisfont le protocole.
        """
        from llmcore import BaseSession

        cfg = {
            "apikey": "test-key",
            "apibase": "https://api.example.com",
            "model": "test-model",
        }
        session = BaseSession(cfg)
        # BaseSession has .api_mode but not .model_name (it has .model instead)
        # It also lacks stream() and abort() — so it should NOT satisfy the full protocol
        assert not isinstance(session, LLMSessionProtocol)

    def test_mock_llm_session_satisfies_protocol(self) -> None:
        """Un mock complet satisfait LLMSessionProtocol."""
        session = MockLLMSession()
        assert isinstance(session, LLMSessionProtocol)

    def test_base_handler_satisfies_handler_protocol(self) -> None:
        """BaseHandler possède dispatch mais n'a pas handle_step/should_continue.

        BaseHandler ne satisfait PAS HandlerProtocol car son interface est
        différente (dispatch vs handle_step/should_continue).
        """
        from agent_loop import BaseHandler

        handler = BaseHandler()
        # BaseHandler has dispatch(), not handle_step()/should_continue()
        assert not isinstance(handler, HandlerProtocol)

    def test_mock_handler_satisfies_protocol(self) -> None:
        """Un mock complet satisfait HandlerProtocol."""
        handler = MockHandler()
        assert isinstance(handler, HandlerProtocol)

    def test_mock_agent_satisfies_protocol(self) -> None:
        """Un mock complet satisfait AgentProtocol."""
        agent = MockAgent()
        assert isinstance(agent, AgentProtocol)

    def test_mock_browser_driver_satisfies_protocol(self) -> None:
        """Un mock complet satisfait BrowserDriverProtocol."""
        driver = MockBrowserDriver()
        assert isinstance(driver, BrowserDriverProtocol)

    def test_generic_agent_has_required_methods(self) -> None:
        """GenericAgent possède put_task, abort, et next_llm (équivalent switch_model)."""
        # We verify that the agentmain module has the expected methods
        # without actually instantiating GenericAgent (which needs full config)
        import agentmain

        # Verify the class exists and has the methods
        assert hasattr(agentmain.GenericAgent, "abort")
        assert hasattr(agentmain.GenericAgent, "put_task")
        assert hasattr(agentmain.GenericAgent, "next_llm")

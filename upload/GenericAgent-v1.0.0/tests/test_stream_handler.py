"""
Tests unitaires pour le gestionnaire de streaming (StreamHandler).

Ce module teste exhaustivement la classe StreamHandler extraite de
``frontends/qt/stream_handler.py``. Aucune dépendance PySide6 n'est
nécessaire — toute la logique est testable en pur Python avec des
mocks pour l'agent.
"""
from __future__ import annotations

import os
import sys
import queue
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def chunk_log():
    """Liste pour enregistrer les appels au callback on_stream_chunk."""
    return []


@pytest.fixture
def done_log():
    """Liste pour enregistrer les appels au callback on_stream_done."""
    return []


@pytest.fixture
def handler(chunk_log, done_log):
    """Crée un StreamHandler avec des callbacks qui journalisent."""
    from frontends.qt.stream_handler import StreamHandler

    def on_chunk(text):
        chunk_log.append(text)

    def on_done(text):
        done_log.append(text)

    return StreamHandler(on_chunk, on_done)


@pytest.fixture
def mock_agent():
    """Crée un mock d'agent avec put_task et abort."""
    agent = MagicMock()
    q = queue.Queue()
    agent.put_task.return_value = q
    agent.abort.return_value = None
    return agent, q


# ══════════════════════════════════════════════════════════════════════
# Initialisation
# ══════════════════════════════════════════════════════════════════════

class TestStreamHandlerInit:
    """Tests pour l'initialisation du StreamHandler."""

    def test_initial_state(self, handler):
        """L'état initial est inactif avec un texte vide."""
        assert handler.is_streaming is False
        assert handler.streaming_text == ""

    def test_initial_queue_is_none(self, handler):
        """La file d'affichage est initialement None."""
        assert handler._display_queue is None

    def test_callbacks_stored(self, chunk_log, done_log):
        """Les callbacks sont stockés correctement."""
        from frontends.qt.stream_handler import StreamHandler
        h = StreamHandler(lambda t: chunk_log.append(t), lambda t: done_log.append(t))
        assert callable(h._on_stream_chunk)
        assert callable(h._on_stream_done)

    def test_poll_interval_ms_constant(self):
        """POLL_INTERVAL_MS est défini comme constante de classe."""
        from frontends.qt.stream_handler import StreamHandler
        assert StreamHandler.POLL_INTERVAL_MS == 40


# ══════════════════════════════════════════════════════════════════════
# start_stream
# ══════════════════════════════════════════════════════════════════════

class TestStartStream:
    """Tests pour la méthode start_stream."""

    def test_start_sets_streaming_true(self, handler, mock_agent):
        """start_stream active l'état de streaming."""
        agent, _ = mock_agent
        handler.start_stream(agent, "Bonjour", [])
        assert handler.is_streaming is True

    def test_start_resets_streaming_text(self, handler, mock_agent):
        """start_stream réinitialise le texte de streaming."""
        agent, _ = mock_agent
        handler._streaming_text = "Ancien texte"
        handler.start_stream(agent, "Nouveau", [])
        assert handler.streaming_text == ""

    def test_start_calls_agent_put_task(self, handler, mock_agent):
        """start_stream appelle agent.put_task avec le prompt."""
        agent, _ = mock_agent
        handler.start_stream(agent, "Test prompt", [])
        agent.put_task.assert_called_once()
        # Vérifier que le prompt est passé
        call_args = agent.put_task.call_args
        assert "Test prompt" in call_args[0][0]

    def test_start_stores_queue(self, handler, mock_agent):
        """start_stream stocke la file d'affichage retournée."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        assert handler._display_queue is q

    @patch('frontends.qt.stream_handler._build_prompt_with_uploads')
    def test_start_with_files(self, mock_build, handler, mock_agent):
        """start_stream passe les fichiers à _build_prompt_with_uploads."""
        agent, q = mock_agent
        mock_build.return_value = ("Full prompt", "Display prompt", [])
        files = [{"name": "test.py", "type": "text/plain", "raw": b"code"}]
        handler.start_stream(agent, "Analyse", files)
        mock_build.assert_called_once_with("Analyse", files)

    def test_start_with_empty_prompt(self, handler, mock_agent):
        """start_stream fonctionne avec un prompt vide."""
        agent, _ = mock_agent
        handler.start_stream(agent, "", [])
        assert handler.is_streaming is True


# ══════════════════════════════════════════════════════════════════════
# poll_queue
# ══════════════════════════════════════════════════════════════════════

class TestPollQueue:
    """Tests pour la méthode poll_queue."""

    def test_poll_empty_queue(self, handler, mock_agent):
        """poll_queue sur une file vide retourne une liste vide."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        result = handler.poll_queue()
        assert result == []

    def test_poll_no_queue(self, handler):
        """poll_queue sans file retourne une liste vide."""
        result = handler.poll_queue()
        assert result == []

    def test_poll_next_item(self, handler, mock_agent, chunk_log):
        """poll_queue traite un item 'next' et appelle on_stream_chunk."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"next": "Premier chunk"})
        result = handler.poll_queue()
        assert len(result) == 1
        assert result[0] == {"next": "Premier chunk"}
        assert handler.streaming_text == "Premier chunk"
        assert chunk_log == ["Premier chunk"]

    def test_poll_done_item(self, handler, mock_agent, done_log):
        """poll_queue traite un item 'done' et appelle on_stream_done."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"done": "Réponse finale"})
        result = handler.poll_queue()
        assert len(result) == 1
        assert handler.is_streaming is False
        assert handler.streaming_text == "Réponse finale"
        assert done_log == ["Réponse finale"]

    def test_poll_done_clears_queue(self, handler, mock_agent):
        """Après un item 'done', la file est mise à None."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"done": "Fin"})
        handler.poll_queue()
        assert handler._display_queue is None

    def test_poll_multiple_next_items(self, handler, mock_agent, chunk_log):
        """poll_queue traite plusieurs items 'next' consécutifs."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"next": "Chunk 1"})
        q.put({"next": "Chunk 2"})
        q.put({"next": "Chunk 3"})
        result = handler.poll_queue()
        assert len(result) == 3
        assert handler.streaming_text == "Chunk 3"
        assert len(chunk_log) == 3

    def test_poll_next_then_done(self, handler, mock_agent, chunk_log, done_log):
        """poll_queue traite des items 'next' puis un item 'done'."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"next": "En cours..."})
        q.put({"done": "Réponse complète"})
        result = handler.poll_queue()
        assert len(result) == 2
        assert handler.is_streaming is False
        assert len(chunk_log) == 1
        assert len(done_log) == 1

    def test_poll_stops_after_done(self, handler, mock_agent):
        """Après 'done', les items restants dans la file ne sont pas traités."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"done": "Fin"})
        q.put({"next": "Après fin — ne doit pas être traité"})
        result = handler.poll_queue()
        # Seul le premier item doit être traité
        assert len(result) == 1
        assert handler.streaming_text == "Fin"

    def test_poll_after_done_returns_empty(self, handler, mock_agent):
        """poll_queue après un done retourne une liste vide."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"done": "Fin"})
        handler.poll_queue()
        # La file est None maintenant
        result = handler.poll_queue()
        assert result == []


# ══════════════════════════════════════════════════════════════════════
# stop_stream
# ══════════════════════════════════════════════════════════════════════

class TestStopStream:
    """Tests pour la méthode stop_stream."""

    def test_stop_while_streaming(self, handler, mock_agent, done_log):
        """stop_stream arrête un stream en cours."""
        agent, _ = mock_agent
        handler._is_streaming = True
        handler._streaming_text = "Texte partiel"
        handler.stop_stream(agent)
        assert handler.is_streaming is False
        assert handler._display_queue is None
        assert len(done_log) == 1
        assert done_log[0] == "Texte partiel"

    def test_stop_with_no_text(self, handler, mock_agent, done_log):
        """stop_stream utilise le message par défaut si aucun texte accumulé."""
        agent, _ = mock_agent
        handler._is_streaming = True
        handler._streaming_text = ""
        handler.stop_stream(agent)
        assert done_log[0] == "(Arrêté)"

    def test_stop_calls_agent_abort(self, handler, mock_agent):
        """stop_stream appelle agent.abort()."""
        agent, _ = mock_agent
        handler._is_streaming = True
        handler.stop_stream(agent)
        agent.abort.assert_called_once()

    def test_stop_not_streaming_does_nothing(self, handler, mock_agent, done_log):
        """stop_stream sans stream actif ne fait rien."""
        agent, _ = mock_agent
        handler._is_streaming = False
        handler.stop_stream(agent)
        agent.abort.assert_not_called()
        assert len(done_log) == 0

    def test_stop_handles_agent_abort_exception(self, handler, mock_agent, done_log):
        """stop_stream gère une exception dans agent.abort()."""
        agent, _ = mock_agent
        agent.abort.side_effect = RuntimeError("Agent error")
        handler._is_streaming = True
        handler._streaming_text = "Texte"
        # Ne doit pas crasher
        handler.stop_stream(agent)
        assert handler.is_streaming is False
        assert len(done_log) == 1


# ══════════════════════════════════════════════════════════════════════
# reset
# ══════════════════════════════════════════════════════════════════════

class TestReset:
    """Tests pour la méthode reset."""

    def test_reset_clears_state(self, handler, mock_agent):
        """reset réinitialise l'état du handler."""
        agent, _ = mock_agent
        handler._is_streaming = True
        handler._streaming_text = "Texte"
        handler._display_queue = queue.Queue()
        handler.reset()
        assert handler.is_streaming is False
        assert handler.streaming_text == ""
        assert handler._display_queue is None

    def test_reset_does_not_call_callbacks(self, handler, chunk_log, done_log):
        """reset n'appelle PAS les callbacks."""
        handler._is_streaming = True
        handler._streaming_text = "Texte"
        handler.reset()
        assert len(chunk_log) == 0
        assert len(done_log) == 0


# ══════════════════════════════════════════════════════════════════════
# Propriétés
# ══════════════════════════════════════════════════════════════════════

class TestProperties:
    """Tests pour les propriétés is_streaming et streaming_text."""

    def test_is_streaming_property(self, handler):
        """is_streaming est une propriété en lecture seule."""
        assert handler.is_streaming is False
        handler._is_streaming = True
        assert handler.is_streaming is True

    def test_streaming_text_property(self, handler):
        """streaming_text est une propriété en lecture seule."""
        assert handler.streaming_text == ""
        handler._streaming_text = "En cours"
        assert handler.streaming_text == "En cours"


# ══════════════════════════════════════════════════════════════════════
# Cas limites
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests pour les cas limites et les situations inhabituelles."""

    def test_exception_in_chunk_callback(self, handler, mock_agent):
        """Une exception dans on_stream_chunk ne crashe pas poll_queue."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])

        # Remplacer le callback par un qui lève une exception
        handler._on_stream_chunk = MagicMock(side_effect=ValueError("Chunk error"))
        q.put({"next": "Texte"})
        # Ne doit pas crasher
        result = handler.poll_queue()
        assert len(result) == 1
        # Le texte doit quand même être mis à jour
        assert handler.streaming_text == "Texte"

    def test_exception_in_done_callback(self, handler, mock_agent):
        """Une exception dans on_stream_done ne crashe pas poll_queue."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])

        handler._on_stream_done = MagicMock(side_effect=ValueError("Done error"))
        q.put({"done": "Réponse finale"})
        # Ne doit pas crasher
        result = handler.poll_queue()
        assert len(result) == 1
        assert handler.is_streaming is False

    def test_multiple_start_stop_cycles(self, handler, mock_agent):
        """Des cycles start/stop multiples fonctionnent correctement."""
        agent, q = mock_agent
        # Cycle 1
        handler.start_stream(agent, "Q1", [])
        q.put({"done": "A1"})
        handler.poll_queue()
        assert handler.is_streaming is False

        # Cycle 2
        handler.start_stream(agent, "Q2", [])
        q.put({"done": "A2"})
        handler.poll_queue()
        assert handler.is_streaming is False
        assert handler.streaming_text == "A2"

        # Cycle 3 avec arrêt manuel
        handler.start_stream(agent, "Q3", [])
        handler.stop_stream(agent)
        assert handler.is_streaming is False

    def test_start_resets_previous_state(self, handler, mock_agent):
        """start_stream réinitialise l'état d'un stream précédent."""
        agent, q = mock_agent
        handler.start_stream(agent, "Q1", [])
        q.put({"next": "Partial"})
        handler.poll_queue()

        # Démarrer un nouveau stream
        handler.start_stream(agent, "Q2", [])
        assert handler.streaming_text == ""
        assert handler.is_streaming is True

    def test_done_item_with_both_keys(self, handler, mock_agent, chunk_log, done_log):
        """Un item avec à la fois 'next' et 'done' traite les deux."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put({"next": "Progress", "done": "Final"})
        result = handler.poll_queue()
        # L'item doit avoir été traité
        assert len(result) == 1
        assert handler.is_streaming is False

    def test_poll_queue_with_non_dict_item(self, handler, mock_agent):
        """Un item non-dict dans la file ne crashe pas (stocké mais pas traité)."""
        agent, q = mock_agent
        handler.start_stream(agent, "Test", [])
        q.put("string_item")  # Non-standard mais ne doit pas crasher
        result = handler.poll_queue()
        assert len(result) == 1

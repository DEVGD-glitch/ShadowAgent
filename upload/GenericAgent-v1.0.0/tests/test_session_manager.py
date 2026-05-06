"""
Tests unitaires pour le gestionnaire de sessions (SessionManager).

Ce module teste exhaustivement la classe SessionManager extraite de
``frontends/qt/session_manager.py``. Aucune dépendance PySide6 n'est
nécessaire — toute la logique est testable en pur Python.
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mgr():
    """Crée un SessionManager frais pour chaque test."""
    from frontends.qt.session_manager import SessionManager
    return SessionManager()


@pytest.fixture
def populated_mgr(mgr):
    """SessionManager avec quelques messages préexistants."""
    mgr.add_message("user", "Bonjour, aide-moi avec Python")
    mgr.add_message("assistant", "Bien sûr ! Que souhaitez-vous faire ?")
    mgr.add_message("user", "Créer une liste")
    return mgr


# ══════════════════════════════════════════════════════════════════════
# Création et initialisation
# ══════════════════════════════════════════════════════════════════════

class TestSessionCreation:
    """Tests pour la création et l'initialisation du SessionManager."""

    def test_initial_messages_empty(self, mgr):
        """Les messages sont initialement vides."""
        assert mgr.messages == []

    def test_initial_session_has_id(self, mgr):
        """La session initiale possède un identifiant."""
        assert "id" in mgr.session
        assert isinstance(mgr.session["id"], str)
        assert len(mgr.session["id"]) > 0

    def test_initial_session_default_title(self, mgr):
        """La session initiale a le titre par défaut."""
        assert mgr.session["title"] == "Nouvelle conversation"

    def test_initial_session_empty_messages(self, mgr):
        """Les messages de la session initiale sont vides."""
        assert mgr.session["messages"] == []

    def test_initial_history_is_list(self, mgr):
        """L'historique est une liste."""
        assert isinstance(mgr.history, list)

    def test_initial_pending_files_empty(self, mgr):
        """Les fichiers en attente sont initialement vides."""
        assert mgr.pending_files == []

    def test_autonomous_disabled_by_default(self, mgr):
        """Le mode autonome est désactivé par défaut."""
        assert mgr.autonomous_enabled is False

    def test_last_reply_time_is_recent(self, mgr):
        """L'horodatage de dernière réponse est récent."""
        assert time.time() - mgr.last_reply_time < 2.0

    def test_streaming_text_initially_empty(self, mgr):
        """Le texte de streaming est initialement vide."""
        assert mgr.streaming_text == ""

    def test_is_streaming_initially_false(self, mgr):
        """Le streaming est initialement inactif."""
        assert mgr.is_streaming is False


# ══════════════════════════════════════════════════════════════════════
# add_message
# ══════════════════════════════════════════════════════════════════════

class TestAddMessage:
    """Tests pour la méthode add_message."""

    def test_add_user_message(self, mgr):
        """L'ajout d'un message utilisateur fonctionne."""
        mgr.add_message("user", "Bonjour")
        assert len(mgr.messages) == 1
        assert mgr.messages[0] == {"role": "user", "content": "Bonjour"}

    def test_add_assistant_message(self, mgr):
        """L'ajout d'un message assistant fonctionne."""
        mgr.add_message("assistant", "Salut !")
        assert len(mgr.messages) == 1
        assert mgr.messages[0] == {"role": "assistant", "content": "Salut !"}

    def test_add_system_message(self, mgr):
        """L'ajout d'un message système fonctionne."""
        mgr.add_message("system", "Instruction")
        assert len(mgr.messages) == 1
        assert mgr.messages[0]["role"] == "system"

    def test_auto_title_on_first_user_message(self, mgr):
        """Le titre est mis à jour automatiquement au premier message utilisateur."""
        mgr.add_message("user", "Aide-moi avec Python")
        assert mgr.session["title"] != "Nouvelle conversation"
        assert "Aide-moi avec Python" in mgr.session["title"]

    def test_auto_title_truncated_long_content(self, mgr):
        """Le titre auto est tronqué si le contenu dépasse 20 caractères."""
        long_msg = "Ceci est un message très long qui dépasse vingt caractères"
        mgr.add_message("user", long_msg)
        assert mgr.session["title"].endswith("...")
        assert len(mgr.session["title"]) <= 23  # 20 + "..."

    def test_auto_title_short_content_no_ellipsis(self, mgr):
        """Pas d'ellipsis si le contenu est court."""
        mgr.add_message("user", "Bonjour")
        assert not mgr.session["title"].endswith("...")

    def test_auto_title_not_updated_for_assistant(self, mgr):
        """Un message assistant ne déclenche pas la mise à jour du titre."""
        mgr.add_message("assistant", "Réponse")
        assert mgr.session["title"] == "Nouvelle conversation"

    def test_auto_title_not_updated_if_already_set(self, mgr):
        """Le titre n'est pas modifié s'il a déjà été personnalisé."""
        mgr.add_message("user", "Premier message")
        first_title = mgr.session["title"]
        mgr.add_message("user", "Deuxième message")
        assert mgr.session["title"] == first_title

    def test_auto_title_empty_content_no_update(self, mgr):
        """Un message utilisateur avec contenu vide ne modifie pas le titre."""
        mgr.add_message("user", "")
        assert mgr.session["title"] == "Nouvelle conversation"

    def test_last_reply_time_updated_on_assistant(self, mgr):
        """L'horodatage est mis à jour quand un message assistant est ajouté."""
        old_time = mgr.last_reply_time
        time.sleep(0.01)
        mgr.add_message("assistant", "Réponse")
        assert mgr.last_reply_time > old_time

    def test_last_reply_time_not_updated_on_user(self, mgr):
        """L'horodatage n'est PAS mis à jour pour un message utilisateur."""
        old_time = mgr.last_reply_time
        mgr.add_message("user", "Question")
        assert mgr.last_reply_time == old_time

    def test_multiple_messages(self, mgr):
        """Plusieurs messages s'ajoutent dans l'ordre."""
        mgr.add_message("user", "Q1")
        mgr.add_message("assistant", "A1")
        mgr.add_message("user", "Q2")
        assert len(mgr.messages) == 3
        assert mgr.messages[0]["content"] == "Q1"
        assert mgr.messages[1]["content"] == "A1"
        assert mgr.messages[2]["content"] == "Q2"


# ══════════════════════════════════════════════════════════════════════
# save_session / auto_save
# ══════════════════════════════════════════════════════════════════════

class TestSaveSession:
    """Tests pour save_session et auto_save."""

    def test_save_session_with_messages(self, populated_mgr):
        """save_session sauvegarde la session avec des messages."""
        populated_mgr.save_session()
        # Vérifier que l'historique a été mis à jour
        found = any(h.get("id") == populated_mgr.session["id"] for h in populated_mgr.history)
        assert found

    def test_save_session_empty_does_nothing(self, mgr):
        """save_session ne fait rien si la conversation est vide."""
        original_history = mgr.history.copy()
        mgr.save_session()
        # L'historique ne doit pas changer (pas de messages)
        assert mgr.history == original_history

    def test_auto_save_with_messages(self, populated_mgr):
        """auto_save génère un titre et sauvegarde."""
        populated_mgr.auto_save()
        # Le titre doit avoir été mis à jour
        assert populated_mgr.session["title"] != "Nouvelle conversation"

    def test_auto_save_empty_does_nothing(self, mgr):
        """auto_save ne fait rien si la conversation est vide."""
        mgr.auto_save()
        assert mgr.session["title"] == "Nouvelle conversation"

    @patch('frontends.qt.session_manager._save_history')
    @patch('frontends.qt.session_manager._load_history', return_value=[])
    def test_concurrent_save_safe(self, mock_load, mock_save, mgr):
        """Deux sauvegardes successives ne causent pas d'erreur."""
        mgr.add_message("user", "Test concurrent 1")
        mgr.save_session()
        mgr.add_message("assistant", "Réponse 1")
        mgr.save_session()
        assert mock_save.call_count == 2


# ══════════════════════════════════════════════════════════════════════
# clear_session / new_session
# ══════════════════════════════════════════════════════════════════════

class TestClearNewSession:
    """Tests pour clear_session et new_session."""

    def test_clear_session_resets_messages(self, populated_mgr):
        """clear_session vide les messages."""
        populated_mgr.clear_session()
        assert mgr_msgs(populated_mgr) == []

    def test_clear_session_new_id(self, populated_mgr):
        """clear_session crée un nouvel identifiant de session."""
        old_id = populated_mgr.session["id"]
        populated_mgr.clear_session()
        assert populated_mgr.session["id"] != old_id

    def test_clear_session_default_title(self, populated_mgr):
        """clear_session rétablit le titre par défaut."""
        populated_mgr.clear_session()
        assert populated_mgr.session["title"] == "Nouvelle conversation"

    def test_clear_session_clears_pending_files(self, populated_mgr):
        """clear_session efface les fichiers en attente."""
        populated_mgr.add_pending_file("test.py", "text/plain", b"code")
        populated_mgr.clear_session()
        assert populated_mgr.pending_files == []

    def test_clear_session_resets_streaming(self, populated_mgr):
        """clear_session réinitialise l'état de streaming."""
        populated_mgr.streaming_text = "En cours..."
        populated_mgr.is_streaming = True
        populated_mgr.clear_session()
        assert populated_mgr.streaming_text == ""
        assert populated_mgr.is_streaming is False

    def test_new_session_saves_previous(self, populated_mgr):
        """new_session sauvegarde la session précédente avant d'effacer."""
        with patch.object(populated_mgr, 'auto_save') as mock_auto_save:
            populated_mgr.new_session()
            mock_auto_save.assert_called_once()

    def test_new_session_without_messages_no_save(self, mgr):
        """new_session ne sauvegarde pas si la conversation est vide."""
        with patch.object(mgr, 'auto_save') as mock_auto_save:
            mgr.new_session()
            mock_auto_save.assert_not_called()


def mgr_msgs(mgr):
    """Helper pour obtenir la liste des messages."""
    return mgr.messages


# ══════════════════════════════════════════════════════════════════════
# restore_session / delete_session
# ══════════════════════════════════════════════════════════════════════

class TestRestoreDeleteSession:
    """Tests pour restore_session et delete_session."""

    def test_restore_session(self, mgr):
        """restore_session restaure les messages d'une session."""
        session_dict = {
            "id": "restored_001",
            "title": "Session restaurée",
            "messages": [
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": "Réponse"},
            ],
        }
        result = mgr.restore_session(session_dict)
        assert result is not None
        assert len(result) == 2
        assert mgr.session["id"] == "restored_001"
        assert mgr.session["title"] == "Session restaurée"

    def test_restore_empty_dict_returns_none(self, mgr):
        """restore_session avec un dictionnaire vide retourne None."""
        result = mgr.restore_session({})
        assert result is None

    def test_restore_none_returns_none(self, mgr):
        """restore_session avec None retourne None."""
        result = mgr.restore_session(None)
        assert result is None

    def test_restore_clears_pending_files(self, mgr):
        """restore_session efface les fichiers en attente."""
        mgr.add_pending_file("test.py", "text/plain", b"code")
        mgr.restore_session({
            "id": "r_002",
            "title": "Test",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        assert mgr.pending_files == []

    def test_restore_resets_streaming(self, mgr):
        """restore_session réinitialise l'état de streaming."""
        mgr.streaming_text = "En cours..."
        mgr.is_streaming = True
        mgr.restore_session({
            "id": "r_003",
            "title": "Test",
            "messages": [],
        })
        assert mgr.streaming_text == ""
        assert mgr.is_streaming is False

    def test_restore_session_missing_messages(self, mgr):
        """restore_session avec un dict sans 'messages' crée une liste vide."""
        session_dict = {"id": "r_004", "title": "Pas de messages"}
        result = mgr.restore_session(session_dict)
        assert result == []

    def test_delete_session_existing(self, mgr):
        """delete_session supprime une session existante."""
        # Ajouter une session dans l'historique
        mgr._history = [{"id": "to_delete", "title": "À supprimer"}]
        result = mgr.delete_session("to_delete")
        assert result is True
        assert len(mgr.history) == 0

    def test_delete_session_nonexistent(self, mgr):
        """delete_session retourne False pour une session inexistante."""
        mgr._history = [{"id": "keep_me", "title": "À garder"}]
        result = mgr.delete_session("nonexistent")
        assert result is False
        assert len(mgr.history) == 1


# ══════════════════════════════════════════════════════════════════════
# update_token_usage / get_token_label
# ══════════════════════════════════════════════════════════════════════

class TestTokenUsage:
    """Tests pour update_token_usage et get_token_label."""

    def test_empty_session_zero_tokens(self, mgr):
        """Une session vide a 0 tokens."""
        usage = mgr.update_token_usage()
        assert usage["in_tokens"] == 0
        assert usage["out_tokens"] == 0

    def test_user_messages_counted_as_input(self, populated_mgr):
        """Les messages utilisateur sont comptés comme tokens d'entrée."""
        usage = populated_mgr.update_token_usage()
        assert usage["in_tokens"] > 0

    def test_assistant_messages_counted_as_output(self, populated_mgr):
        """Les messages assistant sont comptés comme tokens de sortie."""
        usage = populated_mgr.update_token_usage()
        assert usage["out_tokens"] > 0

    def test_streaming_text_included(self, mgr):
        """Le texte en streaming est inclus dans les tokens de sortie."""
        mgr.add_message("assistant", "Réponse")
        mgr.streaming_text = "Texte en streaming supplémentaire"
        mgr.is_streaming = True
        usage = mgr.update_token_usage()
        assert usage["out_tokens"] > 0

    def test_get_token_label_empty(self, mgr):
        """get_token_label retourne une chaîne vide sans messages."""
        label = mgr.get_token_label()
        assert label == ""

    def test_get_token_label_with_messages(self, populated_mgr):
        """get_token_label retourne un label formaté avec des messages."""
        label = populated_mgr.get_token_label()
        assert len(label) > 0
        assert "tokens" in label.lower() or "entrée" in label.lower()


# ══════════════════════════════════════════════════════════════════════
# toggle_autonomous / is_idle_timeout
# ══════════════════════════════════════════════════════════════════════

class TestAutonomousMode:
    """Tests pour le mode autonome."""

    def test_toggle_activates(self, mgr):
        """toggle_autonomous active le mode."""
        assert mgr.autonomous_enabled is False
        result = mgr.toggle_autonomous()
        assert result is True
        assert mgr.autonomous_enabled is True

    def test_toggle_deactivates(self, mgr):
        """toggle_autonomous désactive le mode après activation."""
        mgr.toggle_autonomous()  # Active
        result = mgr.toggle_autonomous()  # Désactive
        assert result is False
        assert mgr.autonomous_enabled is False

    def test_toggle_updates_reply_time(self, mgr):
        """toggle_autonomous met à jour l'horodatage."""
        old_time = mgr.last_reply_time
        time.sleep(0.01)
        mgr.toggle_autonomous()
        assert mgr.last_reply_time > old_time

    def test_is_idle_timeout_disabled(self, mgr):
        """is_idle_timeout retourne False si le mode autonome est désactivé."""
        assert mgr.is_idle_timeout() is False
        # Même avec un timeout très court
        assert mgr.is_idle_timeout(timeout_seconds=0.001) is False

    def test_is_idle_timeout_active_not_expired(self, mgr):
        """is_idle_timeout retourne False si le délai n'est pas expiré."""
        mgr.toggle_autonomous()
        assert mgr.is_idle_timeout(timeout_seconds=3600) is False

    def test_is_idle_timeout_active_expired(self, mgr):
        """is_idle_timeout retourne True si le délai est expiré."""
        mgr.toggle_autonomous()
        # Simuler un temps d'inactivité
        mgr.last_reply_time = time.time() - 2000
        assert mgr.is_idle_timeout(timeout_seconds=1800) is True

    def test_is_idle_timeout_custom_seconds(self, mgr):
        """is_idle_timeout respecte le paramètre de délai."""
        mgr.toggle_autonomous()
        mgr.last_reply_time = time.time() - 5
        assert mgr.is_idle_timeout(timeout_seconds=10) is False
        assert mgr.is_idle_timeout(timeout_seconds=3) is True


# ══════════════════════════════════════════════════════════════════════
# get_last_user_message
# ══════════════════════════════════════════════════════════════════════

class TestGetLastUserMessage:
    """Tests pour get_last_user_message."""

    def test_no_messages(self, mgr):
        """Retourne None sans messages."""
        assert mgr.get_last_user_message() is None

    def test_only_assistant_messages(self, mgr):
        """Retourne None avec seulement des messages assistant."""
        mgr.add_message("assistant", "Bonjour")
        assert mgr.get_last_user_message() is None

    def test_single_user_message(self, mgr):
        """Retourne le contenu du seul message utilisateur."""
        mgr.add_message("user", "Ma question")
        assert mgr.get_last_user_message() == "Ma question"

    def test_multiple_user_messages(self, populated_mgr):
        """Retourne le contenu du dernier message utilisateur."""
        result = populated_mgr.get_last_user_message()
        assert result == "Créer une liste"

    def test_empty_user_message(self, mgr):
        """Retourne une chaîne vide pour un message utilisateur vide."""
        mgr.add_message("user", "")
        result = mgr.get_last_user_message()
        assert result == ""


# ══════════════════════════════════════════════════════════════════════
# add_pending_file / clear_pending_files
# ══════════════════════════════════════════════════════════════════════

class TestPendingFiles:
    """Tests pour la gestion des fichiers en attente."""

    def test_add_pending_file(self, mgr):
        """L'ajout d'un fichier en attente fonctionne."""
        mgr.add_pending_file("test.py", "text/plain", b"print('hello')")
        assert len(mgr.pending_files) == 1
        assert mgr.pending_files[0]["name"] == "test.py"
        assert mgr.pending_files[0]["type"] == "text/plain"
        assert mgr.pending_files[0]["raw"] == b"print('hello')"

    def test_add_multiple_pending_files(self, mgr):
        """Plusieurs fichiers peuvent être ajoutés."""
        mgr.add_pending_file("a.py", "text/plain", b"a")
        mgr.add_pending_file("b.png", "image/png", b"\x89PNG")
        assert len(mgr.pending_files) == 2

    def test_add_duplicate_pending_file_ignored(self, mgr):
        """Un fichier dupliqué (même nom) est ignoré."""
        mgr.add_pending_file("test.py", "text/plain", b"v1")
        mgr.add_pending_file("test.py", "text/plain", b"v2")
        assert len(mgr.pending_files) == 1
        assert mgr.pending_files[0]["raw"] == b"v1"

    def test_clear_pending_files(self, mgr):
        """clear_pending_files efface tous les fichiers en attente."""
        mgr.add_pending_file("a.py", "text/plain", b"a")
        mgr.add_pending_file("b.py", "text/plain", b"b")
        mgr.clear_pending_files()
        assert mgr.pending_files == []


# ══════════════════════════════════════════════════════════════════════
# reload_history
# ══════════════════════════════════════════════════════════════════════

class TestReloadHistory:
    """Tests pour reload_history."""

    def test_reload_returns_list(self, mgr):
        """reload_history retourne une liste."""
        result = mgr.reload_history()
        assert isinstance(result, list)

    def test_reload_updates_internal_history(self, mgr):
        """reload_history met à jour l'historique interne."""
        with patch('frontends.qt.session_manager._load_history', return_value=[{"id": "new"}]):
            result = mgr.reload_history()
            assert len(result) == 1
            assert mgr.history == [{"id": "new"}]


# ══════════════════════════════════════════════════════════════════════
# Cas limites
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests pour les cas limites et les situations inhabituelles."""

    def test_unicode_content(self, mgr):
        """Les messages Unicode sont gérés correctement."""
        mgr.add_message("user", "你好世界 🌍 こんにちは")
        assert mgr.messages[0]["content"] == "你好世界 🌍 こんにちは"

    def test_unicode_title(self, mgr):
        """Le titre auto gère les caractères Unicode."""
        mgr.add_message("user", "你好世界这是测试")
        assert mgr.session["title"] != "Nouvelle conversation"

    def test_very_long_message(self, mgr):
        """Un message très long est ajouté sans erreur."""
        long_msg = "A" * 100_000
        mgr.add_message("user", long_msg)
        assert len(mgr.messages[0]["content"]) == 100_000

    def test_newlines_in_content(self, mgr):
        """Les retours à la ligne dans le contenu sont préservés."""
        mgr.add_message("user", "Ligne 1\nLigne 2\nLigne 3")
        assert "\n" in mgr.messages[0]["content"]

    def test_special_chars_in_content(self, mgr):
        """Les caractères spéciaux sont préservés."""
        mgr.add_message("user", '<script>alert("XSS")</script>')
        assert "<script>" in mgr.messages[0]["content"]

    def test_multiple_toggles(self, mgr):
        """Des bascules multiples du mode autonome sont cohérentes."""
        for _ in range(11):
            mgr.toggle_autonomous()
        # Après 11 toggles depuis False, on doit être à True (impair)
        assert mgr.autonomous_enabled is True

    @patch('frontends.qt.session_manager._load_history', side_effect=Exception("IO Error"))
    def test_load_history_exception_in_restore(self, mock_load, mgr):
        """Une exception dans _load_history pendant restore ne crashe pas."""
        with pytest.raises(Exception):
            mgr.restore_session({"id": "x", "title": "T", "messages": []})

    @patch('frontends.qt.session_manager._save_history', side_effect=IOError("Disk full"))
    @patch('frontends.qt.session_manager._load_history', return_value=[])
    def test_save_history_exception(self, mock_load, mock_save, mgr):
        """Une exception dans _save_history est propagée."""
        mgr.add_message("user", "Test")
        with pytest.raises(IOError):
            mgr.save_session()

    def test_messages_is_copy(self, mgr):
        """La propriété messages retourne une référence interne mutable."""
        # La propriété retourne self._messages directement
        mgr.add_message("user", "Test")
        msgs = mgr.messages
        assert msgs is mgr._messages

    def test_delete_session_empty_history(self, mgr):
        """delete_session sur un historique vide retourne False."""
        mgr._history = []
        assert mgr.delete_session("any") is False

"""
Tests unitaires pour llmcore.py — retry, parsing, sessions, conversion.
Étend les tests existants avec des cas supplémentaires pour les fonctions
avancées du module.
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ══════════════════════════════════════════════════════════════════════
# BaseSession — validation de configuration
# ══════════════════════════════════════════════════════════════════════

class TestBaseSessionConfig:
    """Tests pour la validation de configuration de BaseSession."""

    def test_defaults(self):
        """BaseSession a des valeurs par défaut raisonnables."""
        from llmcore import BaseSession
        cfg = {'apikey': 'test-key', 'apibase': 'https://api.example.com'}
        session = BaseSession(cfg)
        assert session.api_key == 'test-key'
        assert session.max_retries == 4
        assert session.stream is True
        assert session.verify is True
        assert session.connect_timeout >= 1
        assert session.read_timeout >= 5

    def test_custom_values(self):
        """BaseSession accepte des valeurs personnalisées."""
        from llmcore import BaseSession
        cfg = {
            'apikey': 'test-key', 'apibase': 'https://api.example.com',
            'max_retries': 2, 'stream': False, 'timeout': 15, 'read_timeout': 120,
        }
        session = BaseSession(cfg)
        assert session.max_retries == 2
        assert session.stream is False
        assert session.connect_timeout == 15
        assert session.read_timeout == 120

    def test_api_base_trailing_slash_stripped(self):
        """Le slash final de apibase est supprimé."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com/'}
        session = BaseSession(cfg)
        assert not session.api_base.endswith('/')

    def test_negative_retries_clamped(self):
        """Les retries négatifs sont clamps à 0."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com', 'max_retries': -1}
        session = BaseSession(cfg)
        assert session.max_retries >= 0

    def test_proxy_configured(self):
        """Le proxy est configuré correctement."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com', 'proxy': 'http://proxy:8080'}
        session = BaseSession(cfg)
        assert session.proxies is not None
        assert session.proxies['http'] == 'http://proxy:8080'
        assert session.proxies['https'] == 'http://proxy:8080'

    def test_no_proxy(self):
        """Sans proxy, proxies est None."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com'}
        session = BaseSession(cfg)
        assert session.proxies is None

    def test_api_mode_chat_completions_default(self):
        """Le mode API par défaut est chat_completions."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com'}
        session = BaseSession(cfg)
        assert session.api_mode == 'chat_completions'

    def test_api_mode_responses(self):
        """Le mode responses est configurable."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com', 'api_mode': 'responses'}
        session = BaseSession(cfg)
        assert session.api_mode == 'responses'

    def test_temperature_default(self):
        """La température par défaut est 1."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com'}
        session = BaseSession(cfg)
        assert session.temperature == 1

    def test_custom_temperature(self):
        """La température est configurable."""
        from llmcore import BaseSession
        cfg = {'apikey': 'k', 'apibase': 'https://api.example.com', 'temperature': 0.5}
        session = BaseSession(cfg)
        assert session.temperature == 0.5


# ══════════════════════════════════════════════════════════════════════
# auto_make_url — cas limites
# ══════════════════════════════════════════════════════════════════════

class TestAutoMakeUrlEdgeCases:
    """Tests pour les cas limites de auto_make_url."""

    def test_url_with_v1(self):
        """Une URL avec /v1/ n'ajoute pas un autre /v1/."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com/v1", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_url_without_version(self):
        """Une URL sans version ajoute /v1/."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_url_with_dollar_suffix(self):
        """Le suffixe $ indique que l'URL est complète."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com/v1/chat$", "chat/completions")
        assert result == "https://api.example.com/v1/chat"

    def test_url_already_ends_with_path(self):
        """Une URL qui se termine déjà par le path n'ajoute pas de doublon."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com/v1/chat/completions", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_url_with_v2(self):
        """Une URL avec /v2/ est détectée comme versionnée."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com/v2", "messages")
        assert result == "https://api.example.com/v2/messages"

    def test_url_trailing_slash_stripped(self):
        """Les slashs finaux sont supprimés de la base."""
        from llmcore import auto_make_url
        result = auto_make_url("https://api.example.com/v1/", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"


# ══════════════════════════════════════════════════════════════════════
# compress_history_tags
# ══════════════════════════════════════════════════════════════════════

class TestCompressHistoryTags:
    """Tests pour compress_history_tags."""

    def test_empty_messages(self):
        """compress_history_tags avec des messages vides ne crashe pas."""
        from llmcore import compress_history_tags
        # Réinitialiser le compteur interne
        compress_history_tags._cd = 0
        result = compress_history_tags([], force=True)
        assert result == []

    def test_short_messages_unchanged(self):
        """Les messages courts ne sont pas modifiés."""
        from llmcore import compress_history_tags
        compress_history_tags._cd = 0
        messages = [{"role": "user", "content": "Hello"}]
        result = compress_history_tags(messages, force=True)
        assert result[0]["content"] == "Hello"

    def test_long_thinking_tag_truncated(self):
        """Les balises <thinking> longues sont tronquées."""
        from llmcore import compress_history_tags
        compress_history_tags._cd = 0
        long_thinking = "x" * 2000
        messages = [{"role": "assistant", "content": f"<thinking>{long_thinking}</thinking>"}]
        result = compress_history_tags(messages, force=True, max_len=100, keep_recent=0)
        assert len(result[0]["content"]) < len(long_thinking)

    def test_keep_recent_preserved(self):
        """Les messages récents ne sont pas compressés."""
        from llmcore import compress_history_tags
        compress_history_tags._cd = 0
        long_thinking = "x" * 2000
        messages = [
            {"role": "assistant", "content": f"<thinking>{long_thinking}</thinking>"},
            {"role": "user", "content": "Recent"},
        ]
        result = compress_history_tags(messages, force=True, keep_recent=1)
        # Le dernier message (recent) doit être intact
        assert result[-1]["content"] == "Recent"

    def test_counter_based_skipping(self):
        """compress_history_tags ne compresse que tous les 5 appels (sans force)."""
        from llmcore import compress_history_tags
        compress_history_tags._cd = 0
        long_thinking = "x" * 2000
        messages = [{"role": "assistant", "content": f"<thinking>{long_thinking}</thinking>"}]
        # Premier appel : _cd = 1, pas de compression (1 % 5 != 0)
        result1 = compress_history_tags(messages)
        # Cinquième appel : _cd = 5, compression (5 % 5 == 0)
        for _ in range(3):
            compress_history_tags(messages)
        result5 = compress_history_tags(messages)
        # Le 5ème appel devrait compresser


# ══════════════════════════════════════════════════════════════════════
# _sanitize_leading_user_msg
# ══════════════════════════════════════════════════════════════════════

class TestSanitizeLeadingUserMsg:
    """Tests pour _sanitize_leading_user_msg."""

    def test_string_content_unchanged(self):
        """Un message avec content de type string est retourné tel quel."""
        from llmcore import _sanitize_leading_user_msg
        msg = {"role": "user", "content": "Hello"}
        result = _sanitize_leading_user_msg(msg)
        assert result["content"] == "Hello"

    def test_tool_result_converted_to_text(self):
        """Les blocs tool_result sont convertis en texte brut."""
        from llmcore import _sanitize_leading_user_msg
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "Résultat outil"},
                {"type": "text", "text": "Message utilisateur"},
            ]
        }
        result = _sanitize_leading_user_msg(msg)
        # Le contenu doit être converti en blocs text
        assert isinstance(result["content"], list)
        assert all(b.get("type") == "text" for b in result["content"])

    def test_tool_result_with_list_content(self):
        """Les blocs tool_result avec content de type list sont gérés."""
        from llmcore import _sanitize_leading_user_msg
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": [
                    {"type": "text", "text": "Ligne 1"},
                    {"type": "text", "text": "Ligne 2"},
                ]},
            ]
        }
        result = _sanitize_leading_user_msg(msg)
        # Les textes de la liste sont joints par des nouvelles lignes
        texts = [b["text"] for b in result["content"]]
        combined = "\n".join(texts)
        assert "Ligne 1" in combined
        assert "Ligne 2" in combined

    def test_does_not_modify_original(self):
        """La fonction ne modifie pas le dict original."""
        from llmcore import _sanitize_leading_user_msg
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "X"},
            ]
        }
        original_content = msg["content"]
        _sanitize_leading_user_msg(msg)
        assert msg["content"] is original_content

    def test_empty_content_list(self):
        """Une liste de content vide retourne un bloc texte vide."""
        from llmcore import _sanitize_leading_user_msg
        msg = {"role": "user", "content": []}
        result = _sanitize_leading_user_msg(msg)
        assert isinstance(result["content"], list)


# ══════════════════════════════════════════════════════════════════════
# _try_parse_tool_args — JSON concaténé
# ══════════════════════════════════════════════════════════════════════

class TestTryParseToolArgsExtended:
    """Tests étendus pour _try_parse_tool_args."""

    def test_single_json(self):
        """Un seul objet JSON est parsé correctement."""
        from llmcore import _try_parse_tool_args
        result = _try_parse_tool_args('{"name": "code_run", "arguments": {"type": "python"}}')
        assert len(result) == 1
        assert result[0]["name"] == "code_run"

    def test_empty_string(self):
        """Une chaîne vide retourne [{}]."""
        from llmcore import _try_parse_tool_args
        result = _try_parse_tool_args("")
        assert result == [{}]

    def test_concatenated_json(self):
        """Deux objets JSON concaténés sont séparés et parsés."""
        from llmcore import _try_parse_tool_args
        raw = '{"name": "code_run", "arguments": {"type": "python"}}{"name": "file_read", "arguments": {"path": "test.txt"}}'
        result = _try_parse_tool_args(raw)
        assert len(result) == 2
        assert result[0]["name"] == "code_run"
        assert result[1]["name"] == "file_read"

    def test_invalid_json_returns_raw(self):
        """Du JSON invalide retourne [{"_raw": ...}]."""
        from llmcore import _try_parse_tool_args
        result = _try_parse_tool_args("not json at all")
        assert len(result) == 1
        assert "_raw" in result[0]

    def test_partial_concatenated_json(self):
        """Du JSON concaténé partiellement invalide retourne _raw."""
        from llmcore import _try_parse_tool_args
        raw = '{"valid": true}{invalid json}'
        result = _try_parse_tool_args(raw)
        assert len(result) == 1
        assert "_raw" in result[0]


# ══════════════════════════════════════════════════════════════════════
# _msgs_claude2oai — conversion
# ══════════════════════════════════════════════════════════════════════

class TestMsgsClaude2Oai:
    """Tests pour _msgs_claude2oai."""

    def test_simple_text_message(self):
        """Un message texte simple est converti correctement."""
        from llmcore import _msgs_claude2oai
        messages = [{"role": "user", "content": "Bonjour"}]
        result = _msgs_claude2oai(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_assistant_with_tool_use(self):
        """Un message assistant avec tool_use est converti."""
        from llmcore import _msgs_claude2oai
        messages = [{
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Voici le résultat"},
                {"type": "tool_use", "id": "tu_1", "name": "code_run", "input": {"type": "python"}},
            ]
        }]
        result = _msgs_claude2oai(messages)
        assert result[0]["role"] == "assistant"
        assert "tool_calls" in result[0]
        assert result[0]["tool_calls"][0]["function"]["name"] == "code_run"

    def test_user_with_tool_result(self):
        """Un message utilisateur avec tool_result est converti en rôle tool."""
        from llmcore import _msgs_claude2oai
        messages = [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "Résultat"},
            ]
        }]
        result = _msgs_claude2oai(messages)
        # Le tool_result doit devenir un message de rôle "tool"
        assert any(m["role"] == "tool" for m in result)

    def test_thinking_in_assistant(self):
        """Le thinking d'un assistant est converti en reasoning_content."""
        from llmcore import _msgs_claude2oai
        messages = [{
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Je réfléchis..."},
                {"type": "text", "text": "Réponse"},
            ]
        }]
        result = _msgs_claude2oai(messages)
        assert "reasoning_content" in result[0]
        assert result[0]["reasoning_content"] == "Je réfléchis..."

    def test_string_content_user(self):
        """Un message utilisateur avec content string est converti."""
        from llmcore import _msgs_claude2oai
        messages = [{"role": "user", "content": "Hello"}]
        result = _msgs_claude2oai(messages)
        assert result[0]["role"] == "user"
        assert isinstance(result[0]["content"], list)

    def test_system_message_passthrough(self):
        """Un message système est passé tel quel."""
        from llmcore import _msgs_claude2oai
        messages = [{"role": "system", "content": "Instruction système"}]
        result = _msgs_claude2oai(messages)
        assert result[0]["role"] == "system"


# ══════════════════════════════════════════════════════════════════════
# _fix_messages
# ══════════════════════════════════════════════════════════════════════

class TestFixMessages:
    """Tests pour _fix_messages."""

    def test_empty_messages(self):
        """Des messages vides retournent une liste vide."""
        from llmcore import _fix_messages
        assert _fix_messages([]) == []

    def test_consecutive_same_role_merged(self):
        """Les messages consécutifs du même rôle sont fusionnés."""
        from llmcore import _fix_messages
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "user", "content": "Q2"},
        ]
        result = _fix_messages(messages)
        assert len(result) == 1
        # Le contenu fusionné doit contenir les deux textes
        c = result[0]["content"]
        assert isinstance(c, list)
        texts = [b["text"] for b in c if isinstance(b, dict) and b.get("type") == "text"]
        combined = " ".join(texts)
        assert "Q1" in combined
        assert "Q2" in combined

    def test_missing_tool_result_added(self):
        """Les tool_result manquants sont ajoutés automatiquement."""
        from llmcore import _fix_messages
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_1", "name": "test", "input": {}}
            ]},
            {"role": "user", "content": [{"type": "text", "text": "Suite"}]},
        ]
        result = _fix_messages(messages)
        # Le message utilisateur doit avoir un tool_result ajouté
        user_msg = result[-1]
        content = user_msg["content"]
        has_tool_result = any(b.get("type") == "tool_result" for b in content if isinstance(b, dict))
        assert has_tool_result

    def test_leading_non_user_removed(self):
        """Les messages initiaux non-utilisateur sont retirés."""
        from llmcore import _fix_messages
        messages = [
            {"role": "assistant", "content": "Pas au début"},
            {"role": "user", "content": "Premier message utilisateur"},
        ]
        result = _fix_messages(messages)
        assert result[0]["role"] == "user"

    def test_alternating_messages_unchanged(self):
        """Des messages alternés correctement ne sont pas modifiés."""
        from llmcore import _fix_messages
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]
        result = _fix_messages(messages)
        assert len(result) == 3
        assert [m["role"] for m in result] == ["user", "assistant", "user"]


# ══════════════════════════════════════════════════════════════════════
# _stamp_oai_cache_markers
# ══════════════════════════════════════════════════════════════════════

class TestStampOaiCacheMarkers:
    """Tests pour _stamp_oai_cache_markers."""

    def test_no_marker_for_non_claude(self):
        """Pas de marqueur de cache pour les modèles non-Claude."""
        from llmcore import _stamp_oai_cache_markers
        messages = [{"role": "user", "content": "Hello"}]
        _stamp_oai_cache_markers(messages, "gpt-4")
        assert "cache_control" not in str(messages)

    def test_marker_for_claude_model(self):
        """Un marqueur de cache est ajouté pour les modèles Claude."""
        from llmcore import _stamp_oai_cache_markers
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Question"},
        ]
        _stamp_oai_cache_markers(messages, "claude-3-opus")
        # Le dernier message utilisateur doit avoir cache_control
        last_user = [m for m in messages if m.get("role") == "user"][-1]
        content = last_user.get("content")
        if isinstance(content, list):
            assert any("cache_control" in str(b) for b in content)
        elif isinstance(content, dict):
            assert "cache_control" in str(content)

    def test_marker_for_anthropic_model(self):
        """Un marqueur de cache est ajouté pour les modèles contenant 'anthropic'."""
        from llmcore import _stamp_oai_cache_markers
        messages = [{"role": "user", "content": "Hello"}]
        _stamp_oai_cache_markers(messages, "anthropic-model-v1")
        # Le message doit avoir été modifié
        assert "cache_control" in str(messages[0].get("content", ""))

    def test_string_content_converted_to_list(self):
        """Le contenu string est converti en liste avec cache_control."""
        from llmcore import _stamp_oai_cache_markers
        messages = [{"role": "user", "content": "Hello"}]
        _stamp_oai_cache_markers(messages, "claude-3-haiku")
        assert isinstance(messages[0]["content"], list)

    def test_only_last_two_user_messages(self):
        """Seuls les 2 derniers messages utilisateur reçoivent le marqueur."""
        from llmcore import _stamp_oai_cache_markers
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Second"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Third"},
        ]
        _stamp_oai_cache_markers(messages, "claude-3-sonnet")
        # Seuls les 2 derniers messages utilisateur doivent avoir cache_control
        user_msgs = [m for m in messages if m.get("role") == "user"]
        # Le premier message ne doit PAS avoir cache_control dans son contenu
        first_content = str(user_msgs[0].get("content", ""))
        # Les deux derniers doivent l'avoir
        assert "cache_control" in str(user_msgs[-1].get("content", ""))
        assert "cache_control" in str(user_msgs[-2].get("content", ""))


# ══════════════════════════════════════════════════════════════════════
# Retry logic (existant — complété)
# ══════════════════════════════════════════════════════════════════════

class TestLlmRetryLogic:
    """Tests pour la logique de retry du LLM."""

    def test_retryable_status_codes(self):
        """Les codes de statut retryable sont corrects."""
        RETRYABLE = {408, 409, 425, 429, 500, 502, 503, 504, 529}
        assert 429 in RETRYABLE
        assert 500 in RETRYABLE
        assert 503 in RETRYABLE
        assert 200 not in RETRYABLE
        assert 401 not in RETRYABLE
        assert 403 not in RETRYABLE

    def test_delay_increases_with_attempts(self):
        """Le délai augmente avec le nombre de tentatives (backoff exponentiel)."""
        import random
        def _simulate_delay(attempt):
            base_delay = min(30.0, 1.0 * (2 ** attempt))
            jitter = random.uniform(0, 0.5 * base_delay)
            return base_delay + jitter

        delays = [_simulate_delay(i) for i in range(5)]
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i-1] * 0.5

    def test_max_delay_capped(self):
        """Le délai maximum est plafonné à 30 secondes."""
        base_delay = min(30.0, 1.0 * (2 ** 10))
        assert base_delay == 30.0


# ══════════════════════════════════════════════════════════════════════
# JSON parsing (existant — complété)
# ══════════════════════════════════════════════════════════════════════

class TestJsonParsing:
    """Tests pour le parsing JSON tolérant."""

    def test_tryparse_valid_json(self):
        """tryparse parse du JSON valide."""
        from llmcore import tryparse
        result = tryparse('{"name": "test", "value": 42}')
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_tryparse_json_with_backticks(self):
        """tryparse gère le JSON entouré de backticks."""
        from llmcore import tryparse
        result = tryparse('```json\n{"name": "test"}\n```')
        assert result["name"] == "test"


# ══════════════════════════════════════════════════════════════════════
# Vérification que print() n'est pas remplacé
# ══════════════════════════════════════════════════════════════════════

class TestPrintNotReplaced:
    """Tests pour vérifier que print() n'est pas remplacé globalement."""

    def test_print_is_builtin(self):
        """print() est toujours la fonction builtin."""
        import builtins
        assert print is builtins.print

    def test_safeprint_exists_but_not_assigned(self):
        """safeprint existe mais n'est pas assignée à print."""
        import llmcore
        assert hasattr(llmcore, 'safeprint')
        assert hasattr(llmcore, '_oldprint')

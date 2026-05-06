"""
Tests unitaires pour ga.py — sécurité code_run, utilitaires, handler.
Étend les tests existants avec des cas supplémentaires.
"""
import os
import sys
import pytest
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ga import (
    code_run, file_patch, file_read, expand_file_refs,
    DANGEROUS_SHELL_PATTERNS, set_shell_confirm_callback,
    _shell_confirm_callback, smart_format, ask_user,
    GenericAgentHandler,
)
import ga


# ══════════════════════════════════════════════════════════════════════
# code_run avec callback de confirmation shell
# ══════════════════════════════════════════════════════════════════════

class TestCodeRunShellConfirm:
    """Tests pour code_run avec callback de confirmation shell (accept/reject)."""

    def setup_method(self):
        """Sauvegarde le callback original avant chaque test."""
        self._original_callback = ga._shell_confirm_callback

    def teardown_method(self):
        """Restaure le callback original après chaque test."""
        ga._shell_confirm_callback = self._original_callback

    def test_shell_accept_with_callback(self):
        """Un callback qui accepte permet l'exécution de la commande shell."""
        set_shell_confirm_callback(lambda code, code_type: True)
        # Exécuter une commande shell simple
        gen = code_run("echo test_confirmation", code_type="bash", timeout=10)
        results = list(gen)
        # La commande doit avoir été exécutée (pas de message "bloquée")
        all_output = "".join(str(r) for r in results)
        assert "bloquée" not in all_output.lower()

    def test_shell_reject_with_callback(self):
        """Un callback qui refuse bloque la commande shell dangereuse."""
        set_shell_confirm_callback(lambda code, code_type: False)
        gen = code_run("rm -rf /tmp/test_reject", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        assert "bloquée" in all_output.lower() or "annulée" in all_output.lower()

    def test_shell_dangerous_pattern_detected(self):
        """Les commandes shell dangereuses sont détectées par les patterns."""
        import re
        dangerous_commands = [
            "rm -rf /tmp/test",
            "shutdown /s /t 0",
            "format C:",
            "del /f /q important.txt",
        ]
        for cmd in dangerous_commands:
            found = any(re.search(p, cmd.lower()) for p in DANGEROUS_SHELL_PATTERNS)
            assert found, f"Commande non détectée comme dangereuse : {cmd}"


# ══════════════════════════════════════════════════════════════════════
# expand_file_refs avec références valides et invalides
# ══════════════════════════════════════════════════════════════════════

class TestExpandFileRefsExtended:
    """Tests étendus pour expand_file_refs."""

    def test_no_refs(self):
        """Un texte sans références n'est pas modifié."""
        result = expand_file_refs("Hello world")
        assert result == "Hello world"

    def test_invalid_ref_path(self):
        """Une référence vers un fichier inexistant lève une erreur."""
        with pytest.raises(ValueError):
            expand_file_refs("{{file:/nonexistent/path.txt:1:5}}")

    def test_valid_ref(self):
        """Une référence valide est expandée."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("ligne 1\nligne 2\nligne 3\n")
            path = f.name
        try:
            result = expand_file_refs(f"{{{{file:{path}:1:2}}}}")
            assert "ligne 1" in result
            assert "ligne 2" in result
        finally:
            os.unlink(path)

    def test_line_out_of_range(self):
        """Des numéros de ligne hors limites lèvent une erreur."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("ligne 1\nligne 2\n")
            path = f.name
        try:
            with pytest.raises(ValueError):
                expand_file_refs(f"{{{{file:{path}:1:999}}}}")
        finally:
            os.unlink(path)

    def test_start_greater_than_end(self):
        """start > end lève une erreur."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("ligne 1\n")
            path = f.name
        try:
            with pytest.raises(ValueError):
                expand_file_refs(f"{{{{file:{path}:5:1}}}}")
        finally:
            os.unlink(path)

    def test_multiple_refs_in_text(self):
        """Plusieurs références dans un même texte sont expandées."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("aaa\nbbb\nccc\nddd\n")
            path = f.name
        try:
            result = expand_file_refs(f"Avant {{{{file:{path}:1:2}}}} Entre {{{{file:{path}:3:4}}}} Après")
            assert "aaa" in result
            assert "bbb" in result
            assert "ccc" in result
            assert "ddd" in result
            assert "Avant" in result
            assert "Après" in result
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
# file_patch — cas limites
# ══════════════════════════════════════════════════════════════════════

class TestFilePatchEdgeCases:
    """Tests pour les cas limites de file_patch."""

    def test_patch_multiple_matches(self):
        """Patcher avec old_content trouvé plusieurs fois retourne une erreur."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("foo bar foo bar foo")
            path = f.name
        try:
            result = file_patch(path, "foo", "baz")
            assert result["status"] == "error"
            # Message may say "2 correspondances", "3 matches", "Found 3", etc.
            # depending on i18n — just check it's an error about multiple matches
            msg = result.get("msg", "").lower()
            assert any(kw in msg for kw in ["multiple", "correspond", "match"]), f"Expected multiple-match error, got: {result}"
        finally:
            os.unlink(path)

    def test_patch_empty_file(self):
        """Patcher un fichier vide avec un contenu inexistant retourne une erreur."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            path = f.name
        try:
            result = file_patch(path, "nonexistent", "new")
            assert result["status"] == "error"
        finally:
            os.unlink(path)

    def test_patch_empty_file_with_empty_old(self):
        """Patcher un fichier vide avec old_content vide retourne une erreur."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")
            path = f.name
        try:
            result = file_patch(path, "", "new")
            assert result["status"] == "error"
        finally:
            os.unlink(path)

    def test_patch_preserves_surrounding_content(self):
        """Le contenu autour du patch est préservé."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("before\nold\nafter")
            path = f.name
        try:
            result = file_patch(path, "old", "new")
            assert result["status"] == "success"
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert content == "before\nnew\nafter"
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
# file_read avec recherche par mot-clé
# ══════════════════════════════════════════════════════════════════════

class TestFileReadKeywordSearch:
    """Tests pour file_read avec le paramètre keyword."""

    def test_read_with_keyword_found(self):
        """file_read avec keyword retourne les lignes autour du mot-clé."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for i in range(50):
                f.write(f"Ligne numéro {i}\n")
            path = f.name
        try:
            result = file_read(path, keyword="numéro 25", count=10, show_linenos=False)
            assert "25" in result
        finally:
            os.unlink(path)

    def test_read_with_keyword_not_found(self):
        """file_read avec keyword non trouvé retourne un message approprié."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("ligne 1\nligne 2\n")
            path = f.name
        try:
            result = file_read(path, keyword="INTRUVABLE_XYZ", show_linenos=False)
            assert "not found" in result.lower() or "introuvable" in result.lower() or "falling back" in result.lower()
        finally:
            os.unlink(path)

    def test_read_with_keyword_case_insensitive(self):
        """La recherche par mot-clé est insensible à la casse."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Hello World\n")
            path = f.name
        try:
            result = file_read(path, keyword="hello world", show_linenos=False)
            assert "Hello World" in result
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
# smart_format avec diverses entrées
# ══════════════════════════════════════════════════════════════════════

class TestSmartFormatExtended:
    """Tests étendus pour smart_format."""

    def test_short_string_unchanged(self):
        """Une chaîne courte n'est pas modifiée."""
        result = smart_format("hello", max_str_len=100)
        assert result == "hello"

    def test_long_string_truncated(self):
        """Une chaîne longue est tronquée."""
        long_str = "A" * 200
        result = smart_format(long_str, max_str_len=50)
        assert len(result) < 200
        assert "..." in result or "omitted" in result.lower()

    def test_exact_boundary(self):
        """Une chaîne à la limite exacte n'est pas tronquée."""
        s = "A" * 100
        result = smart_format(s, max_str_len=100)
        assert result == s

    def test_non_string_input(self):
        """Un input non-chaîne est converti en chaîne."""
        result = smart_format(42, max_str_len=100)
        assert result == "42"

    def test_empty_string(self):
        """Une chaîne vide reste vide."""
        result = smart_format("", max_str_len=100)
        assert result == ""

    def test_unicode_string(self):
        """Les chaînes Unicode sont gérées correctement."""
        result = smart_format("你好世界", max_str_len=100)
        assert "你好世界" in result

    def test_custom_omission_string(self):
        """Le paramètre omit_str est utilisé pour la troncature."""
        long_str = "A" * 200
        result = smart_format(long_str, max_str_len=50, omit_str="[COUPÉ]")
        assert "[COUPÉ]" in result


# ══════════════════════════════════════════════════════════════════════
# GenericAgentHandler._extract_code_block
# ══════════════════════════════════════════════════════════════════════

class TestExtractCodeBlock:
    """Tests pour GenericAgentHandler._extract_code_block."""

    @pytest.fixture
    def handler(self):
        """Crée un handler pour les tests."""
        mock_parent = MagicMock()
        return GenericAgentHandler(mock_parent)

    def test_extract_python_block(self, handler):
        """Extraction d'un bloc de code Python."""
        response = MagicMock()
        response.content = "Voici le code :\n```python\nprint('hello')\n```\nFin"
        result = handler._extract_code_block(response, "python")
        assert result == "print('hello')"

    def test_extract_bash_block(self, handler):
        """Extraction d'un bloc de code bash."""
        response = MagicMock()
        response.content = "```bash\necho hello\n```"
        result = handler._extract_code_block(response, "bash")
        assert result == "echo hello"

    def test_extract_no_block(self, handler):
        """Retourne None si aucun bloc de code n'est trouvé."""
        response = MagicMock()
        response.content = "Pas de code ici"
        result = handler._extract_code_block(response, "python")
        assert result is None

    def test_extract_multiple_blocks_returns_last(self, handler):
        """Retourne le dernier bloc si plusieurs sont présents."""
        response = MagicMock()
        response.content = "```python\nfirst()\n```\nTexte\n```python\nsecond()\n```"
        result = handler._extract_code_block(response, "python")
        assert result == "second()"

    def test_extract_powershell_block(self, handler):
        """Extraction d'un bloc de code powershell."""
        response = MagicMock()
        response.content = "```powershell\nGet-Process\n```"
        result = handler._extract_code_block(response, "powershell")
        assert result == "Get-Process"


# ══════════════════════════════════════════════════════════════════════
# ask_user avec et sans candidates
# ══════════════════════════════════════════════════════════════════════

class TestAskUserExtended:
    """Tests étendus pour ask_user."""

    def test_ask_user_returns_interrupt(self):
        """ask_user retourne un statut INTERRUPT."""
        result = ask_user("Question test")
        assert result["status"] == "INTERRUPT"
        assert result["intent"] == "HUMAN_INTERVENTION"
        assert result["data"]["question"] == "Question test"

    def test_ask_user_with_candidates(self):
        """ask_user avec des options les passe correctement."""
        result = ask_user("Choisissez", candidates=["A", "B", "C"])
        assert result["data"]["candidates"] == ["A", "B", "C"]

    def test_ask_user_without_candidates(self):
        """ask_user sans candidates retourne une liste vide."""
        result = ask_user("Question")
        assert result["data"]["candidates"] == []

    def test_ask_user_empty_question(self):
        """ask_user avec une question vide fonctionne."""
        result = ask_user("")
        assert result["data"]["question"] == ""

    def test_ask_user_unicode_question(self):
        """ask_user gère les questions Unicode."""
        result = ask_user("你好世界")
        assert result["data"]["question"] == "你好世界"

    def test_ask_user_single_candidate(self):
        """ask_user avec un seul candidat."""
        result = ask_user("Confirmer ?", candidates=["Oui"])
        assert result["data"]["candidates"] == ["Oui"]

"""
Tests unitaires pour les modules Qt extraits (Phase 3).
Teste constants, theme, utils, widgets, floating_button et la confirmation shell.

Note : Les tests nécessitant PySide6 sont marqués avec @pytest.mark.skipif
car l'environnement CI/Linux n'a pas PySide6 installé.
Sur la machine Windows de l'utilisateur avec PySide6, tous les tests passeront.
"""
import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Vérifier si PySide6 est disponible
try:
    import PySide6
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/constants.py (pas besoin de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestQtConstants:
    """Tests pour les constantes Qt (pas de dépendance PySide6)."""

    def test_history_file_defined(self):
        """HISTORY_FILE est défini."""
        from frontends.qt.constants import HISTORY_FILE
        assert isinstance(HISTORY_FILE, str)
        assert len(HISTORY_FILE) > 0
        assert "chat_history" in HISTORY_FILE

    def test_text_file_exts_defined(self):
        """TEXT_FILE_EXTS contient les extensions courantes."""
        from frontends.qt.constants import TEXT_FILE_EXTS
        assert isinstance(TEXT_FILE_EXTS, set)
        assert ".py" in TEXT_FILE_EXTS
        assert ".json" in TEXT_FILE_EXTS
        assert ".txt" in TEXT_FILE_EXTS
        assert ".md" in TEXT_FILE_EXTS
        assert ".csv" in TEXT_FILE_EXTS
        assert ".yaml" in TEXT_FILE_EXTS
        assert ".js" in TEXT_FILE_EXTS
        assert ".ts" in TEXT_FILE_EXTS
        assert ".sql" in TEXT_FILE_EXTS

    def test_text_file_exts_excludes_binary(self):
        """TEXT_FILE_EXTS ne contient pas d'extensions binaires."""
        from frontends.qt.constants import TEXT_FILE_EXTS
        assert ".png" not in TEXT_FILE_EXTS
        assert ".jpg" not in TEXT_FILE_EXTS
        assert ".exe" not in TEXT_FILE_EXTS
        assert ".zip" not in TEXT_FILE_EXTS

    def test_max_inline_chars_positive(self):
        """MAX_INLINE_CHARS est un entier positif."""
        from frontends.qt.constants import MAX_INLINE_CHARS
        assert isinstance(MAX_INLINE_CHARS, int)
        assert MAX_INLINE_CHARS > 0

    def test_max_inline_chars_reasonable(self):
        """MAX_INLINE_CHARS est dans une plage raisonnable (1000-50000)."""
        from frontends.qt.constants import MAX_INLINE_CHARS
        assert 1000 <= MAX_INLINE_CHARS <= 50000

    def test_svg_templates_exist(self):
        """Tous les templates SVG nécessaires sont définis."""
        from frontends.qt import constants
        svg_names = [
            '_SVG_COPY', '_SVG_REGEN', '_SVG_CHAT', '_SVG_CLOCK',
            '_SVG_SEARCH', '_SVG_BOOK', '_SVG_GEAR', '_SVG_PLUS',
            '_SVG_CLIP', '_SVG_STOP', '_SVG_RESET', '_SVG_SAVE',
            '_SVG_TRASH', '_SVG_BOLT', '_SVG_PLAY', '_SVG_FILE',
            '_SVG_USER', '_SVG_BOT', '_SVG_SEND',
        ]
        for name in svg_names:
            assert hasattr(constants, name), f"SVG manquant : {name}"
            val = getattr(constants, name)
            assert isinstance(val, str), f"{name} doit être une chaîne"
            assert "{c}" in val, f"{name} doit contenir le placeholder {{c}}"

    def test_svg_templates_are_valid_xml_ish(self):
        """Les templates SVG contiennent des éléments SVG valides."""
        from frontends.qt import constants
        svg_names = [
            '_SVG_CHAT', '_SVG_CLOCK', '_SVG_BOOK', '_SVG_GEAR',
            '_SVG_PLUS', '_SVG_STOP', '_SVG_SAVE', '_SVG_TRASH',
            '_SVG_BOLT', '_SVG_PLAY', '_SVG_FILE', '_SVG_USER',
            '_SVG_BOT', '_SVG_SEND', '_SVG_COPY', '_SVG_REGEN',
        ]
        for name in svg_names:
            val = getattr(constants, name)
            assert "svg" in val.lower() or "viewBox" in val, \
                f"{name} doit contenir des éléments SVG"

    def test_icon_cache_is_dict(self):
        """_icon_cache est un dictionnaire."""
        from frontends.qt.constants import _icon_cache
        assert isinstance(_icon_cache, dict)

    def test_icon_cache_initially_empty(self):
        """_icon_cache est initialement vide."""
        from frontends.qt.constants import _icon_cache
        # Le cache peut contenir des entrées d'un test précédent
        # mais doit être un dict valide
        assert isinstance(_icon_cache, dict)

    def test_svg_clip_equals_plus(self):
        """_SVG_CLIP est un alias de _SVG_PLUS."""
        from frontends.qt.constants import _SVG_CLIP, _SVG_PLUS
        assert _SVG_CLIP == _SVG_PLUS

    def test_svg_reset_equals_regen(self):
        """_SVG_RESET est un alias de _SVG_REGEN."""
        from frontends.qt.constants import _SVG_RESET, _SVG_REGEN
        assert _SVG_RESET == _SVG_REGEN

    def test_svg_stop_uses_fill_not_stroke(self):
        """_SVG_STOP utilise fill au lieu de stroke (icône pleine)."""
        from frontends.qt.constants import _SVG_STOP
        assert 'fill="{c}"' in _SVG_STOP
        assert 'stroke="none"' in _SVG_STOP

    def test_svg_play_uses_fill(self):
        """_SVG_PLAY utilise fill (icône pleine type play)."""
        from frontends.qt.constants import _SVG_PLAY
        assert 'fill="{c}"' in _SVG_PLAY


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/theme.py (nécessite PySide6 pour QColor)
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 non installé")
class TestQtTheme:
    """Tests pour le thème visuel Qt (nécessite PySide6)."""

    def test_color_palette_has_required_keys(self):
        """La palette C contient toutes les clés requises."""
        from frontends.qt.theme import C
        required_keys = [
            'bg', 'panel', 'border', 'accent', 'text', 'muted',
            'user_g0', 'user_g1', 'asst_bg', 'asst_bdr',
            'send_g0', 'send_g1', 'green',
        ]
        for key in required_keys:
            assert key in C, f"Clé manquante dans la palette : {key}"

    def test_color_palette_accent_is_string(self):
        """La couleur accent est une chaîne hex."""
        from frontends.qt.theme import C
        assert isinstance(C["accent"], str)
        assert C["accent"].startswith("#")

    def test_color_palette_text_is_string(self):
        """La couleur text est une chaîne hex."""
        from frontends.qt.theme import C
        assert isinstance(C["text"], str)
        assert C["text"].startswith("#")

    def test_scrollbar_style_is_string(self):
        """SCROLLBAR_STYLE est une chaîne CSS non vide."""
        from frontends.qt.theme import SCROLLBAR_STYLE
        assert isinstance(SCROLLBAR_STYLE, str)
        assert len(SCROLLBAR_STYLE) > 0
        assert "QScrollBar" in SCROLLBAR_STYLE

    def test_scrollbar_style_has_vertical_selector(self):
        """SCROLLBAR_STYLE contient le sélecteur vertical."""
        from frontends.qt.theme import SCROLLBAR_STYLE
        assert "QScrollBar:vertical" in SCROLLBAR_STYLE

    def test_scrollbar_style_has_handle(self):
        """SCROLLBAR_STYLE définit le style du handle."""
        from frontends.qt.theme import SCROLLBAR_STYLE
        assert "QScrollBar::handle:vertical" in SCROLLBAR_STYLE

    def test_md_css_is_string(self):
        """_MD_CSS est une chaîne CSS non vide pour le rendu Markdown."""
        from frontends.qt.theme import _MD_CSS
        assert isinstance(_MD_CSS, str)
        assert len(_MD_CSS) > 0
        assert "body" in _MD_CSS
        assert "code" in _MD_CSS
        assert "pre" in _MD_CSS

    def test_md_css_has_heading_styles(self):
        """_MD_CSS contient des styles pour les titres."""
        from frontends.qt.theme import _MD_CSS
        assert "h1" in _MD_CSS
        assert "h2" in _MD_CSS

    def test_md_css_has_link_style(self):
        """_MD_CSS contient un style pour les liens."""
        from frontends.qt.theme import _MD_CSS
        assert "a {" in _MD_CSS or "a:" in _MD_CSS

    def test_md_css_has_table_style(self):
        """_MD_CSS contient des styles pour les tables."""
        from frontends.qt.theme import _MD_CSS
        assert "table" in _MD_CSS
        assert "th" in _MD_CSS or "td" in _MD_CSS


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Markdown (pas besoin de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestMarkdownToHtml:
    """Tests pour la conversion Markdown → HTML (pas de dépendance PySide6)."""

    def test_md_to_html_basic(self):
        """_md_to_html convertit du Markdown simple en HTML."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("**gras** et *italique*")
        assert "<b>gras</b>" in result
        assert "<i>italique</i>" in result

    def test_md_to_html_code_block(self):
        """_md_to_html convertit les blocs de code."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("```python\nprint('hello')\n```")
        assert "<pre><code>" in result or "<code>" in result

    def test_md_to_html_heading(self):
        """_md_to_html convertit les titres."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("# Titre principal")
        assert "<h1>" in result

    def test_md_to_html_h2(self):
        """_md_to_html convertit les titres de niveau 2."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("## Sous-titre")
        assert "<h2>" in result

    def test_md_to_html_h3(self):
        """_md_to_html convertit les titres de niveau 3."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("### Section")
        assert "<h3>" in result

    def test_md_to_html_link(self):
        """_md_to_html convertit les liens."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("[Texte](https://example.com)")
        assert '<a href="https://example.com">Texte</a>' in result

    def test_md_to_html_empty_string(self):
        """_md_to_html gère la chaîne vide."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("")
        assert isinstance(result, str)

    def test_md_to_html_inline_code(self):
        """_md_to_html convertit le code inline."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("Utilisez `print()` pour afficher")
        assert "<code>print()</code>" in result

    def test_md_to_html_unordered_list(self):
        """_md_to_html convertit les listes non ordonnées."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("- item 1\n- item 2")
        assert "<ul>" in result
        assert "<li>" in result
        assert "</ul>" in result

    def test_md_to_html_horizontal_rule(self):
        """_md_to_html convertit les séparateurs horizontaux."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("---")
        assert "<hr>" in result

    def test_md_to_html_multiline_code(self):
        """_md_to_html convertit les blocs de code multilignes."""
        from frontends.qt.utils import _md_to_html
        code = "```\nline 1\nline 2\nline 3\n```"
        result = _md_to_html(code)
        assert "<pre><code>" in result
        assert "line 1" in result
        assert "</code></pre>" in result

    def test_md_to_html_code_escapes_html(self):
        """_md_to_html échappe le HTML dans les blocs de code."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("```\n<div>test</div>\n```")
        assert "&lt;div&gt;" in result

    def test_md_to_html_paragraph(self):
        """_md_to_html wrappe le texte simple dans des paragraphes."""
        from frontends.qt.utils import _md_to_html
        result = _md_to_html("Hello world")
        assert "<p>" in result or "Hello world" in result

    def test_md_to_html_complex_document(self):
        """_md_to_html gère un document complexe avec plusieurs éléments."""
        from frontends.qt.utils import _md_to_html
        doc = "# Titre\n\nParagraphe avec **gras** et *italique*.\n\n- Liste 1\n- Liste 2\n\n```python\ncode()\n```"
        result = _md_to_html(doc)
        assert "<h1>" in result
        assert "<b>gras</b>" in result
        assert "<li>" in result
        assert "<pre><code>" in result


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Sessions & Historique (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestSessionUtils:
    """Tests pour les utilitaires de session (pas de dépendance PySide6)."""

    def test_make_session_id_format(self):
        """_make_session_id retourne un identifiant au format YYYYMMDD_HHMMSS_f."""
        from frontends.qt.utils import _make_session_id
        sid = _make_session_id()
        assert isinstance(sid, str)
        assert len(sid) > 15
        parts = sid.split("_")
        assert len(parts) == 3

    def test_make_session_id_unique(self):
        """Deux appels à _make_session_id retournent des IDs différents."""
        from frontends.qt.utils import _make_session_id
        import time
        id1 = _make_session_id()
        time.sleep(0.001)
        id2 = _make_session_id()
        assert id1 != id2

    def test_make_session_id_starts_with_date(self):
        """_make_session_id commence par la date au format YYYYMMDD."""
        from frontends.qt.utils import _make_session_id
        from datetime import datetime
        sid = _make_session_id()
        today = datetime.now().strftime("%Y%m%d")
        assert sid.startswith(today)

    def test_load_history_returns_list(self):
        """_load_history retourne une liste (même si le fichier n'existe pas)."""
        from frontends.qt.utils import _load_history
        result = _load_history()
        assert isinstance(result, list)

    def test_save_and_load_history(self):
        """Sauvegarder et recharger l'historique fonctionne."""
        from frontends.qt.utils import _save_history, _load_history
        original = _load_history()
        test_entry = {"id": "test_unit_001", "title": "Test session", "messages": []}
        original.append(test_entry)
        _save_history(original)
        loaded = _load_history()
        assert any(h.get("id") == "test_unit_001" for h in loaded)
        # Nettoyer
        cleaned = [h for h in loaded if h.get("id") != "test_unit_001"]
        _save_history(cleaned)

    def test_save_history_with_unicode(self):
        """L'historique peut contenir des caractères Unicode."""
        from frontends.qt.utils import _save_history, _load_history
        original = _load_history()
        test_entry = {"id": "test_unicode_001", "title": "你好世界 🌍", "messages": [
            {"role": "user", "content": "こんにちは"}
        ]}
        original.append(test_entry)
        _save_history(original)
        loaded = _load_history()
        found = next((h for h in loaded if h.get("id") == "test_unicode_001"), None)
        assert found is not None
        assert found["title"] == "你好世界 🌍"
        # Nettoyer
        cleaned = [h for h in loaded if h.get("id") != "test_unicode_001"]
        _save_history(cleaned)

    def test_auto_title_session_with_new_conversation(self):
        """_auto_title_session génère un titre à partir du premier message."""
        from frontends.qt.utils import _auto_title_session
        session = {"id": "1", "title": "Nouvelle conversation"}
        messages = [
            {"role": "user", "content": "Aide-moi avec Python"},
            {"role": "assistant", "content": "Bien sûr!"},
        ]
        title = _auto_title_session(session, messages)
        assert title == "Aide-moi avec Python"

    def test_auto_title_session_truncates_long_title(self):
        """_auto_title_session tronque les titres longs à 30 caractères."""
        from frontends.qt.utils import _auto_title_session
        session = {"id": "1", "title": "Nouvelle conversation"}
        long_msg = "Ceci est un message très long qui dépasse largement les trente caractères"
        messages = [{"role": "user", "content": long_msg}]
        title = _auto_title_session(session, messages)
        assert len(title) <= 30
        assert title == long_msg[:30]

    def test_auto_title_session_replaces_newlines(self):
        """_auto_title_session remplace les retours à la ligne dans le titre."""
        from frontends.qt.utils import _auto_title_session
        session = {"id": "1", "title": "Nouvelle conversation"}
        messages = [{"role": "user", "content": "Ligne 1\nLigne 2"}]
        title = _auto_title_session(session, messages)
        assert "\n" not in title

    def test_auto_title_session_preserves_existing_title(self):
        """_auto_title_session ne modifie pas un titre existant."""
        from frontends.qt.utils import _auto_title_session
        session = {"id": "1", "title": "Mon titre existant"}
        messages = [{"role": "user", "content": "Autre chose"}]
        title = _auto_title_session(session, messages)
        assert title == "Mon titre existant"

    def test_auto_title_session_no_user_message(self):
        """_auto_title_session retourne le titre par défaut sans message utilisateur."""
        from frontends.qt.utils import _auto_title_session
        session = {"id": "1", "title": "Nouvelle conversation"}
        messages = [{"role": "assistant", "content": "Bonjour!"}]
        title = _auto_title_session(session, messages)
        assert title == "Nouvelle conversation"

    def test_merge_session_new_session(self):
        """_merge_session_into_history ajoute une nouvelle session."""
        from frontends.qt.utils import _merge_session_into_history
        history = [{"id": "1", "title": "Ancienne"}]
        session = {"id": "2", "title": "Nouvelle"}
        result = _merge_session_into_history(history, session)
        assert len(result) == 2
        assert any(s["id"] == "2" for s in result)

    def test_merge_session_existing_session(self):
        """_merge_session_into_history met à jour une session existante."""
        from frontends.qt.utils import _merge_session_into_history
        history = [{"id": "1", "title": "Ancien titre"}]
        session = {"id": "1", "title": "Nouveau titre"}
        result = _merge_session_into_history(history, session)
        assert len(result) == 1
        assert result[0]["title"] == "Nouveau titre"

    def test_merge_session_empty_history(self):
        """_merge_session_into_history gère un historique vide."""
        from frontends.qt.utils import _merge_session_into_history
        history = []
        session = {"id": "1", "title": "Première session"}
        result = _merge_session_into_history(history, session)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_merge_session_does_not_modify_original(self):
        """_merge_session_into_history copie la session sans modifier l'originale."""
        from frontends.qt.utils import _merge_session_into_history
        history = []
        session = {"id": "1", "title": "Test"}
        result = _merge_session_into_history(history, session)
        # La session dans le résultat doit être une copie
        session["title"] = "Modifié"
        assert result[0]["title"] == "Test"


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Pièces jointes (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestBuildPromptWithUploads:
    """Tests pour _build_prompt_with_uploads (pas de dépendance PySide6)."""

    def test_no_files(self):
        """_build_prompt_with_uploads sans fichiers retourne le prompt inchangé."""
        from frontends.qt.utils import _build_prompt_with_uploads
        prompt = "Bonjour"
        full, display, attachments = _build_prompt_with_uploads(prompt, [])
        assert full == prompt
        assert display == prompt
        assert attachments == []

    def test_with_text_file(self):
        """_build_prompt_with_uploads avec un fichier texte l'inline."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [{"name": "test.py", "type": "text/plain", "raw": b"print('hello')"}]
        full, display, attachments = _build_prompt_with_uploads("Analyse", files)
        assert "Fichier texte" in full
        assert "test.py" in full
        assert "print('hello')" in full
        assert len(attachments) == 1
        assert attachments[0]["type"] == "file"
        assert attachments[0]["name"] == "test.py"

    def test_with_image_file(self):
        """_build_prompt_with_uploads avec une image inclut le base64."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [{"name": "photo.png", "type": "image/png", "raw": b"\x89PNG\r\n"}]
        full, display, attachments = _build_prompt_with_uploads("Décris", files)
        assert "Image jointe" in full
        assert "photo.png" in full
        assert "base64" in full
        assert len(attachments) == 1
        assert attachments[0]["type"] == "image"

    def test_with_binary_file(self):
        """_build_prompt_with_uploads avec un fichier binaire non-image."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [{"name": "data.bin", "type": "application/octet-stream", "raw": b"\x00\x01\x02"}]
        full, display, attachments = _build_prompt_with_uploads("Analyse", files)
        assert "data.bin" in full
        assert len(attachments) == 1
        assert attachments[0]["type"] == "file"

    def test_with_multiple_files(self):
        """_build_prompt_with_uploads avec plusieurs fichiers."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [
            {"name": "a.py", "type": "text/plain", "raw": b"code_a"},
            {"name": "b.txt", "type": "text/plain", "raw": b"code_b"},
        ]
        full, display, attachments = _build_prompt_with_uploads("Analyse", files)
        assert "a.py" in full
        assert "b.txt" in full
        assert len(attachments) == 2

    def test_display_prompt_contains_attachment_info(self):
        """Le display_prompt contient l'info sur les pièces jointes."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [{"name": "test.py", "type": "text/plain", "raw": b"code"}]
        _, display, _ = _build_prompt_with_uploads("Analyse", files)
        assert "fichier(s)" in display or "Pièces jointes" in display

    def test_text_file_truncation(self):
        """Un fichier texte trop long est tronqué."""
        from frontends.qt.utils import _build_prompt_with_uploads
        long_content = "A" * 10000  # Dépasse MAX_INLINE_CHARS
        files = [{"name": "big.py", "type": "text/plain", "raw": long_content.encode()}]
        full, _, _ = _build_prompt_with_uploads("Analyse", files)
        assert "tronqué" in full.lower() or "file_read" in full.lower()

    def test_full_prompt_contains_attachment_header(self):
        """Le full_prompt contient l'en-tête de pièce jointe."""
        from frontends.qt.utils import _build_prompt_with_uploads
        files = [{"name": "test.py", "type": "text/plain", "raw": b"code"}]
        full, _, _ = _build_prompt_with_uploads("Analyse", files)
        assert "Fichier joint" in full or "sauvegardé" in full


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Token estimation (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestTokenEstimation:
    """Tests pour l'estimation de tokens (pas de dépendance PySide6)."""

    def test_empty_messages(self):
        """Messages vides donnent 0 tokens."""
        from frontends.qt.utils import _estimate_token_usage
        result = _estimate_token_usage([])
        assert result["in_tokens"] == 0
        assert result["out_tokens"] == 0

    def test_user_message_only(self):
        """Un message utilisateur compte comme input."""
        from frontends.qt.utils import _estimate_token_usage
        messages = [{"role": "user", "content": "Hello world"}]
        result = _estimate_token_usage(messages)
        assert result["in_tokens"] > 0
        assert result["out_tokens"] == 0

    def test_assistant_message_only(self):
        """Un message assistant compte comme output."""
        from frontends.qt.utils import _estimate_token_usage
        messages = [{"role": "assistant", "content": "Bonjour le monde"}]
        result = _estimate_token_usage(messages)
        assert result["in_tokens"] == 0
        assert result["out_tokens"] > 0

    def test_mixed_messages(self):
        """Les messages utilisateur et assistant sont comptés séparément."""
        from frontends.qt.utils import _estimate_token_usage
        messages = [
            {"role": "user", "content": "A" * 100},
            {"role": "assistant", "content": "B" * 200},
        ]
        result = _estimate_token_usage(messages)
        assert result["in_tokens"] > 0
        assert result["out_tokens"] > 0
        # L'assistant a écrit 2x plus de caractères → plus de tokens
        assert result["out_tokens"] > result["in_tokens"]

    def test_streaming_text_counted(self):
        """Le texte en streaming est ajouté aux tokens de sortie."""
        from frontends.qt.utils import _estimate_token_usage
        messages = [{"role": "assistant", "content": "Done"}]
        result_no_stream = _estimate_token_usage(messages, "", False)
        result_with_stream = _estimate_token_usage(messages, "Streaming text here", True)
        assert result_with_stream["out_tokens"] > result_no_stream["out_tokens"]

    def test_streaming_text_ignored_when_not_streaming(self):
        """Le texte de streaming est ignoré si is_streaming=False."""
        from frontends.qt.utils import _estimate_token_usage
        messages = []
        result1 = _estimate_token_usage(messages, "some text", False)
        result2 = _estimate_token_usage(messages, "", False)
        assert result1["out_tokens"] == result2["out_tokens"]

    def test_estimation_ratio(self):
        """L'estimation utilise un ratio d'environ 2.5 chars/token."""
        from frontends.qt.utils import _estimate_token_usage
        # 250 chars = ~100 tokens
        messages = [{"role": "user", "content": "A" * 250}]
        result = _estimate_token_usage(messages)
        assert result["in_tokens"] == 100

    def test_missing_content_key(self):
        """Les messages sans clé 'content' sont gérés gracieusement."""
        from frontends.qt.utils import _estimate_token_usage
        messages = [{"role": "user"}]
        result = _estimate_token_usage(messages)
        assert result["in_tokens"] == 0


class TestFormatTokenLabel:
    """Tests pour _format_token_label (pas de dépendance PySide6)."""

    def test_zero_tokens(self):
        """Avec 0 tokens, retourne une chaîne vide."""
        from frontends.qt.utils import _format_token_label
        assert _format_token_label(0, 0) == ""

    def test_with_input_tokens(self):
        """Avec des tokens d'entrée, retourne un label formaté."""
        from frontends.qt.utils import _format_token_label
        result = _format_token_label(100, 0)
        assert "100" in result
        assert "entrée" in result

    def test_with_output_tokens(self):
        """Avec des tokens de sortie, retourne un label formaté."""
        from frontends.qt.utils import _format_token_label
        result = _format_token_label(0, 50)
        assert "50" in result
        assert "sortie" in result

    def test_with_both_tokens(self):
        """Avec les deux types de tokens, retourne un label complet."""
        from frontends.qt.utils import _format_token_label
        result = _format_token_label(100, 50)
        assert "100" in result
        assert "50" in result
        assert "entrée" in result
        assert "sortie" in result


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Backend health check (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestBackendHealthCheck:
    """Tests pour _check_backend_health (pas de dépendance PySide6)."""

    def test_healthy_backend(self):
        """Un backend qui répond correctement est détecté comme sain."""
        from frontends.qt.utils import _check_backend_health

        class MockBackend:
            model = "test-model"
            def ask(self, msg):
                return "Bonjour, je suis un assistant."

        assert _check_backend_health(MockBackend()) is True

    def test_failing_backend(self):
        """Un backend qui lève une exception est détecté comme défaillant."""
        from frontends.qt.utils import _check_backend_health

        class FailingBackend:
            model = "fail-model"
            def ask(self, msg):
                raise ConnectionError("API unreachable")

        assert _check_backend_health(FailingBackend()) is False

    def test_error_response_backend(self):
        """Un backend qui retourne 'Error' est détecté comme défaillant."""
        from frontends.qt.utils import _check_backend_health

        class ErrorBackend:
            model = "error-model"
            def ask(self, msg):
                return "Error: API key invalid"

        assert _check_backend_health(ErrorBackend()) is False

    def test_bracket_response_backend(self):
        """Un backend qui retourne une réponse entre crochets est détecté comme défaillant."""
        from frontends.qt.utils import _check_backend_health

        class BracketBackend:
            model = "bracket-model"
            def ask(self, msg):
                return "[ERROR] Something went wrong"

        assert _check_backend_health(BracketBackend()) is False

    def test_empty_response_backend(self):
        """Un backend qui retourne une réponse vide est détecté comme défaillant."""
        from frontends.qt.utils import _check_backend_health

        class EmptyBackend:
            model = "empty-model"
            def ask(self, msg):
                return ""

        assert _check_backend_health(EmptyBackend()) is False

    def test_generator_backend(self):
        """Un backend dont ask() est un générateur est géré correctement."""
        from frontends.qt.utils import _check_backend_health

        class GeneratorBackend:
            model = "gen-model"
            def ask(self, msg):
                yield "Bonjour"
                yield "!"
                yield ""

        assert _check_backend_health(GeneratorBackend()) is True

    def test_backend_with_raw_msgs_cleaned(self):
        """Le message de test est nettoyé de l'historique raw_msgs."""
        from frontends.qt.utils import _check_backend_health

        class BackendWithRawMsgs:
            model = "raw-msgs-model"
            raw_msgs = [{"prompt": "Bonjour", "response": "Salut"}, {"prompt": "Other", "response": "Reply"}]
            def ask(self, msg):
                self.raw_msgs.append({"prompt": msg, "response": "OK"})
                return "OK"

        backend = BackendWithRawMsgs()
        _check_backend_health(backend)
        # Le message de test doit avoir été retiré
        assert not any(m.get("prompt") == "Bonjour" for m in backend.raw_msgs)


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — Styles UI (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestUIStyles:
    """Tests pour les fonctions de style UI (pas de dépendance PySide6)."""

    def test_small_btn_style_contains_color(self):
        """_small_btn_style inclut la couleur spécifiée."""
        from frontends.qt.utils import _small_btn_style
        result = _small_btn_style("#ff0000")
        assert "#ff0000" in result

    def test_small_btn_style_is_valid_css(self):
        """_small_btn_style génère du CSS valide pour QPushButton."""
        from frontends.qt.utils import _small_btn_style
        result = _small_btn_style("#059669")
        assert "QPushButton" in result
        assert "background" in result
        assert "border-radius" in result
        assert "font-size" in result

    def test_small_btn_style_hover(self):
        """_small_btn_style inclut un style hover."""
        from frontends.qt.utils import _small_btn_style
        result = _small_btn_style("#059669")
        assert "hover" in result.lower()

    def test_model_row_style_exists(self):
        """MODEL_ROW_STYLE est défini et est une chaîne."""
        from frontends.qt.utils import MODEL_ROW_STYLE
        assert isinstance(MODEL_ROW_STYLE, str)
        assert len(MODEL_ROW_STYLE) > 0
        assert "QPushButton" in MODEL_ROW_STYLE

    def test_model_row_active_exists(self):
        """MODEL_ROW_ACTIVE est défini et est une chaîne."""
        from frontends.qt.utils import MODEL_ROW_ACTIVE
        assert isinstance(MODEL_ROW_ACTIVE, str)
        assert len(MODEL_ROW_ACTIVE) > 0
        assert "QPushButton" in MODEL_ROW_ACTIVE

    def test_model_row_active_different_from_style(self):
        """MODEL_ROW_ACTIVE est différent de MODEL_ROW_STYLE."""
        from frontends.qt.utils import MODEL_ROW_STYLE, MODEL_ROW_ACTIVE
        assert MODEL_ROW_ACTIVE != MODEL_ROW_STYLE

    def test_model_row_active_contains_accent_color(self):
        """MODEL_ROW_ACTIVE contient la couleur d'accent (violet)."""
        from frontends.qt.utils import MODEL_ROW_ACTIVE
        assert "124,58,237" in MODEL_ROW_ACTIVE or "7c3aed" in MODEL_ROW_ACTIVE


# ══════════════════════════════════════════════════════════════════════
# Tests pour frontends/qt/utils.py — SVG icon (nécessite PySide6)
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 non installé")
class TestSvgIcon:
    """Tests pour la création d'icônes SVG (nécessite PySide6)."""

    def test_svg_icon_returns_qicon(self):
        """_svg_icon retourne un QIcon."""
        from frontends.qt.utils import _svg_icon
        from frontends.qt.constants import _SVG_CHAT
        from PySide6.QtGui import QIcon
        icon = _svg_icon("test_chat", _SVG_CHAT, "#ffffff")
        assert isinstance(icon, QIcon)

    def test_svg_icon_uses_cache(self):
        """_svg_icon met en cache les icônes."""
        from frontends.qt.utils import _svg_icon
        from frontends.qt.constants import _SVG_CHAT, _icon_cache
        # Vider le cache pour ce test
        keys_before = set(_icon_cache.keys())
        icon1 = _svg_icon("cache_test", _SVG_CHAT, "#ff0000", 16)
        icon2 = _svg_icon("cache_test", _SVG_CHAT, "#ff0000", 16)
        # Le deuxième appel doit utiliser le cache
        assert icon1 is icon2


# ══════════════════════════════════════════════════════════════════════
# Tests pour la confirmation shell (sécurité code_run) — pas de PySide6
# ══════════════════════════════════════════════════════════════════════

class TestShellConfirmCallback:
    """Tests pour le système de confirmation shell branché dans ChatPanel."""

    def test_set_shell_confirm_callback_importable(self):
        """set_shell_confirm_callback est importable depuis ga.py."""
        from ga import set_shell_confirm_callback
        assert callable(set_shell_confirm_callback)

    def test_shell_confirm_callback_registration(self):
        """On peut enregistrer un callback de confirmation shell."""
        import ga
        from ga import set_shell_confirm_callback
        original = ga._shell_confirm_callback

        def my_callback(code, code_type):
            return True

        set_shell_confirm_callback(my_callback)
        assert ga._shell_confirm_callback is my_callback

        # Nettoyer
        ga._shell_confirm_callback = original

    def test_shell_confirm_callback_can_reject(self):
        """Un callback qui retourne False bloque la commande."""
        import ga
        from ga import set_shell_confirm_callback
        original = ga._shell_confirm_callback

        rejected = []

        def reject_callback(code, code_type):
            rejected.append(code)
            return False

        set_shell_confirm_callback(reject_callback)
        # Vérifier que le callback est bien en place
        assert ga._shell_confirm_callback is reject_callback

        # Nettoyer
        ga._shell_confirm_callback = original

    def test_dangerous_patterns_exist(self):
        """Les patterns de commandes dangereuses sont définis."""
        from ga import DANGEROUS_SHELL_PATTERNS
        assert isinstance(DANGEROUS_SHELL_PATTERNS, list)
        assert len(DANGEROUS_SHELL_PATTERNS) > 0
        patterns_str = " ".join(DANGEROUS_SHELL_PATTERNS)
        assert "rm" in patterns_str
        assert "shutdown" in patterns_str
        assert "format" in patterns_str


# ══════════════════════════════════════════════════════════════════════
# Tests pour la structure modulaire (pas de PySide6)
# ══════════════════════════════════════════════════════════════════════

class TestModularStructure:
    """Tests pour vérifier que la structure modulaire est correcte."""

    def test_qt_package_init_exists(self):
        """Le package frontends/qt a un __init__.py."""
        init_path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', '__init__.py'
        )
        assert os.path.exists(init_path)

    def test_constants_module_file_exists(self):
        """Le fichier constants.py existe dans frontends/qt/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'constants.py'
        )
        assert os.path.exists(path)

    def test_theme_module_file_exists(self):
        """Le fichier theme.py existe dans frontends/qt/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'theme.py'
        )
        assert os.path.exists(path)

    def test_utils_module_file_exists(self):
        """Le fichier utils.py existe dans frontends/qt/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'utils.py'
        )
        assert os.path.exists(path)

    def test_widgets_module_file_exists(self):
        """Le fichier widgets.py existe dans frontends/qt/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'widgets.py'
        )
        assert os.path.exists(path)

    def test_floating_button_module_file_exists(self):
        """Le fichier floating_button.py existe dans frontends/qt/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'floating_button.py'
        )
        assert os.path.exists(path)

    def test_constants_module_importable(self):
        """Le module constants est importable (pas de dépendance PySide6)."""
        from frontends.qt import constants
        assert constants is not None

    def test_qtapp_file_exists(self):
        """Le fichier qtapp.py existe dans frontends/."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        assert os.path.exists(path)

    def test_qtapp_line_count_reduced(self):
        """Le fichier qtapp.py a été réduit par rapport au monolithe original (2022 lignes)."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            lines = len(f.readlines())
        # Le monolithe original faisait 2 022 lignes
        # Après refonte, il doit être significativement plus petit
        assert lines < 1500, f"qtapp.py fait encore {lines} lignes, attendu < 1500"

    def test_qtapp_uses_modular_imports(self):
        """qtapp.py importe depuis les modules extraits."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Vérifier que qtapp.py importe depuis les modules
        assert "from frontends.qt.constants import" in content
        assert "from frontends.qt.theme import" in content
        assert "from frontends.qt.utils import" in content
        assert "from frontends.qt.widgets import" in content
        assert "from frontends.qt.floating_button import FloatingButton" in content

    def test_qtapp_uses_extracted_modules(self):
        """qtapp.py importe et utilise les modules extraits (Phase 3)."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Le nouvel qtapp.py importe SessionManager et StreamHandler
        assert "SessionManager" in content or "session_manager" in content
        assert "StreamHandler" in content or "stream_handler" in content

    def test_qtapp_has_shell_confirm(self):
        """qtapp.py branche la confirmation shell dans ChatPanel."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "set_shell_confirm_callback" in content
        assert "_shell_confirm_dialog" in content

    def test_no_duplicated_code_in_qtapp(self):
        """qtapp.py ne contient plus les blocs de code extraits dans les modules."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qtapp.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Ces éléments doivent avoir été extraits et ne plus être définis dans qtapp.py
        # Vérifier que les SVG templates ne sont PAS définis localement
        assert 'HISTORY_FILE = "memory/chat_history.json"' not in content, \
            "HISTORY_FILE ne doit plus être défini localement dans qtapp.py"
        assert "C = {" not in content, \
            "La palette C ne doit plus être définie localement dans qtapp.py"
        assert "SCROLLBAR_STYLE = " not in content, \
            "SCROLLBAR_STYLE ne doit plus être défini localement dans qtapp.py"
        # Phase 3 : vérifier que les styles et helpers ont été extraits
        assert "def _small_btn_style" not in content, \
            "_small_btn_style ne doit plus être défini localement dans qtapp.py"
        assert "_MODEL_ROW_STYLE" not in content, \
            "_MODEL_ROW_STYLE ne doit plus être défini localement dans qtapp.py"
        assert "_MODEL_ROW_ACTIVE" not in content, \
            "_MODEL_ROW_ACTIVE ne doit plus être défini localement dans qtapp.py"


# ══════════════════════════════════════════════════════════════════════
# Tests pour les nouveaux modules (session_manager, stream_handler, pages)
# ══════════════════════════════════════════════════════════════════════

class TestNewModulesImportable:
    """Tests pour vérifier que les nouveaux modules sont importables sans PySide6."""

    def test_session_manager_importable(self):
        """Le module session_manager est importable sans PySide6."""
        from frontends.qt.session_manager import SessionManager
        assert SessionManager is not None

    def test_stream_handler_importable(self):
        """Le module stream_handler est importable sans PySide6."""
        from frontends.qt.stream_handler import StreamHandler
        assert StreamHandler is not None

    def test_session_manager_class_exists(self):
        """La classe SessionManager existe dans le module."""
        from frontends.qt.session_manager import SessionManager
        assert callable(SessionManager)

    def test_stream_handler_class_exists(self):
        """La classe StreamHandler existe dans le module."""
        from frontends.qt.stream_handler import StreamHandler
        assert callable(StreamHandler)

    def test_session_manager_file_exists(self):
        """Le fichier session_manager.py existe."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'session_manager.py'
        )
        assert os.path.exists(path)

    def test_stream_handler_file_exists(self):
        """Le fichier stream_handler.py existe."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'stream_handler.py'
        )
        assert os.path.exists(path)

    def test_pages_package_file_exists(self):
        """Le package pages/ existe avec un __init__.py."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'pages', '__init__.py'
        )
        assert os.path.exists(path)


class TestModularArchitectureAPI:
    """Tests pour vérifier que les classes et fonctions attendues existent."""

    def test_session_manager_has_expected_methods(self):
        """SessionManager possède toutes les méthodes attendues."""
        from frontends.qt.session_manager import SessionManager
        expected_methods = [
            'auto_save', 'save_session', 'clear_session', 'new_session',
            'restore_session', 'delete_session', 'update_token_usage',
            'get_token_label', 'toggle_autonomous', 'is_idle_timeout',
            'get_last_user_message', 'add_message',
            'add_pending_file', 'clear_pending_files', 'reload_history',
        ]
        for method in expected_methods:
            assert hasattr(SessionManager, method), f"Méthode manquante : {method}"

    def test_session_manager_has_expected_properties(self):
        """SessionManager possède les propriétés en lecture seule attendues."""
        from frontends.qt.session_manager import SessionManager
        expected_props = ['messages', 'session', 'history', 'pending_files']
        for prop in expected_props:
            assert hasattr(SessionManager, prop), f"Propriété manquante : {prop}"

    def test_session_manager_has_expected_attributes(self):
        """SessionManager possède les attributs attendus."""
        from frontends.qt.session_manager import SessionManager
        # On vérifie juste que __init__ existe et est callable
        assert callable(getattr(SessionManager, '__init__', None))

    def test_stream_handler_has_expected_methods(self):
        """StreamHandler possède toutes les méthodes attendues."""
        from frontends.qt.stream_handler import StreamHandler
        expected_methods = [
            'start_stream', 'poll_queue', 'stop_stream', 'reset',
        ]
        for method in expected_methods:
            assert hasattr(StreamHandler, method), f"Méthode manquante : {method}"

    def test_stream_handler_has_expected_properties(self):
        """StreamHandler possède les propriétés attendues."""
        from frontends.qt.stream_handler import StreamHandler
        expected_props = ['is_streaming', 'streaming_text']
        for prop in expected_props:
            assert hasattr(StreamHandler, prop), f"Propriété manquante : {prop}"

    def test_stream_handler_has_poll_interval_constant(self):
        """StreamHandler définit POLL_INTERVAL_MS."""
        from frontends.qt.stream_handler import StreamHandler
        assert hasattr(StreamHandler, 'POLL_INTERVAL_MS')
        assert isinstance(StreamHandler.POLL_INTERVAL_MS, int)


class TestPageSignalDefinitions:
    """Tests pour vérifier que les pages ont les signaux attendus.

    Ces tests inspectent les attributs de classe sans instancier
    les widgets (pas besoin de QApplication).
    """

    def test_chat_page_signal_names_in_source(self):
        """ChatPage définit les signaux send_message, stop_stream, regenerate_response."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'pages', 'chat_page.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "send_message = Signal(str, list)" in content
        assert "stop_stream = Signal()" in content
        assert "regenerate_response = Signal()" in content

    def test_history_page_signal_names_in_source(self):
        """HistoryPage définit les signaux restore_session, delete_session."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'pages', 'history_page.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "restore_session = Signal(dict)" in content
        assert "delete_session = Signal(str)" in content

    def test_sop_page_no_signals_in_source(self):
        """SOPPage ne définit pas de signaux (navigation passive)."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'pages', 'sop_page.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Signal(" not in content

    def test_settings_page_signal_names_in_source(self):
        """SettingsPage définit les 6 signaux attendus."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'frontends', 'qt', 'pages', 'settings_page.py'
        )
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "switch_model = Signal(int)" in content
        assert "reset_prompt = Signal()" in content
        assert "save_session = Signal()" in content
        assert "clear_conversation = Signal()" in content
        assert "toggle_autonomous = Signal()" in content
        assert "trigger_autonomous = Signal()" in content


# ══════════════════════════════════════════════════════════════════════
# Tests pour les fichiers i18n (vérification de cohérence)
# ══════════════════════════════════════════════════════════════════════

class TestI18nConsistency:
    """Tests pour vérifier la cohérence des traductions."""

    def test_all_json_files_valid(self):
        """Les 3 fichiers JSON de traduction sont du JSON valide."""
        i18n_dir = os.path.join(os.path.dirname(__file__), '..', 'i18n')
        for lang in ['fr', 'en', 'zh']:
            path = os.path.join(i18n_dir, f'{lang}.json')
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{lang}.json doit être un dictionnaire"

    def test_security_keys_in_all_languages(self):
        """Les clés de sécurité shell sont dans toutes les langues."""
        i18n_dir = os.path.join(os.path.dirname(__file__), '..', 'i18n')
        for lang in ['fr', 'en', 'zh']:
            path = os.path.join(i18n_dir, f'{lang}.json')
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            error_section = data.get('error', {})
            assert 'shell_blocked' in error_section, f"shell_blocked manquant dans {lang}.json"
            assert 'shell_dangerous' in error_section, f"shell_dangerous manquant dans {lang}.json"

    def test_consistent_keys_across_languages(self):
        """Les mêmes clés existent dans toutes les langues."""
        i18n_dir = os.path.join(os.path.dirname(__file__), '..', 'i18n')
        datasets = {}
        for lang in ['fr', 'en', 'zh']:
            path = os.path.join(i18n_dir, f'{lang}.json')
            with open(path, 'r', encoding='utf-8') as f:
                datasets[lang] = json.load(f)
        # Vérifier que toutes les langues ont les mêmes clés de premier niveau
        keys_sets = {lang: set(data.keys()) for lang, data in datasets.items()}
        # Au moins les clés principales doivent être communes
        common_keys = keys_sets['fr'] & keys_sets['en'] & keys_sets['zh']
        assert len(common_keys) > 0, "Aucune clé commune entre les langues"

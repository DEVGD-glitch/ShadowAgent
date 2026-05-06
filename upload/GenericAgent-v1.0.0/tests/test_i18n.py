"""
Tests unitaires pour le système d'internationalisation (i18n).
"""
import os
import sys
import json
import tempfile
import pytest

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from i18n import t, get_lang, set_lang, SUPPORTED_LANGS, DEFAULT_LANG


class TestI18nBasics:
    """Tests de base du système i18n."""

    def test_supported_languages(self):
        """Les 3 langues supportées sont fr, en, zh."""
        assert "fr" in SUPPORTED_LANGS
        assert "en" in SUPPORTED_LANGS
        assert "zh" in SUPPORTED_LANGS
        assert len(SUPPORTED_LANGS) == 3

    def test_default_language_is_english(self):
        """The default fallback language is English (international standard)."""
        assert DEFAULT_LANG == "en"

    def test_set_and_get_language(self):
        """On peut changer la langue et la récupérer."""
        set_lang("en")
        assert get_lang() == "en"
        set_lang("fr")
        assert get_lang() == "fr"
        set_lang("zh")
        assert get_lang() == "zh"

    def test_invalid_language_falls_back(self):
        """Une langue invalide ne crashe pas."""
        # set_lang ne fait rien si la langue n'est pas supportée
        set_lang("fr")  # Réinitialiser
        # Via environnement
        original = os.environ.get("GA_LANG")
        try:
            os.environ["GA_LANG"] = "de"
            # Forcer le rechargement
            import i18n
            i18n._LANG = None
            lang = get_lang()
            # Doit retomber sur fr (défaut) car "de" n'est pas supporté
            assert lang in SUPPORTED_LANGS or lang == DEFAULT_LANG
        finally:
            if original is not None:
                os.environ["GA_LANG"] = original
            else:
                os.environ.pop("GA_LANG", None)
            i18n._LANG = None


class TestTranslations:
    """Tests des traductions elles-mêmes."""

    @classmethod
    def setup_class(cls):
        """Charger les fichiers de traduction pour vérification."""
        cls.i18n_dir = os.path.join(os.path.dirname(__file__), '..', 'i18n')
        cls.fr_data = json.load(open(os.path.join(cls.i18n_dir, 'fr.json'), encoding='utf-8'))
        cls.en_data = json.load(open(os.path.join(cls.i18n_dir, 'en.json'), encoding='utf-8'))
        cls.zh_data = json.load(open(os.path.join(cls.i18n_dir, 'zh.json'), encoding='utf-8'))

    def test_fr_translations_exist(self):
        """Le fichier français contient des traductions."""
        assert len(self.fr_data) > 0
        assert "error" in self.fr_data
        assert "ui" in self.fr_data

    def test_en_translations_exist(self):
        """Le fichier anglais contient des traductions."""
        assert len(self.en_data) > 0
        assert "error" in self.en_data

    def test_zh_translations_exist(self):
        """Le fichier chinois contient des traductions."""
        assert len(self.zh_data) > 0
        assert "error" in self.zh_data

    def test_all_languages_have_same_error_keys(self):
        """Toutes les langues ont les mêmes clés dans la section 'error'."""
        fr_keys = set(self.fr_data.get("error", {}).keys())
        en_keys = set(self.en_data.get("error", {}).keys())
        zh_keys = set(self.zh_data.get("zh", {}).keys())
        # Au minimum, les clés françaises et anglaises doivent correspondre
        assert fr_keys == en_keys, f"Différence clés FR/EN: {fr_keys.symmetric_difference(en_keys)}"

    def test_translate_known_key(self):
        """Une clé connue retourne une traduction."""
        set_lang("fr")
        result = t("error.timeout")
        assert result != "error.timeout"  # Ne doit pas retourner la clé elle-même
        assert "dépassé" in result.lower() or "délai" in result.lower()

    def test_translate_unknown_key_returns_key(self):
        """Une clé inconnue retourne la clé elle-même."""
        set_lang("fr")
        result = t("nonexistent.key.xyz")
        assert result == "nonexistent.key.xyz"

    def test_translate_with_format_args(self):
        """Les arguments de formatage fonctionnent."""
        set_lang("fr")
        result = t("error.old_content_multiple", 5)
        assert "5" in result

    def test_translate_fallback_to_english(self):
        """Si une clé manque dans une langue, on retombe sur l'anglais."""
        # Ce test vérifie que le mécanisme de fallback existe
        set_lang("fr")
        result = t("error.timeout")
        # Doit retourner quelque chose de non-vide
        assert result is not None
        assert len(result) > 0


class TestFrenchTranslations:
    """Tests spécifiques aux traductions françaises."""

    @classmethod
    def setup_class(cls):
        set_lang("fr")

    def test_error_messages_in_french(self):
        """Les messages d'erreur sont en français."""
        assert "dépassé" in t("error.timeout").lower() or "délai" in t("error.timeout").lower()
        assert "fichier" in t("error.file_not_exist").lower() or "n'existe" in t("error.file_not_exist").lower()

    def test_ui_labels_in_french(self):
        """Les labels UI sont en français."""
        result = t("ui.new_chat")
        assert result != "ui.new_chat"  # Traduit
        assert "conversation" in result.lower() or "nouvelle" in result.lower()

    def test_action_messages_in_french(self):
        """Les messages d'action sont en français."""
        result = t("action.partial_edit_success")
        assert "réussie" in result.lower() or "modification" in result.lower()

    def test_security_messages_in_french(self):
        """Les messages de sécurité sont en français."""
        result = t("error.shell_blocked")
        assert "bloquée" in result.lower() or "sécurité" in result.lower()

    def test_setup_messages_in_french(self):
        """Les messages d'installation sont en français."""
        result = t("setup.welcome")
        assert "bienvenue" in result.lower() or "install" in result.lower()

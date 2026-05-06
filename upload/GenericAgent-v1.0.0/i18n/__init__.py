# ══════════════════════════════════════════════════════════════════════════════
#  GenericAgent — Internationalization system (i18n)
#  Replaces all hardcoded text with a translation lookup system
# ══════════════════════════════════════════════════════════════════════════════
"""
Usage:
    from i18n import t
    
    t("error.timeout")              → "Request timed out"
    t("ui.new_chat")                → "New conversation"
    t("error.no_browser_tab")       → "No browser tab available"
    
Language is detected from:
    1. GA_LANG environment variable
    2. System locale (locale.getlocale / locale.getdefaultlocale)
    3. OS environment variables (LANG, LC_ALL, LC_MESSAGES, LANGUAGE)
    4. Fallback: "en" (English — international default)
"""
import json
import locale
import os

_LANG = None
_MESSAGES = {}

SUPPORTED_LANGS = ("fr", "en", "zh")
DEFAULT_LANG = "en"


def _locale_to_lang(locale_str: str) -> str | None:
    """Map a locale code like 'fr_FR', 'en_US', 'zh_CN' to a supported language code.

    Handles codes with encoding suffixes (e.g. 'fr_FR.UTF-8') and bare
    language codes (e.g. 'fr', 'zh').  Returns ``None`` if the locale
    cannot be mapped to a supported language.
    """
    if not locale_str:
        return None
    # Strip encoding suffix (e.g. ".UTF-8")
    code = locale_str.split(".")[0].strip().lower()
    # Try exact match first (e.g. "fr", "en", "zh")
    if code in SUPPORTED_LANGS:
        return code
    # Try language part of ll_CC locale (e.g. "fr_fr" → "fr", "zh_cn" → "zh")
    lang_part = code.split("_")[0]
    if lang_part in SUPPORTED_LANGS:
        return lang_part
    # Handle special cases: zh_Hant, zh_TW → zh, etc.
    if lang_part == "chinese":
        return "zh"
    return None


def get_lang():
    """Determine the active language.

    Priority:
        1. ``GA_LANG`` environment variable
        2. System locale (``locale.getlocale()`` then ``locale.getdefaultlocale()``)
        3. OS environment variables (LANG, LC_ALL, LC_MESSAGES, LANGUAGE)
        4. Fallback to ``DEFAULT_LANG`` ("en")
    """
    global _LANG
    if _LANG is not None:
        return _LANG

    # 1. Check GA_LANG environment variable
    lang = os.environ.get("GA_LANG", "").strip().lower()
    if lang in SUPPORTED_LANGS:
        _LANG = lang
        return _LANG

    # 2. Check system locale
    try:
        # locale.getlocale() returns (language_code, encoding) for the LC_CTYPE category
        loc = locale.getlocale()
        if loc and loc[0]:
            mapped = _locale_to_lang(loc[0])
            if mapped:
                _LANG = mapped
                return _LANG
    except (ValueError, TypeError):
        pass

    try:
        # locale.getdefaultlocale() is deprecated in 3.11+ but still works
        # and may return a value when getlocale() does not.
        # We use getattr to handle the case where it has been removed entirely
        # in a future Python version.
        _gdl = getattr(locale, "getdefaultlocale", None)
        if _gdl is not None and callable(_gdl):
            loc = _gdl()
            if loc and loc[0]:
                mapped = _locale_to_lang(loc[0])
                if mapped:
                    _LANG = mapped
                    return _LANG
    except (ValueError, TypeError, AttributeError, DeprecationWarning):
        pass

    # 3. Try OS environment variables as a last resort before fallback
    for env_var in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        env_val = os.environ.get(env_var, "")
        if env_val:
            mapped = _locale_to_lang(env_val)
            if mapped:
                _LANG = mapped
                return _LANG

    # 4. Fallback to English (international default)
    _LANG = DEFAULT_LANG
    return _LANG

def set_lang(lang):
    """Force la langue."""
    global _LANG, _MESSAGES
    if lang in SUPPORTED_LANGS:
        _LANG = lang
        _MESSAGES = {}
        _load_messages(lang)

def _load_messages(lang):
    """Charge les messages pour une langue donnée."""
    global _MESSAGES
    if lang in _MESSAGES:
        return _MESSAGES[lang]
    i18n_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(i18n_dir, f"{lang}.json")
    if not os.path.exists(filepath):
        filepath = os.path.join(i18n_dir, "en.json")
        if not os.path.exists(filepath):
            return {}
    try:
        with open(filepath, encoding="utf-8") as f:
            _MESSAGES[lang] = json.load(f)
    except (json.JSONDecodeError, OSError):
        _MESSAGES[lang] = {}
    return _MESSAGES[lang]

def t(key, *args, **kwargs):
    """
    Traduit une clé en texte localisé.
    Args:
        key: Clé de traduction (ex: "error.timeout")
        *args, **kwargs: Arguments pour le formatage
    Returns:
        Texte traduit, ou la clé elle-même si non trouvée
    """
    lang = get_lang()
    messages = _load_messages(lang)
    parts = key.split(".")
    value = messages
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            en_messages = _load_messages("en")
            value = en_messages
            for p in parts:
                if isinstance(value, dict) and p in value:
                    value = value[p]
                else:
                    return key
            break
    if isinstance(value, str):
        if args or kwargs:
            try:
                return value.format(*args, **kwargs)
            except (IndexError, KeyError):
                return value
        return value
    return key

translate = t

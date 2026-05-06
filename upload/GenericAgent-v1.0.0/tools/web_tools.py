"""tools.web_tools — Web / browser operation utilities for GenericAgent.

Extracted from ga.py as part of the Phase 3 monolith split (task 3.1.1).

This module provides web-scanning and JS-execution functions that operate
through the TMWebDriver browser automation layer:

- :func:`web_scan` — Retrieve simplified HTML & tab list from the active browser
- :func:`web_execute_js` — Execute JavaScript in the browser and capture results
- :func:`first_init_driver` — Lazy-initialise the TMWebDriver singleton
- :data:`_driver` — Module-level browser driver instance (lazy-initialised)
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import time
import traceback
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Système de traduction i18n (same fallback pattern as ga.py)
# ---------------------------------------------------------------------------
try:
    from i18n import t
except ImportError:
    def t(key: str, *args: Any, **kwargs: Any) -> str:  # type: ignore[misc]
        """Fallback si le module i18n n'est pas disponible."""
        _fallback: dict[str, str] = {
            "error.no_browser_tab": "Aucun onglet navigateur disponible. Consultez la mémoire L3 pour la cause.",
        }
        msg = _fallback.get(key, key)
        if args:
            try:
                return msg.format(*args)
            except (IndexError, KeyError):
                return msg
        return msg

logger = logging.getLogger("ga.web_tools")

# ---------------------------------------------------------------------------
# Directory where this package lives — used for header scripts & temp dir
# ---------------------------------------------------------------------------
script_dir: str = os.path.dirname(os.path.abspath(__file__))
# Walk one level up so that ``script_dir`` matches the *project* root
_project_root: str = os.path.dirname(script_dir)


# ---------------------------------------------------------------------------
# smart_format — shared string truncation utility (local copy to avoid
# circular import with tools.file_ops at module load time)
# ---------------------------------------------------------------------------
def _smart_format(data: Any, max_str_len: int = 100, omit_str: str = " ... ") -> str:
    """Tronque intelligemment une chaîne en conservant le début et la fin."""
    if not isinstance(data, str):
        data = str(data)
    if len(data) < max_str_len + len(omit_str) * 2:
        return data
    return f"{data[: max_str_len // 2]}{omit_str}{data[-max_str_len // 2 :]}"


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════
__all__ = [
    "web_scan",
    "web_execute_js",
    "first_init_driver",
    "_driver",
    "format_error",
]


# ---------------------------------------------------------------------------
# Module-level browser driver (lazy-initialised)
# ---------------------------------------------------------------------------
_driver: Optional[Any] = None


def format_error(e: Exception) -> str:
    """Formate une exception avec le type, le message et la localisation dans le code.

    Extrait la dernière frame du traceback pour indiquer le fichier et la ligne
    exacts où l'erreur s'est produite.

    Args:
        e: L'exception à formater.

    Returns:
        str: Message formaté de type "ExcType: message @ fichier:ligne, fonction -> code".
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb = traceback.extract_tb(exc_traceback)
    if tb:
        f = tb[-1]
        fname = os.path.basename(f.filename)
        return f"{exc_type.__name__}: {str(e)} @ {fname}:{f.lineno}, {f.name} -> `{f.line}`"
    return f"{exc_type.__name__}: {str(e)}"


def first_init_driver() -> None:
    """Initialise le pilote navigateur TMWebDriver au premier appel.

    Attend jusqu'à 20 secondes pour qu'une session navigateur soit disponible.
    Si l'initialisation échoue, le driver reste None et l'appelant gérera l'erreur.
    """
    global _driver
    try:
        from TMWebDriver import TMWebDriver

        _driver = TMWebDriver()
    except (ImportError, OSError) as e:
        logger.error("Échec de l'initialisation du pilote navigateur : %s", e)
        _driver = None
        return
    sess: list = []
    for i in range(20):
        time.sleep(1)
        try:
            sess = _driver.get_all_sessions()
        except (ConnectionError, OSError) as e:
            logger.debug("Waiting for browser session... (%s)", e)
            continue
        if len(sess) > 0:
            break
    if len(sess) == 0:
        logger.warning("Aucune session navigateur disponible après 20 secondes")
        return
    if len(sess) == 1:
        time.sleep(3)


def web_scan(
    tabs_only: bool = False,
    switch_tab_id: Optional[str] = None,
    text_only: bool = False,
) -> dict[str, Any]:
    """Récupère le contenu HTML simplifié de la page courante et la liste des onglets.

    Note : la simplification filtre les barres latérales, éléments flottants, etc.

    Args:
        tabs_only: Retourne uniquement la liste des onglets, sans contenu HTML (économise des tokens).
        switch_tab_id: Optionnel, si fourni, bascule vers cet onglet avant le scan.
        text_only: Retourne uniquement le texte sans balises HTML.

    Returns:
        dict: Résultat avec statut, métadonnées des onglets, et contenu HTML optionnel.
    """
    global _driver
    try:
        if _driver is None:
            first_init_driver()
        if _driver is None or len(_driver.get_all_sessions()) == 0:
            logger.warning("web_scan: no browser tab available")
            return {"status": "error", "msg": t("error.no_browser_tab")}
        tabs: list[dict] = []
        for sess in _driver.get_all_sessions():
            sess.pop("connected_at", None)
            sess.pop("type", None)
            sess["url"] = sess.get("url", "")[:50] + (
                "..." if len(sess.get("url", "")) > 50 else ""
            )
            tabs.append(sess)
        if switch_tab_id:
            _driver.default_session_id = switch_tab_id
        result: dict[str, Any] = {
            "status": "success",
            "metadata": {
                "tabs_count": len(tabs),
                "tabs": tabs,
                "active_tab": _driver.default_session_id,
            },
        }
        if not tabs_only:
            import simphtml

            importlib.reload(simphtml)
            result["content"] = simphtml.get_html(
                _driver, cutlist=True, maxchars=35000, text_only=text_only
            )
            if text_only:
                result["content"] = _smart_format(
                    result["content"],
                    max_str_len=10000,
                    omit_str="\n\n[omitted long content]\n\n",
                )
        return result
    except Exception as e:
        logger.error("web_scan failed: %s", format_error(e))
        return {"status": "error", "msg": format_error(e)}


def web_execute_js(
    script: str,
    switch_tab_id: Optional[str] = None,
    no_monitor: bool = False,
) -> dict[str, Any]:
    """Exécute un script JS pour contrôler le navigateur et capture les résultats.

    Args:
        script: Code JavaScript à exécuter dans le navigateur.
        switch_tab_id: Identifiant de l'onglet cible (optionnel).
        no_monitor: Désactive le monitoring des changements DOM.

    Returns:
        dict: Résultat de l'exécution JavaScript avec statut et données.
    """
    global _driver
    try:
        if _driver is None:
            first_init_driver()
        if _driver is None or len(_driver.get_all_sessions()) == 0:
            logger.warning("web_execute_js: no browser tab available")
            return {"status": "error", "msg": t("error.no_browser_tab")}
        if switch_tab_id:
            _driver.default_session_id = switch_tab_id
        import simphtml

        result = simphtml.execute_js_rich(script, _driver, no_monitor=no_monitor)
        return result
    except Exception as e:
        logger.error("web_execute_js failed: %s", format_error(e))
        return {"status": "error", "msg": format_error(e)}

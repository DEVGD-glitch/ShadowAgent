# ══════════════════════════════════════════════════════════════════════════════
#  GenericAgent — Chargeur d'environnement (.env)
#  Charge les variables d'environnement depuis un fichier .env optionnel
# ══════════════════════════════════════════════════════════════════════════════

"""
Chargeur d'environnement pour GenericAgent.

Ce module fournit la fonction ``load_env()`` qui charge les variables
de configuration depuis un fichier ``.env`` placé à la racine du projet.
Si le fichier ``.env`` est absent, le module ne lève aucune erreur —
les variables d'environnement système ou les valeurs par défaut sont
utilisées à la place.

Variables supportées
--------------------
LLM_API_KEY : str
    Clé API pour le service LLM (ex : OpenAI, Anthropic).
    Valeur par défaut : chaîne vide.

LLM_BASE_URL : str
    URL de base du point de terminaison LLM.
    Valeur par défaut : chaîne vide.

LLM_MODEL : str
    Nom du modèle LLM à utiliser.
    Valeur par défaut : chaîne vide.

AGENT_WORKSPACE_DIR : str
    Répertoire de travail de l'agent pour les fichiers temporaires
    et les sorties.
    Valeur par défaut : ``"workspace"``.

LOG_LEVEL : str
    Niveau de journalisation (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    Valeur par défaut : ``"INFO"``.

Utilisation
-----------
::

    from env_loader import load_env

    load_env()  # À appeler une seule fois au démarrage

Notes
-----
- Le fichier ``.env`` ne doit **jamais** être versionné (il est dans
  ``.gitignore``).
- Utilisez ``.env.example`` comme modèle pour documenter les variables
  attendues.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Valeurs par défaut ──────────────────────────────────────────────────────
_DEFAULTS: dict[str, str] = {
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "",
    "LLM_MODEL": "",
    "AGENT_WORKSPACE_DIR": "workspace",
    "LOG_LEVEL": "INFO",
}

# ── Clés reconnues ──────────────────────────────────────────────────────────
_SUPPORTED_KEYS: list[str] = list(_DEFAULTS.keys())


def _find_env_file(start: Optional[Path] = None) -> Optional[Path]:
    """Recherche le fichier ``.env`` en remontant l'arborescence.

    Parcourt les répertoires parents depuis *start* jusqu'à la racine
    du système de fichiers pour localiser un fichier ``.env``.

    Paramètres
    ----------
    start : Path | None
        Répertoire de départ pour la recherche. Si ``None``, utilise
        le répertoire parent de ce fichier (la racine du projet).

    Retourne
    --------
    Path | None
        Chemin vers le fichier ``.env`` trouvé, ou ``None`` si absent.
    """
    if start is None:
        start = Path(__file__).resolve().parent

    current = start
    for _ in range(10):  # Limite de profondeur pour éviter les boucles infinies
        candidate = current / ".env"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def load_env(env_path: Optional[Path] = None) -> None:
    """Charge les variables d'environnement depuis un fichier ``.env``.

    Cette fonction tente de charger un fichier ``.env`` et d'en injecter
    les valeurs dans ``os.environ``. Les variables déjà définies dans
    l'environnement ne sont **pas** écrasées.

    Si le fichier ``.env`` est introuvable, la fonction se contente de
    journaliser un message informatif et n'échoue pas silencieusement.

    Paramètres
    ----------
    env_path : Path | None
        Chemin explicite vers le fichier ``.env``. Si ``None``, la
        fonction recherche automatiquement le fichier en remontant
        l'arborescence depuis la racine du projet.

    Effets de bord
    --------------
    - Définit les variables d'environnement manquantes avec leurs
      valeurs par défaut.
    - Journalise le résultat du chargement au niveau ``DEBUG``.

    Exemples
    --------
    ::

        # Chargement automatique (recherche .env)
        load_env()

        # Chargement depuis un chemin explicite
        from pathlib import Path
        load_env(Path("/opt/genericagent/.env"))
    """
    # ── Tentative de chargement du fichier .env ─────────────────────────
    loaded_from_file = False

    if env_path is not None:
        if env_path.is_file():
            _load_dotenv(env_path)
            loaded_from_file = True
        else:
            logger.debug(
                "Fichier .env spécifié introuvable : %s — "
                "utilisation des valeurs par défaut.",
                env_path,
            )
    else:
        found = _find_env_file()
        if found is not None:
            _load_dotenv(found)
            loaded_from_file = True
        else:
            logger.debug(
                "Aucun fichier .env trouvé — "
                "utilisation des valeurs par défaut."
            )

    if loaded_from_file:
        logger.debug("Variables d'environnement chargées depuis .env")

    # ── Application des valeurs par défaut pour les clés manquantes ─────
    for key, default in _DEFAULTS.items():
        if key not in os.environ or os.environ[key] == "":
            os.environ.setdefault(key, default)

    # ── Configuration du niveau de journalisation ───────────────────────
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.getLogger("genericagent").setLevel(
        getattr(logging, log_level, logging.INFO)
    )


def _load_dotenv(path: Path) -> None:
    """Charge un fichier ``.env`` avec ``python-dotenv`` si disponible.

    Utilise ``dotenv.load_dotenv`` si le paquet ``python-dotenv`` est
    installé. Sinon, effectue un parsage manuel rudimentaire du fichier.

    Paramètres
    ----------
    path : Path
        Chemin absolu vers le fichier ``.env`` à charger.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(path, override=False)
    except ImportError:
        # Parsage manuel de secours si python-dotenv n'est pas installé
        logger.debug(
            "python-dotenv non installé — parsage manuel du fichier .env"
        )
        _parse_dotenv_manual(path)


def _parse_dotenv_manual(path: Path) -> None:
    """Parsage manuel rudimentaire d'un fichier ``.env``.

    Lit le fichier ligne par ligne, ignore les commentaires (``#``) et
    les lignes vides, et définit les variables dans ``os.environ`` sans
    écraser les valeurs existantes.

    Paramètres
    ----------
    path : Path
        Chemin vers le fichier ``.env`` à analyser.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key in _SUPPORTED_KEYS:
                    os.environ.setdefault(key, value)
    except OSError as exc:
        logger.warning("Impossible de lire le fichier .env : %s", exc)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Récupère une variable d'environnement avec valeur par défaut optionnelle.

    Fonction utilitaire qui encapsule ``os.environ.get`` avec une
    vérification que la clé fait partie des variables supportées.

    Paramètres
    ----------
    key : str
        Nom de la variable d'environnement.
    default : str | None
        Valeur par défaut si la variable n'est pas définie.

    Retourne
    --------
    str | None
        Valeur de la variable, ou *default* si absente.

    Exemples
    --------
    ::

        api_key = get_env("LLM_API_KEY")
        workspace = get_env("AGENT_WORKSPACE_DIR", "workspace")
    """
    if default is None and key in _DEFAULTS:
        default = _DEFAULTS[key]
    return os.environ.get(key, default)

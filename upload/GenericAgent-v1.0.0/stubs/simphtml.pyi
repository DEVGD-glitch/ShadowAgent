"""Type stubs for the simphtml module.

Fournit les annotations de type pour les fonctions publiques
du module :mod:`simphtml` utilisé par GenericAgent pour la
simplification HTML et l'exécution JavaScript riche.
"""

from typing import Any, Optional


def get_html(
    driver: Any,
    cutlist: bool = False,
    maxchars: int = 35000,
    instruction: str = "",
    extra_js: str = "",
    text_only: bool = False,
) -> str:
    """Récupère le contenu HTML simplifié de la page courante.

    Paramètres
    ----------
    driver : Any
        Pilote navigateur (TMWebDriver) pour l'accès à la page.
    cutlist : bool
        Si ``True``, applique le filtrage de la cutlist pour supprimer
        les éléments non pertinents (barres latérales, flottants, etc.).
    maxchars : int
        Nombre maximal de caractères du résultat.
    instruction : str
        Instruction optionnelle injectée avant la simplification.
    extra_js : str
        JavaScript supplémentaire à exécuter avant l'extraction.
    text_only : bool
        Si ``True``, retourne uniquement le texte sans balises HTML.

    Retourne
    --------
    str
        Contenu HTML simplifié ou texte extrait.
    """
    ...


def execute_js_rich(
    script: str,
    driver: Any,
    no_monitor: bool = False,
) -> dict[str, Any]:
    """Exécute un script JavaScript et capture les résultats avec monitoring DOM.

    Paramètres
    ----------
    script : str
        Code JavaScript à exécuter dans le navigateur.
    driver : Any
        Pilote navigateur (TMWebDriver) pour l'exécution JS.
    no_monitor : bool
        Si ``True``, désactive le monitoring des changements DOM
        avant/après l'exécution.

    Retourne
    --------
    dict[str, Any]
        Dictionnaire contenant au minimum les clés :
        - ``'status'`` : ``'success'`` ou ``'failed'``
        - ``'js_return'`` : valeur retournée par le script
        - ``'tab_id'`` : identifiant de l'onglet actif
    """
    ...

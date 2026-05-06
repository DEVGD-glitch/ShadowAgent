"""Type stubs for the TMWebDriver module.

Fournit les annotations de type pour la classe :class:`TMWebDriver`
utilisée par GenericAgent pour le contrôle de navigateur via CDP
et WebSocket.
"""

from typing import Any, Optional


class TMWebDriver:
    """Pilote de navigateur basé sur CDP / WebSocket.

    Contrôle un navigateur Chrome/Edge via le Chrome DevTools Protocol
    ou via une extension WebSocket pour l'exécution de JavaScript
    et la gestion des sessions (onglets).

    Attributs
    ---------
    default_session_id : str
        Identifiant de la session (onglet) active par défaut.
    sessions : dict[str, Any]
        Dictionnaire des sessions de navigateur connectées.
    is_remote : bool
        Si ``True``, le pilote fonctionne en mode distant.
    remote : str | None
        URL du serveur distant en mode remote.
    """

    default_session_id: str
    sessions: dict[str, Any]
    is_remote: bool
    remote: Optional[str]

    def __init__(self, remote: Optional[str] = None) -> None:
        """Initialise le pilote de navigateur.

        Paramètres
        ----------
        remote : str | None
            URL optionnelle du serveur TMWebDriver distant.
        """
        ...

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Retourne la liste des sessions de navigateur actives.

        Retourne
        --------
        list[dict[str, Any]]
            Liste de dictionnaires contenant ``'id'``, ``'url'``,
            et autres métadonnées de chaque session active.
        """
        ...

    def get_session_dict(self) -> dict[str, str]:
        """Retourne un dictionnaire associant les IDs de session à leurs URLs.

        Retourne
        --------
        dict[str, str]
            Mapping ``{session_id: url}`` des sessions actives.
        """
        ...

    def execute_js(
        self,
        code: str,
        timeout: int = 15,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Exécute un script JavaScript dans l'onglet spécifié.

        Paramètres
        ----------
        code : str
            Code JavaScript à exécuter.
        timeout : int
            Délai maximum d'attente en secondes (défaut : 15).
        session_id : str | None
            Identifiant de session optionnel. Si ``None``, utilise
            ``default_session_id``.

        Retourne
        --------
        dict[str, Any]
            Résultat contenant ``'data'`` (valeur de retour JS) et
            potentiellement ``'newTabs'`` et ``'closed'``.
        """
        ...

    def find_session(self, url_pattern: str) -> Optional[dict[str, Any]]:
        """Recherche une session dont l'URL correspond au motif donné.

        Paramètres
        ----------
        url_pattern : str
            Motif de recherche (sous-chaîne) dans l'URL de la session.

        Retourne
        --------
        dict[str, Any] | None
            Dictionnaire de la première session correspondante, ou ``None``.
        """
        ...

    def clean_sessions(self) -> None:
        """Nettoie les sessions inactives du registre interne."""
        ...

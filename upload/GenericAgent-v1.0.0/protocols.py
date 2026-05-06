"""Protocoles et énumérations pour le typage structurel de GenericAgent.

Ce module définit les interfaces Protocol et les énumérations utilisées
pour le sous-typage structurel (structural subtyping) à travers le projet.
Elles permettent de vérifier la conformité des classes existantes sans
héritage explicite, améliorant ainsi la sécurité des types et la
documentabilité du code.

Protocoles définis
------------------
- :class:`LLMSessionProtocol` — interface d'une session LLM
- :class:`HandlerProtocol` — interface d'un gestionnaire d'outils agent
- :class:`AgentProtocol` — interface de l'agent principal
- :class:`BrowserDriverProtocol` — interface du pilote navigateur

Énumérations
------------
- :class:`LLMProvider` — fournisseurs LLM pris en charge
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generator, Optional, Protocol, runtime_checkable


# ══════════════════════════════════════════════════════════════════════════════
#  Énumérations
# ══════════════════════════════════════════════════════════════════════════════


class LLMProvider(Enum):
    """Fournisseurs LLM pris en charge par GenericAgent.

    Chaque membre représente une famille de modèles accessible via
    une API compatible (native ou relayée).

    Membres
    -------
    OPENAI
        OpenAI GPT et API compatible (chat_completions / responses).
    CLAUDE
        Anthropic Claude (API Messages native).
    GEMINI
        Google Gemini (via endpoint compatible OpenAI).
    DEEPSEEK
        DeepSeek (reasoning models, via endpoint compatible OpenAI).
    LOCAL
        Modèles locaux servis par Ollama, vLLM, LM Studio, etc.
    """

    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    LOCAL = "local"


# ══════════════════════════════════════════════════════════════════════════════
#  Protocoles
# ══════════════════════════════════════════════════════════════════════════════


@runtime_checkable
class LLMSessionProtocol(Protocol):
    """Protocole pour une session de communication avec un LLM.

    Toute classe qui possède les méthodes et propriétés listées ci-dessous
    satisfait ce protocole et peut être utilisée partout où un
    ``LLMSessionProtocol`` est attendu.

    Méthodes
    --------
    stream(prompt, history, ...)
        Envoie un prompt au LLM et retourne un générateur de chunks texte.
    abort()
        Interrompt la session en cours.

    Propriétés
    ----------
    model_name : str
        Identifiant du modèle utilisé (ex. ``"claude-sonnet-4-6"``).
    api_mode : str
        Mode d'API — ``"chat_completions"``, ``"responses"``, ou ``"messages"``.
    """

    @property
    def model_name(self) -> str:
        """Identifiant du modèle utilisé par cette session."""
        ...

    @property
    def api_mode(self) -> str:
        """Mode d'API de la session (``'chat_completions'``, ``'responses'``, ``'messages'``)."""
        ...

    def stream(
        self,
        prompt: str,
        history: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Generator[str, None, list[dict[str, Any]]]:
        """Envoie un prompt au LLM et retourne un générateur de chunks texte.

        Paramètres
        ----------
        prompt : str
            Le texte de la requête utilisateur.
        history : list[dict] | None
            Historique de conversation optionnel. Si ``None``, l'historique
            interne de la session est utilisé.
        **kwargs
            Arguments supplémentaires transmis à l'API.

        Retourne
        --------
        Generator[str, None, list[dict[str, Any]]]
            Générateur produisant des fragments de texte ; la valeur de
            retour finale est la liste des blocs de contenu parsés.
        """
        ...

    def abort(self) -> None:
        """Interrompt la requête en cours et libère les ressources."""
        ...


@runtime_checkable
class HandlerProtocol(Protocol):
    """Protocole pour un gestionnaire d'outils de l'agent.

    Le handler reçoit les résultats de chaque étape (``StepOutcome``)
    et décide si la boucle agent doit continuer.

    Méthodes
    --------
    handle_step(outcome)
        Traite le résultat d'une étape d'exécution d'outil.
    should_continue(outcome) -> bool
        Détermine si la boucle agent doit poursuivre après cette étape.
    """

    def handle_step(self, outcome: Any) -> Any:
        """Traite le résultat d'une étape d'exécution d'outil.

        Paramètres
        ----------
        outcome : Any
            Le résultat de l'étape (généralement un ``StepOutcome``).

        Retourne
        --------
        Any
            Résultat du traitement, potentiellement modifié.
        """
        ...

    def should_continue(self, outcome: Any) -> bool:
        """Détermine si la boucle agent doit poursuivre après cette étape.

        Paramètres
        ----------
        outcome : Any
            Le résultat de l'étape à évaluer.

        Retourne
        --------
        bool
            ``True`` si la boucle doit continuer, ``False`` sinon.
        """
        ...


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocole pour l'agent principal GenericAgent.

    Définit l'interface minimale que doit satisfaire un agent pour
    interagir avec les frontaux (Qt, Streamlit, CLI, etc.).

    Méthodes
    --------
    put_task(prompt, files)
        Enfile une tâche et retourne une file de résultats.
    abort()
        Signale à l'agent d'interrompre la tâche en cours.
    switch_model(index)
        Change le modèle LLM actif vers l'indice spécifié.
    """

    def put_task(
        self,
        prompt: str,
        files: Optional[list[str]] = None,
    ) -> Any:
        """Enfile une tâche pour l'agent et retourne une file de résultats.

        Paramètres
        ----------
        prompt : str
            Le texte de la requête utilisateur.
        files : list[str] | None
            Liste optionnelle de chemins de fichiers à joindre.

        Retourne
        --------
        Any
            Une file (``queue.Queue``) sur laquelle les résultats
            seront publiés.
        """
        ...

    def abort(self) -> None:
        """Signale à l'agent d'interrompre la tâche en cours."""
        ...

    def switch_model(self, index: int) -> None:
        """Change le modèle LLM actif vers l'indice spécifié.

        Paramètres
        ----------
        index : int
            Indice du modèle dans la liste des clients LLM disponibles.
        """
        ...


@runtime_checkable
class BrowserDriverProtocol(Protocol):
    """Protocole pour le pilote de navigateur (CDP / WebSocket).

    Définit l'interface minimale pour interagir avec un navigateur
    contrôlé à distance via le protocole CDP ou WebSocket.

    Méthodes
    --------
    get_all_sessions()
        Retourne la liste des sessions (onglets) actives.
    execute_js(script)
        Exécute un script JavaScript dans l'onglet actif.
    """

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Retourne la liste des sessions (onglets) de navigateur actives.

        Retourne
        --------
        list[dict[str, Any]]
            Liste de dictionnaires, chacun contenant au minimum
            ``'id'`` et ``'url'`` de la session.
        """
        ...

    def execute_js(
        self,
        script: str,
        timeout: int = 15,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Exécute un script JavaScript dans l'onglet de navigateur actif.

        Paramètres
        ----------
        script : str
            Code JavaScript à exécuter.
        timeout : int
            Délai maximum d'attente en secondes (défaut : 15).
        session_id : str | None
            Identifiant de session optionnel pour cibler un onglet spécifique.

        Retourne
        --------
        dict[str, Any]
            Résultat de l'exécution, contenant au moins la clé ``'data'``.
        """
        ...


# ══════════════════════════════════════════════════════════════════════════════
#  API publique
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "LLMProvider",
    "LLMSessionProtocol",
    "HandlerProtocol",
    "AgentProtocol",
    "BrowserDriverProtocol",
]

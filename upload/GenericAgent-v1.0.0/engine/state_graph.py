"""Moteur de graphe d'état pour GenericAgent v0.6.0.

Ce module implémente un moteur d'exécution basé sur un graphe d'état dirigé,
inspiré de l'architecture LangGraph. Il remplace la boucle agent simple par
un graphe avec support des cycles, du typage d'état avec réducteurs, du
checkpointing pour la tolérance aux pannes, des arêtes conditionnelles pour
le routage dynamique, de la composition de sous-graphes hiérarchiques et du
streaming multi-niveau.

Concepts fondamentaux
---------------------
- **Nœud** : une fonction Python prenant l'état courant et retournant un
  dictionnaire de mises à jour partielles.
- **Arête** : un lien orienté entre deux nœuds déterminant le flux de
  contrôle séquentiel.
- **Arête conditionnelle** : un lien orienté dont la cible est déterminée
  dynamiquement par une fonction de routage.
- **Réducteur** : fonction de fusion appliquée à chaque clé d'état lorsque
  plusieurs nœuds parallèles produisent des mises à jour concurrentes.
- **Checkpoint** : sauvegarde complète de l'état après chaque étape,
  permettant la reprise après panne.

Exemple d'utilisation
---------------------
>>> from typing import TypedDict
>>> class AgentState(TypedDict):
...     messages: list
...     next_action: str
>>> graph = StateGraph(AgentState, reducers={"messages": add_messages})
>>> graph.add_node("think", think_fn)
>>> graph.add_node("act", act_fn)
>>> graph.add_edge("think", "act")
>>> graph.add_conditional_edges("act", route_fn, {"retry": "think", "done": "__end__"})
>>> graph.set_entry_point("think")
>>> compiled = graph.compile(checkpointer=MemoryCheckpointer())
>>> result = compiled.invoke({"messages": [], "next_action": ""})
"""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Type,
    Union,
    runtime_checkable,
)

from logging_config import get_logger

logger = get_logger("engine.state_graph")


# ══════════════════════════════════════════════════════════════════════════════
#  Exceptions
# ══════════════════════════════════════════════════════════════════════════════


class GraphError(Exception):
    """Exception de base pour toutes les erreurs liées au graphe d'état.

    Paramètres
    ----------
    message : str
        Description lisible de l'erreur.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


class GraphCompileError(GraphError):
    """Levée lorsque la compilation du graphe échoue (structure invalide).

    Causes possibles : nœud manquant, arête vers un nœud inexistant,
    point d'entrée non défini, cycle sans point de sortie, etc.
    """


class GraphExecutionError(GraphError):
    """Levée lorsqu'une erreur se produit pendant l'exécution du graphe.

    Le détail de l'erreur originale est conservé dans l'attribut
    ``__cause__``.
    """


# ══════════════════════════════════════════════════════════════════════════════
#  Énumérations et structures de données
# ══════════════════════════════════════════════════════════════════════════════


class StreamEventType(Enum):
    """Types d'événements de streaming émis pendant l'exécution du graphe.

    Membres
    -------
    TOKEN
        Fragment de texte émis par un nœud (streaming au niveau token).
    NODE_START
        Signal indiquant qu'un nœud commence son exécution.
    NODE_END
        Signal indiquant qu'un nœud a terminé son exécution.
    CUSTOM
        Événement personnalisé défini par l'utilisateur.
    ERROR
        Erreur survenue pendant l'exécution d'un nœud.
    """

    TOKEN = "token"
    NODE_START = "node_start"
    NODE_END = "node_end"
    CUSTOM = "custom"
    ERROR = "error"


@dataclass(frozen=True)
class StreamEvent:
    """Événement de streaming émis pendant l'exécution du graphe.

    Attributs
    ---------
    type : StreamEventType
        Type de l'événement.
    node_name : str
        Nom du nœud source de l'événement.
    data : Any
        Données associées à l'événement (texte pour TOKEN, dict pour
        NODE_START/NODE_END, etc.).
    timestamp : datetime
        Horodatage UTC de l'événement.
    """

    type: StreamEventType
    node_name: str
    data: Any
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class NodeResult:
    """Résultat produit par l'exécution d'un nœud.

    Attributs
    ---------
    output : dict[str, Any]
        Dictionnaire de mises à jour partielles de l'état retourné par
        la fonction du nœud.
    metadata : dict[str, Any]
        Métadonnées optionnelles associées à l'exécution (durée, tokens
        consommés, etc.).
    """

    output: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
#  Réducteurs d'état
# ══════════════════════════════════════════════════════════════════════════════


@runtime_checkable
class StateReducer(Protocol):
    """Protocole pour une fonction de réduction d'état.

    Un réducteur définit comment fusionner une nouvelle valeur avec la
    valeur existante d'une clé d'état. Cela permet de résoudre les
    conflits lorsque plusieurs nœuds parallèles mettent à jour la même
    clé d'état simultanément.

    Méthodes
    --------
    reduce(existing, new) -> Any
        Fusionne la valeur existante avec la nouvelle et retourne le
        résultat.
    """

    def reduce(self, existing: Any, new: Any) -> Any:
        """Fusionne la valeur existante avec la nouvelle valeur.

        Paramètres
        ----------
        existing : Any
            Valeur actuelle de la clé d'état (``None`` si absente).
        new : Any
            Nouvelle valeur à intégrer.

        Retourne
        --------
        Any
            La valeur résultant de la fusion.
        """
        ...


class _AddMessagesReducer:
    """Réducteur qui ajoute des messages en évitant les doublons par identifiant.

    Pour chaque message dans *new*, si un message avec le même ``id``
    existe déjà dans *existing*, il est remplacé ; sinon, il est ajouté
    à la fin de la liste.

    Ce réducteur est inspiré de ``langgraph.graph.message.add_messages``.
    """

    def reduce(self, existing: Any, new: Any) -> list[dict[str, Any]]:
        """Ajoute ou remplace des messages en fonction de leur identifiant.

        Paramètres
        ----------
        existing : list[dict] | None
            Liste existante de messages (peut être ``None`` ou absente).
        new : list[dict] | dict | None
            Nouveau(x) message(s) à intégrer. Peut être un message
            unique ou une liste de messages.

        Retourne
        --------
        list[dict[str, Any]]
            Liste fusionnée de messages.
        """
        if existing is None:
            existing = []
        if new is None:
            return list(existing)
        if isinstance(new, dict):
            new = [new]

        existing_list: list[dict[str, Any]] = list(existing)
        existing_ids = {
            msg.get("id"): idx
            for idx, msg in enumerate(existing_list)
            if "id" in msg
        }

        for msg in new:
            msg_id = msg.get("id")
            if msg_id is not None and msg_id in existing_ids:
                existing_list[existing_ids[msg_id]] = msg
            else:
                existing_list.append(msg)
                if msg_id is not None:
                    existing_ids[msg_id] = len(existing_list) - 1

        return existing_list


class _LastValueReducer:
    """Réducteur qui remplace systématiquement la valeur existante par la nouvelle.

    Utile pour les clés d'état où seule la dernière valeur compte
    (par exemple un compteur, un drapeau, ou une chaîne de statut).
    """

    def reduce(self, existing: Any, new: Any) -> Any:
        """Remplace la valeur existante par la nouvelle.

        Paramètres
        ----------
        existing : Any
            Valeur actuelle (ignorée).
        new : Any
            Nouvelle valeur à conserver.

        Retourne
        --------
        Any
            La nouvelle valeur.
        """
        return new


class _AppendListReducer:
    """Réducteur qui étend la liste existante avec les nouveaux éléments.

    Contrairement à :class:`_AddMessagesReducer`, ce réducteur n'effectue
    aucune déduplication — il se contente d'ajouter les éléments à la fin.
    """

    def reduce(self, existing: Any, new: Any) -> list[Any]:
        """Étend la liste existante avec les nouveaux éléments.

        Paramètres
        ----------
        existing : list | None
            Liste existante (``None`` est traité comme une liste vide).
        new : list | Any
            Nouveaux éléments à ajouter. Si ce n'est pas une liste, la
            valeur est enveloppée dans une liste.

        Retourne
        --------
        list[Any]
            Liste étendue.
        """
        if existing is None:
            existing = []
        if new is None:
            return list(existing)
        if not isinstance(new, list):
            new = [new]
        return list(existing) + list(new)


# Instances singleton pour un usage pratique
add_messages = _AddMessagesReducer()
"""Réducteur pour les clés de type liste de messages avec déduplication par ``id``."""

last_value = _LastValueReducer()
"""Réducteur qui conserve uniquement la dernière valeur."""

append_list = _AppendListReducer()
"""Réducteur qui étend la liste existante sans déduplication."""


# ══════════════════════════════════════════════════════════════════════════════
#  Structures du graphe
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class GraphNode:
    """Représentation d'un nœud dans le graphe d'état.

    Attributs
    ---------
    name : str
        Identifiant unique du nœud dans le graphe.
    fn : Callable
        Fonction d'exécution du nœud. Prend l'état courant (dict) et
        retourne un dictionnaire de mises à jour partielles. Peut
        également retourner un :class:`NodeResult` pour inclure des
        métadonnées.
    metadata : dict[str, Any]
        Métadonnées optionnelles associées au nœud (description, tags,
        version, etc.).
    """

    name: str
    fn: Callable[..., Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Arête orientée statique entre deux nœuds du graphe.

    Attributs
    ---------
    from_node : str
        Nom du nœud source.
    to_node : str
        Nom du nœud cible.
    """

    from_node: str
    to_node: str


@dataclass
class ConditionalEdge:
    """Arête conditionnelle dont la cible est déterminée dynamiquement.

    Attributs
    ---------
    from_node : str
        Nom du nœud source.
    router_fn : Callable
        Fonction de routage prenant l'état courant et retournant le nom
        du nœud cible. La valeur retournée doit correspondre à une clé
        de ``targets`` ou être ``__end__``.
    targets : dict[str, str]
        Mapping entre les valeurs de retour possibles du routeur et les
        noms de nœuds cibles. La clé spéciale ``__end__`` indique la fin
        de l'exécution.
    """

    from_node: str
    router_fn: Callable[..., str]
    targets: dict[str, str] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
#  Checkpointing
# ══════════════════════════════════════════════════════════════════════════════


@runtime_checkable
class CheckpointProtocol(Protocol):
    """Protocole pour un système de checkpointing (sauvegarde/restauration).

    Un checkpointer permet de sauvegarder l'état complet du graphe après
    chaque étape d'exécution, offrant ainsi la possibilité de reprendre
    l'exécution après une panne ou d'inspecter l'historique des états.

    Méthodes
    --------
    save(thread_id, checkpoint_id, state)
        Sauvegarde un checkpoint pour un thread donné.
    load(thread_id, checkpoint_id) -> dict | None
        Charge un checkpoint spécifique.
    list_checkpoints(thread_id) -> list[str]
        Liste les identifiants de checkpoints pour un thread.
    delete(thread_id, checkpoint_id)
        Supprime un checkpoint spécifique.
    """

    def save(
        self, thread_id: str, checkpoint_id: str, state: dict[str, Any]
    ) -> None:
        """Sauvegarde un checkpoint.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant unique du checkpoint.
        state : dict[str, Any]
            État complet à sauvegarder.
        """
        ...

    def load(
        self, thread_id: str, checkpoint_id: str
    ) -> Optional[dict[str, Any]]:
        """Charge un checkpoint spécifique.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à charger.

        Retourne
        --------
        dict[str, Any] | None
            L'état sauvegardé, ou ``None`` si le checkpoint n'existe pas.
        """
        ...

    def list_checkpoints(self, thread_id: str) -> list[str]:
        """Liste les identifiants de checkpoints pour un thread.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.

        Retourne
        --------
        list[str]
            Liste ordonnée des identifiants de checkpoints.
        """
        ...

    def delete(self, thread_id: str, checkpoint_id: str) -> None:
        """Supprime un checkpoint spécifique.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à supprimer.
        """
        ...


class MemoryCheckpointer:
    """Checkpointer en mémoire pour le développement et les tests.

    Les checkpoints sont stockés dans un dictionnaire en mémoire et sont
    perdus à la fin du processus. Thread-safe via un verrou interne.

    Avertissement
    -------------
    Ce checkpointer n'est pas persistant — il ne doit pas être utilisé
    en production pour des données critiques.

    Attributs
    ---------
    _store : dict[str, dict[str, dict[str, Any]]]
        Structure de stockage : ``{thread_id: {checkpoint_id: state}}``.
    _lock : threading.Lock
        Verrou pour garantir la sécurité dans un contexte multi-thread.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def save(
        self, thread_id: str, checkpoint_id: str, state: dict[str, Any]
    ) -> None:
        """Sauvegarde un checkpoint en mémoire.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant unique du checkpoint.
        state : dict[str, Any]
            État complet à sauvegarder (copie profonde).
        """
        with self._lock:
            if thread_id not in self._store:
                self._store[thread_id] = {}
            self._store[thread_id][checkpoint_id] = copy.deepcopy(state)
        logger.debug(
            "Checkpoint sauvegardé : thread=%s, id=%s", thread_id, checkpoint_id
        )

    def load(
        self, thread_id: str, checkpoint_id: str
    ) -> Optional[dict[str, Any]]:
        """Charge un checkpoint depuis la mémoire.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à charger.

        Retourne
        --------
        dict[str, Any] | None
            Copie profonde de l'état sauvegardé, ou ``None``.
        """
        with self._lock:
            thread_data = self._store.get(thread_id)
            if thread_data is None:
                return None
            state = thread_data.get(checkpoint_id)
            if state is None:
                return None
            return copy.deepcopy(state)

    def list_checkpoints(self, thread_id: str) -> list[str]:
        """Liste les identifiants de checkpoints pour un thread.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.

        Retourne
        --------
        list[str]
            Liste triée des identifiants de checkpoints.
        """
        with self._lock:
            thread_data = self._store.get(thread_id)
            if thread_data is None:
                return []
            return sorted(thread_data.keys())

    def delete(self, thread_id: str, checkpoint_id: str) -> None:
        """Supprime un checkpoint de la mémoire.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à supprimer.
        """
        with self._lock:
            thread_data = self._store.get(thread_id)
            if thread_data is not None and checkpoint_id in thread_data:
                del thread_data[checkpoint_id]
                logger.debug(
                    "Checkpoint supprimé : thread=%s, id=%s",
                    thread_id,
                    checkpoint_id,
                )


class SQLiteCheckpointer:
    """Checkpointer persistant basé sur SQLite.

    Stocke les checkpoints dans une base SQLite pour une persistance
    fiable entre les redémarrages du processus. Thread-safe via un
    verrou interne.

    Paramètres
    ----------
    db_path : str
        Chemin vers le fichier de base de données SQLite. Utilisez
        ``":memory:"`` pour une base en mémoire (utile pour les tests).

    Attributs
    ---------
    _db_path : str
        Chemin vers la base SQLite.
    _lock : threading.Lock
        Verrou pour la sécurité multi-thread (SQLite en mode WAL).
    """

    def __init__(self, db_path: str = "checkpoints.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialise le schéma de la base de données SQLite."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        thread_id   TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        state       TEXT NOT NULL,
                        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                        PRIMARY KEY (thread_id, checkpoint_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
                    ON checkpoints (thread_id, created_at)
                    """
                )
                conn.commit()
            finally:
                conn.close()
        logger.debug("Base de checkpoints initialisée : %s", self._db_path)

    def save(
        self, thread_id: str, checkpoint_id: str, state: dict[str, Any]
    ) -> None:
        """Sauvegarde un checkpoint dans SQLite.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant unique du checkpoint.
        state : dict[str, Any]
            État complet à sauvegarder (sérialisé en JSON).
        """
        state_json = json.dumps(state, ensure_ascii=False, default=str)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_id, state, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (thread_id, checkpoint_id, state_json),
                )
                conn.commit()
            finally:
                conn.close()
        logger.debug(
            "Checkpoint SQLite sauvegardé : thread=%s, id=%s",
            thread_id,
            checkpoint_id,
        )

    def load(
        self, thread_id: str, checkpoint_id: str
    ) -> Optional[dict[str, Any]]:
        """Charge un checkpoint depuis SQLite.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à charger.

        Retourne
        --------
        dict[str, Any] | None
            L'état désérialisé, ou ``None`` si le checkpoint n'existe pas.
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute(
                    """
                    SELECT state FROM checkpoints
                    WHERE thread_id = ? AND checkpoint_id = ?
                    """,
                    (thread_id, checkpoint_id),
                )
                row = cursor.fetchone()
            finally:
                conn.close()

        if row is None:
            return None
        return json.loads(row[0])

    def list_checkpoints(self, thread_id: str) -> list[str]:
        """Liste les identifiants de checkpoints pour un thread.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.

        Retourne
        --------
        list[str]
            Liste ordonnée par date de création (du plus ancien au plus
            récent) des identifiants de checkpoints.
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute(
                    """
                    SELECT checkpoint_id FROM checkpoints
                    WHERE thread_id = ?
                    ORDER BY created_at ASC
                    """,
                    (thread_id,),
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

        return [row[0] for row in rows]

    def delete(self, thread_id: str, checkpoint_id: str) -> None:
        """Supprime un checkpoint de SQLite.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread d'exécution.
        checkpoint_id : str
            Identifiant du checkpoint à supprimer.
        """
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    """
                    DELETE FROM checkpoints
                    WHERE thread_id = ? AND checkpoint_id = ?
                    """,
                    (thread_id, checkpoint_id),
                )
                conn.commit()
            finally:
                conn.close()
        logger.debug(
            "Checkpoint SQLite supprimé : thread=%s, id=%s",
            thread_id,
            checkpoint_id,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Graphe d'état
# ══════════════════════════════════════════════════════════════════════════════

# Constantes spéciales pour le graphe
_END = "__end__"
_START = "__start__"


class StateGraph:
    """Graphe d'état dirigé avec support des cycles et du typage.

    Ce graphe permet de définir le flux d'exécution d'un agent sous
    forme de nœuds (fonctions) connectés par des arêtes (flux de
    contrôle). Il supporte les cycles (pour les boucles de
    réessai/auto-correction), les arêtes conditionnelles, et la
    composition hiérarchique via des sous-graphes.

    Paramètres
    ----------
    state_schema : Type[TypedDict]
        Type TypedDict définissant la structure de l'état partagé.
    reducers : dict[str, StateReducer] | None
        Mapping optionnel entre les clés d'état et leurs réducteurs.
        Si aucun réducteur n'est spécifié pour une clé, le
        comportement par défaut est de remplacer la valeur
        (équivalent à :data:`last_value`).

    Exemple
    -------
    >>> from typing import TypedDict, Annotated
    >>> class MyState(TypedDict):
    ...     count: int
    ...     items: list
    >>> graph = StateGraph(
    ...     MyState,
    ...     reducers={"items": append_list},
    ... )
    """

    def __init__(
        self,
        state_schema: Type,  # Type[TypedDict] — évité pour compat runtime
        reducers: Optional[dict[str, Any]] = None,
    ) -> None:
        self._state_schema = state_schema
        self._reducers: dict[str, Any] = dict(reducers) if reducers else {}
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._conditional_edges: list[ConditionalEdge] = []
        self._entry_point: Optional[str] = None
        self._finish_points: set[str] = set()
        self._subgraphs: dict[str, "StateGraph"] = {}

    # ── Construction du graphe ────────────────────────────────────────────

    def add_node(
        self,
        name: str,
        fn: Callable[..., Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> "StateGraph":
        """Ajoute un nœud au graphe.

        Paramètres
        ----------
        name : str
            Nom unique du nœud.
        fn : Callable
            Fonction d'exécution. Prend l'état courant (dict) et
            retourne un dict de mises à jour partielles ou un
            :class:`NodeResult`.
        metadata : dict[str, Any] | None
            Métadonnées optionnelles associées au nœud.

        Retourne
        --------
        StateGraph
            Self, pour允许 le chaînage des appels.

        Lève
        ------
        GraphError
            Si un nœud avec le même nom existe déjà.
        """
        if name in self._nodes:
            raise GraphError(f"Un nœud nommé « {name} » existe déjà.")
        if name in (_END, _START):
            raise GraphError(
                f"Le nom « {name} » est réservé et ne peut pas être "
                f"utilisé comme nom de nœud."
            )
        self._nodes[name] = GraphNode(
            name=name,
            fn=fn,
            metadata=metadata or {},
        )
        logger.debug("Nœud ajouté : %s", name)
        return self

    def add_edge(self, from_node: str, to_node: str) -> "StateGraph":
        """Ajoute une arête orientée statique entre deux nœuds.

        Paramètres
        ----------
        from_node : str
            Nom du nœud source.
        to_node : str
            Nom du nœud cible (``__end__`` pour terminer l'exécution).

        Retourne
        --------
        StateGraph
            Self, pour le chaînage des appels.

        Lève
        ------
        GraphError
            Si un nœud source a déjà une arête sortante statique ou
            conditionnelle (un nœud ne peut avoir qu'un seul type de
            sortie).
        """
        # Vérifier qu'un nœud n'a pas déjà de sortie statique
        for edge in self._edges:
            if edge.from_node == from_node:
                raise GraphError(
                    f"Le nœud « {from_node} » a déjà une arête sortante "
                    f"vers « {edge.to_node} ». Utilisez "
                    f"add_conditional_edges pour le routage multiple."
                )
        # Vérifier qu'un nœud n'a pas déjà de sortie conditionnelle
        for cedge in self._conditional_edges:
            if cedge.from_node == from_node:
                raise GraphError(
                    f"Le nœud « {from_node} » a déjà des arêtes "
                    f"conditionnelles. Impossible d'ajouter une arête "
                    f"statique."
                )
        self._edges.append(GraphEdge(from_node=from_node, to_node=to_node))
        logger.debug("Arête ajoutée : %s -> %s", from_node, to_node)
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        router_fn: Callable[..., str],
        targets: Optional[dict[str, str]] = None,
    ) -> "StateGraph":
        """Ajoute une arête conditionnelle depuis un nœud.

        La fonction de routage est appelée avec l'état courant après
        l'exécution du nœud source. La valeur retournée détermine le
        nœud cible à exécuter ensuite.

        Paramètres
        ----------
        from_node : str
            Nom du nœud source.
        router_fn : Callable
            Fonction prenant l'état courant et retournant une clé de
            *targets* (ou ``"__end__"`` pour terminer).
        targets : dict[str, str] | None
            Mapping optionnel entre les valeurs de retour du routeur
            et les noms de nœuds cibles. Si ``None``, les valeurs de
            retour du routeur sont utilisées directement comme noms
            de nœuds.

        Retourne
        --------
        StateGraph
            Self, pour le chaînage des appels.

        Lève
        ------
        GraphError
            Si le nœud source a déjà une arête sortante statique.
        """
        # Vérifier qu'un nœud n'a pas déjà de sortie statique
        for edge in self._edges:
            if edge.from_node == from_node:
                raise GraphError(
                    f"Le nœud « {from_node} » a déjà une arête statique "
                    f"vers « {edge.to_node} ». Impossible d'ajouter des "
                    f"arêtes conditionnelles."
                )
        self._conditional_edges.append(
            ConditionalEdge(
                from_node=from_node,
                router_fn=router_fn,
                targets=targets or {},
            )
        )
        logger.debug("Arêtes conditionnelles ajoutées depuis : %s", from_node)
        return self

    def add_subgraph(
        self,
        name: str,
        subgraph: "StateGraph",
        metadata: Optional[dict[str, Any]] = None,
    ) -> "StateGraph":
        """Ajoute un sous-graphe comme nœud du graphe courant.

        Le sous-graphe est compilé et exécuté comme un nœud unique.
        L'état est partagé entre le graphe parent et le sous-graphe.

        Paramètres
        ----------
        name : str
            Nom du nœud représentant le sous-graphe.
        subgraph : StateGraph
            Graphe à imbriquer.
        metadata : dict[str, Any] | None
            Métadonnées optionnelles.

        Retourne
        --------
        StateGraph
            Self, pour le chaînage des appels.
        """
        self._subgraphs[name] = subgraph

        # Wrapper le sous-graphe dans une fonction de nœud
        def _subgraph_node_fn(state: dict[str, Any]) -> dict[str, Any]:
            compiled = subgraph.compile()
            return compiled.invoke(state)

        self.add_node(name, _subgraph_node_fn, metadata=metadata)
        logger.debug("Sous-graphe ajouté : %s", name)
        return self

    def set_entry_point(self, node_name: str) -> "StateGraph":
        """Définit le point d'entrée du graphe.

        Paramètres
        ----------
        node_name : str
            Nom du nœud qui sera exécuté en premier.

        Retourne
        --------
        StateGraph
            Self, pour le chaînage des appels.

        Lève
        ------
        GraphError
            Si le nœud n'existe pas dans le graphe.
        """
        if node_name not in self._nodes:
            raise GraphError(
                f"Le nœud « {node_name} » n'existe pas dans le graphe."
            )
        self._entry_point = node_name
        logger.debug("Point d'entrée défini : %s", node_name)
        return self

    def set_finish_point(self, node_name: str) -> "StateGraph":
        """Définit un point de terminaison du graphe.

        Lorsque l'exécution atteint un nœud marqué comme point de
        terminaison, le graphe s'arrête même si le nœud a des arêtes
        sortantes.

        Paramètres
        ----------
        node_name : str
            Nom du nœud de terminaison.

        Retourne
        --------
        StateGraph
            Self, pour le chaînage des appels.

        Lève
        ------
        GraphError
            Si le nœud n'existe pas dans le graphe.
        """
        if node_name not in self._nodes:
            raise GraphError(
                f"Le nœud « {node_name} » n'existe pas dans le graphe."
            )
        self._finish_points.add(node_name)
        logger.debug("Point de terminaison défini : %s", node_name)
        return self

    # ── Compilation ───────────────────────────────────────────────────────

    def compile(
        self,
        checkpointer: Optional[Any] = None,
        interrupt_before: Optional[list[str]] = None,
        interrupt_after: Optional[list[str]] = None,
    ) -> "CompiledGraph":
        """Compile le graphe et retourne une version exécutable.

        La compilation valide la structure du graphe (point d'entrée,
        connexité, nœuds référencés) et construit les tables de routage
        internes pour une exécution efficace.

        Paramètres
        ----------
        checkpointer : CheckpointProtocol | None
            Checkpointer optionnel pour la sauvegarde/restauration de
            l'état après chaque étape.
        interrupt_before : list[str] | None
            Liste de nœuds avant lesquels l'exécution doit être
            interrompue (mode pas-à-pas). Requiert un checkpointer.
        interrupt_after : list[str] | None
            Liste de nœuds après lesquels l'exécution doit être
            interrompue. Requiert un checkpointer.

        Retourne
        --------
        CompiledGraph
            Graphe compilé prêt à l'exécution.

        Lève
        ------
        GraphCompileError
            Si la structure du graphe est invalide.
        """
        self._validate()

        interrupt_before_set = set(interrupt_before or [])
        interrupt_after_set = set(interrupt_after or [])

        if (interrupt_before_set or interrupt_after_set) and checkpointer is None:
            raise GraphCompileError(
                "Les interruptions (interrupt_before/interrupt_after) "
                "requièrent un checkpointer pour la persistance de l'état."
            )

        compiled = CompiledGraph(
            nodes=dict(self._nodes),
            edges=list(self._edges),
            conditional_edges=list(self._conditional_edges),
            entry_point=self._entry_point,
            finish_points=set(self._finish_points),
            state_schema=self._state_schema,
            reducers=dict(self._reducers),
            checkpointer=checkpointer,
            interrupt_before=interrupt_before_set,
            interrupt_after=interrupt_after_set,
        )
        logger.info("Graphe compilé avec succès (%d nœuds)", len(self._nodes))
        return compiled

    def _validate(self) -> None:
        """Valide la structure du graphe avant compilation.

        Lève
        ------
        GraphCompileError
            Si la structure est invalide.
        """
        if not self._nodes:
            raise GraphCompileError("Le graphe ne contient aucun nœud.")

        if self._entry_point is None:
            raise GraphCompileError(
                "Aucun point d'entrée défini. Utilisez set_entry_point()."
            )

        if self._entry_point not in self._nodes:
            raise GraphCompileError(
                f"Le point d'entrée « {self._entry_point} » n'existe pas "
                f"dans le graphe."
            )

        # Vérifier que toutes les arêtes référencent des nœuds existants
        node_names = set(self._nodes.keys()) | {_END}
        for edge in self._edges:
            if edge.from_node not in node_names and edge.from_node != _START:
                raise GraphCompileError(
                    f"Arête : le nœud source « {edge.from_node} » "
                    f"n'existe pas."
                )
            if edge.to_node not in node_names:
                raise GraphCompileError(
                    f"Arête : le nœud cible « {edge.to_node} » n'existe pas."
                )

        for cedge in self._conditional_edges:
            if cedge.from_node not in self._nodes:
                raise GraphCompileError(
                    f"Arête conditionnelle : le nœud source "
                    f"« {cedge.from_node} » n'existe pas."
                )
            for target_key, target_node in cedge.targets.items():
                if target_node not in node_names:
                    raise GraphCompileError(
                        f"Arête conditionnelle : la cible "
                        f"« {target_node} » (clé « {target_key} ») "
                        f"n'existe pas."
                    )


# ══════════════════════════════════════════════════════════════════════════════
#  Graphe compilé (exécutable)
# ══════════════════════════════════════════════════════════════════════════════


class CompiledGraph:
    """Graphe compilé prêt à l'exécution.

    Cette classe est retournée par :meth:`StateGraph.compile` et fournit
    les méthodes d'exécution synchrone (:meth:`invoke`) et en streaming
    (:meth:`stream`), ainsi que les méthodes de gestion de l'état
    (:meth:`get_state`, :meth:`update_state`, :meth:`get_state_history`).

    Attributs
    ---------
    nodes : dict[str, GraphNode]
        Nœuds du graphe indexés par nom.
    edges : list[GraphEdge]
        Arêtes statiques du graphe.
    conditional_edges : list[ConditionalEdge]
        Arêtes conditionnelles du graphe.
    entry_point : str | None
        Nom du nœud de point d'entrée.
    finish_points : set[str]
        Ensemble des nœuds de terminaison.
    state_schema : Type
        Schéma TypedDict de l'état.
    reducers : dict[str, StateReducer]
        Réducteurs pour les clés d'état.
    checkpointer : CheckpointProtocol | None
        Checkpointer pour la persistance.
    interrupt_before : set[str]
        Nœuds avant lesquels interrompre.
    interrupt_after : set[str]
        Nœuds après lesquels interrompre.
    """

    def __init__(
        self,
        nodes: dict[str, GraphNode],
        edges: list[GraphEdge],
        conditional_edges: list[ConditionalEdge],
        entry_point: Optional[str],
        finish_points: set[str],
        state_schema: Type,
        reducers: dict[str, Any],
        checkpointer: Optional[Any] = None,
        interrupt_before: Optional[set[str]] = None,
        interrupt_after: Optional[set[str]] = None,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point
        self.finish_points = finish_points
        self.state_schema = state_schema
        self.reducers = reducers
        self.checkpointer = checkpointer
        self.interrupt_before = interrupt_before or set()
        self.interrupt_after = interrupt_after or set()

        # Construction des tables de routage pour une exécution efficace
        self._static_routes: dict[str, str] = {}
        for edge in self.edges:
            self._static_routes[edge.from_node] = edge.to_node

        self._conditional_routes: dict[str, ConditionalEdge] = {}
        for cedge in self.conditional_edges:
            self._conditional_routes[cedge.from_node] = cedge

    # ── Exécution synchrone ───────────────────────────────────────────────

    def invoke(
        self,
        state: dict[str, Any],
        config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Exécute le graphe de manière synchrone et retourne l'état final.

        Paramètres
        ----------
        state : dict[str, Any]
            État initial du graphe.
        config : dict[str, Any] | None
            Configuration d'exécution optionnelle. Clés supportées :
            - ``thread_id`` (str) : identifiant de thread pour le
              checkpointing et la reprise.
            - ``max_steps`` (int) : nombre maximum d'étapes (défaut : 100).

        Retourne
        --------
        dict[str, Any]
            État final après exécution complète du graphe.

        Lève
        ------
        GraphExecutionError
            Si une erreur se produit pendant l'exécution d'un nœud.
        """
        config = config or {}
        thread_id = config.get("thread_id", str(uuid.uuid4()))
        max_steps = config.get("max_steps", 100)

        # Tenter de reprendre depuis un checkpoint existant
        current_state = self._try_resume(thread_id, state)

        current_node = self._determine_start_node(thread_id, current_state)
        step = 0

        while current_node is not None and current_node != _END and step < max_steps:
            # Vérifier l'interruption avant le nœud
            if current_node in self.interrupt_before:
                logger.info(
                    "Interruption avant le nœud : %s (thread=%s)",
                    current_node,
                    thread_id,
                )
                self._save_checkpoint(thread_id, current_state, current_node)
                break

            # Exécuter le nœud
            logger.debug("Exécution du nœud : %s (étape %d)", current_node, step)
            try:
                result = self._execute_node(current_node, current_state)
            except Exception as exc:
                raise GraphExecutionError(
                    f"Erreur dans le nœud « {current_node} » : {exc}"
                ) from exc

            # Appliquer les mises à jour à l'état
            current_state = self._apply_node_result(current_state, result)

            # Sauvegarder le checkpoint
            self._save_checkpoint(thread_id, current_state, current_node)

            step += 1

            # Vérifier le point de terminaison
            if current_node in self.finish_points:
                logger.debug(
                    "Point de terminaison atteint : %s", current_node
                )
                break

            # Vérifier l'interruption après le nœud
            if current_node in self.interrupt_after:
                logger.info(
                    "Interruption après le nœud : %s (thread=%s)",
                    current_node,
                    thread_id,
                )
                break

            # Déterminer le prochain nœud
            current_node = self._route(current_node, current_state)

        if step >= max_steps:
            logger.warning(
                "Nombre maximum d'étapes atteint (%d) pour thread=%s",
                max_steps,
                thread_id,
            )

        return current_state

    # ── Exécution en streaming ────────────────────────────────────────────

    def stream(
        self,
        state: dict[str, Any],
        config: Optional[dict[str, Any]] = None,
    ) -> Iterator[StreamEvent]:
        """Exécute le graphe en mode streaming.

        Émet des :class:`StreamEvent` au fur et à mesure de l'exécution
        de chaque nœud, permettant un suivi en temps réel.

        Paramètres
        ----------
        state : dict[str, Any]
            État initial du graphe.
        config : dict[str, Any] | None
            Configuration d'exécution (cf. :meth:`invoke`).

        Retourne
        --------
        Iterator[StreamEvent]
            Itérateur sur les événements de streaming.
        """
        config = config or {}
        thread_id = config.get("thread_id", str(uuid.uuid4()))
        max_steps = config.get("max_steps", 100)

        current_state = self._try_resume(thread_id, state)
        current_node = self._determine_start_node(thread_id, current_state)
        step = 0

        while current_node is not None and current_node != _END and step < max_steps:
            # Vérifier l'interruption avant le nœud
            if current_node in self.interrupt_before:
                yield StreamEvent(
                    type=StreamEventType.CUSTOM,
                    node_name=current_node,
                    data={"event": "interrupt_before"},
                )
                self._save_checkpoint(thread_id, current_state, current_node)
                break

            # Émettre NODE_START
            yield StreamEvent(
                type=StreamEventType.NODE_START,
                node_name=current_node,
                data={"step": step, "state_keys": list(current_state.keys())},
            )

            # Exécuter le nœud
            try:
                result = self._execute_node(current_node, current_state)
            except Exception as exc:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    node_name=current_node,
                    data={"error": str(exc), "error_type": type(exc).__name__},
                )
                self._save_checkpoint(thread_id, current_state, current_node)
                break

            # Si le nœud retourne un générateur, streamer les tokens
            if isinstance(result.output, dict) and "__stream__" in result.output:
                stream_iter = result.output["__stream__"]
                for chunk in stream_iter:
                    yield StreamEvent(
                        type=StreamEventType.TOKEN,
                        node_name=current_node,
                        data=chunk,
                    )
                # Retirer la clé technique du résultat
                result.output = {
                    k: v for k, v in result.output.items() if k != "__stream__"
                }

            # Appliquer les mises à jour
            current_state = self._apply_node_result(current_state, result)

            # Sauvegarder le checkpoint
            self._save_checkpoint(thread_id, current_state, current_node)

            # Émettre NODE_END
            yield StreamEvent(
                type=StreamEventType.NODE_END,
                node_name=current_node,
                data={"output_keys": list(result.output.keys())},
            )

            step += 1

            # Vérifier le point de terminaison
            if current_node in self.finish_points:
                yield StreamEvent(
                    type=StreamEventType.CUSTOM,
                    node_name=current_node,
                    data={"event": "finish_point"},
                )
                break

            # Vérifier l'interruption après le nœud
            if current_node in self.interrupt_after:
                yield StreamEvent(
                    type=StreamEventType.CUSTOM,
                    node_name=current_node,
                    data={"event": "interrupt_after"},
                )
                break

            # Déterminer le prochain nœud
            current_node = self._route(current_node, current_state)

        if step >= max_steps:
            yield StreamEvent(
                type=StreamEventType.CUSTOM,
                node_name="__system__",
                data={"event": "max_steps_reached", "max_steps": max_steps},
            )

    # ── Gestion de l'état ────────────────────────────────────────────────

    def get_state(self, thread_id: str) -> Optional[dict[str, Any]]:
        """Récupère l'état le plus récent pour un thread.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.

        Retourne
        --------
        dict[str, Any] | None
            État le plus récent, ou ``None`` si aucun checkpoint n'existe.
        """
        if self.checkpointer is None:
            return None
        checkpoints = self.checkpointer.list_checkpoints(thread_id)
        if not checkpoints:
            return None
        last_checkpoint_id = checkpoints[-1]
        return self.checkpointer.load(thread_id, last_checkpoint_id)

    def update_state(self, thread_id: str, values: dict[str, Any]) -> None:
        """Met à jour l'état d'un thread avec les valeurs fournies.

        Applique les réducteurs aux nouvelles valeurs et sauvegarde un
        nouveau checkpoint.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.
        values : dict[str, Any]
            Valeurs de mise à jour partielles.
        """
        if self.checkpointer is None:
            raise GraphError(
                "Un checkpointer est requis pour mettre à jour l'état."
            )
        current = self.get_state(thread_id) or {}
        updated = self._apply_updates(current, values)
        checkpoint_id = str(uuid.uuid4())
        self.checkpointer.save(thread_id, checkpoint_id, updated)
        logger.debug("État mis à jour pour thread=%s", thread_id)

    def get_state_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Récupère l'historique complet des états pour un thread.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.

        Retourne
        --------
        list[dict[str, Any]]
            Liste ordonnée de tous les checkpoints (du plus ancien au
            plus récent).
        """
        if self.checkpointer is None:
            return []
        checkpoints = self.checkpointer.list_checkpoints(thread_id)
        history: list[dict[str, Any]] = []
        for cp_id in checkpoints:
            state = self.checkpointer.load(thread_id, cp_id)
            if state is not None:
                history.append(state)
        return history

    # ── Méthodes internes ─────────────────────────────────────────────────

    def _try_resume(
        self, thread_id: str, initial_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Tente de reprendre l'exécution depuis le dernier checkpoint.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.
        initial_state : dict[str, Any]
            État initial fourni par l'appelant.

        Retourne
        --------
        dict[str, Any]
            État de départ pour l'exécution (checkpoint ou état initial).
        """
        if self.checkpointer is None:
            return dict(initial_state)
        checkpoints = self.checkpointer.list_checkpoints(thread_id)
        if checkpoints:
            last_id = checkpoints[-1]
            saved = self.checkpointer.load(thread_id, last_id)
            if saved is not None:
                logger.debug(
                    "Reprise depuis le checkpoint : thread=%s, id=%s",
                    thread_id,
                    last_id,
                )
                return saved
        return dict(initial_state)

    def _determine_start_node(
        self, thread_id: str, current_state: dict[str, Any]
    ) -> Optional[str]:
        """Détermine le nœud de départ pour l'exécution.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.
        current_state : dict[str, Any]
            État courant.

        Retourne
        --------
        str | None
            Nom du nœud de départ, ou ``None`` si le graphe est terminé.
        """
        # Vérifier si l'état contient un marqueur de nœud en cours
        pending_node = current_state.get("__pending_node__")
        if pending_node and pending_node in self.nodes:
            return pending_node
        return self.entry_point

    def _execute_node(
        self, node_name: str, state: dict[str, Any]
    ) -> NodeResult:
        """Exécute un nœud individuel et retourne le résultat.

        Paramètres
        ----------
        node_name : str
            Nom du nœud à exécuter.
        state : dict[str, Any]
            État courant passé au nœud.

        Retourne
        --------
        NodeResult
            Résultat de l'exécution du nœud.

        Lève
        ------
        GraphExecutionError
            Si le nœud n'existe pas.
        """
        node = self.nodes.get(node_name)
        if node is None:
            raise GraphExecutionError(
                f"Le nœud « {node_name} » n'existe pas dans le graphe compilé."
            )

        # Passer une copie de l'état pour éviter les mutations accidentelles
        state_copy = copy.deepcopy(state)
        # Retirer les clés internes avant de passer au nœud
        internal_keys = {"__pending_node__"}
        for key in internal_keys:
            state_copy.pop(key, None)

        raw_result = node.fn(state_copy)

        if isinstance(raw_result, NodeResult):
            return raw_result
        if isinstance(raw_result, dict):
            return NodeResult(output=raw_result)

        # Si le nœud retourne None, pas de mise à jour
        if raw_result is None:
            return NodeResult(output={})

        raise GraphExecutionError(
            f"Le nœud « {node_name} » a retourné un type inattendu : "
            f"{type(raw_result).__name__}. Attendu : dict ou NodeResult."
        )

    def _apply_node_result(
        self, state: dict[str, Any], result: NodeResult
    ) -> dict[str, Any]:
        """Applique le résultat d'un nœud à l'état courant.

        Paramètres
        ----------
        state : dict[str, Any]
            État courant.
        result : NodeResult
            Résultat du nœud.

        Retourne
        --------
        dict[str, Any]
            Nouvel état après application des mises à jour.
        """
        return self._apply_updates(state, result.output)

    def _apply_updates(
        self, state: dict[str, Any], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Applique des mises à jour partielles à l'état en utilisant les réducteurs.

        Paramètres
        ----------
        state : dict[str, Any]
            État courant.
        updates : dict[str, Any]
            Mises à jour partielles à appliquer.

        Retourne
        --------
        dict[str, Any]
            Nouvel état après application des réducteurs.
        """
        new_state = dict(state)
        for key, value in updates.items():
            if key.startswith("__"):
                # Clés internes — ne pas traiter avec les réducteurs
                new_state[key] = value
                continue
            reducer = self.reducers.get(key)
            if reducer is not None:
                try:
                    new_state[key] = reducer.reduce(new_state.get(key), value)
                except Exception as exc:
                    logger.warning(
                        "Erreur du réducteur pour la clé « %s » : %s",
                        key,
                        exc,
                    )
                    new_state[key] = value
            else:
                # Pas de réducteur → comportement par défaut (remplacement)
                new_state[key] = value
        return new_state

    def _route(
        self, current_node: str, state: dict[str, Any]
    ) -> Optional[str]:
        """Détermine le prochain nœud à exécuter.

        Paramètres
        ----------
        current_node : str
            Nom du nœud qui vient de s'exécuter.
        state : dict[str, Any]
            État courant.

        Retourne
        --------
        str | None
            Nom du prochain nœud, ou ``None`` / ``__end__`` si terminé.
        """
        # Vérifier d'abord les arêtes conditionnelles
        cedge = self._conditional_routes.get(current_node)
        if cedge is not None:
            # Passer une copie sans clés internes au routeur
            clean_state = {
                k: v for k, v in state.items() if not k.startswith("__")
            }
            route_key = cedge.router_fn(clean_state)
            if cedge.targets:
                next_node = cedge.targets.get(route_key, _END)
            else:
                next_node = route_key

            logger.debug(
                "Routage conditionnel depuis « %s » : clé=%s, cible=%s",
                current_node,
                route_key,
                next_node,
            )
            return next_node

        # Vérifier les arêtes statiques
        next_node = self._static_routes.get(current_node)
        if next_node is not None:
            return next_node

        # Pas de sortie → fin de l'exécution
        return _END

    def _save_checkpoint(
        self,
        thread_id: str,
        state: dict[str, Any],
        current_node: str,
    ) -> None:
        """Sauvegarde un checkpoint si un checkpointer est configuré.

        Paramètres
        ----------
        thread_id : str
            Identifiant du thread.
        state : dict[str, Any]
            État à sauvegarder.
        current_node : str
            Nom du nœud en cours (pour la reprise).
        """
        if self.checkpointer is None:
            return

        # Injecter le nœud en cours pour la reprise
        state_with_pending = dict(state)
        state_with_pending["__pending_node__"] = current_node

        checkpoint_id = str(uuid.uuid4())
        self.checkpointer.save(thread_id, checkpoint_id, state_with_pending)


# ══════════════════════════════════════════════════════════════════════════════
#  API publique
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "StateGraph",
    "GraphNode",
    "GraphEdge",
    "ConditionalEdge",
    "CompiledGraph",
    "StateReducer",
    "add_messages",
    "last_value",
    "append_list",
    "CheckpointProtocol",
    "MemoryCheckpointer",
    "SQLiteCheckpointer",
    "NodeResult",
    "StreamEvent",
    "StreamEventType",
    "GraphError",
    "GraphCompileError",
    "GraphExecutionError",
]

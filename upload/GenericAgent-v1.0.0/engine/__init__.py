"""GenericAgent v0.6.0 — Moteur d'exécution (inspiré de LangGraph).

Ce paquet fournit le moteur d'exécution basé sur un graphe d'état dirigé,
remplaçant la boucle agent simple par un graphe avec support des cycles,
du typage d'état avec réducteurs, du checkpointing, des arêtes conditionnelles,
de la composition de sous-graphes et du streaming.

Modules
-------
state_graph
    Implémentation principale de :class:`StateGraph`, :class:`CompiledGraph`,
    et toutes les classes utilitaires associées.
"""

from .state_graph import (
    StateGraph,
    GraphNode,
    GraphEdge,
    ConditionalEdge,
    CompiledGraph,
    StateReducer,
    add_messages,
    last_value,
    append_list,
    CheckpointProtocol,
    MemoryCheckpointer,
    SQLiteCheckpointer,
    NodeResult,
    StreamEvent,
    StreamEventType,
    GraphError,
    GraphCompileError,
    GraphExecutionError,
)

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

"""GenericAgent v0.6.0 — Flow : Serialisation JSON de graphes d'agents + Flow-as-MCP-Server.

Inspire de Langflow (langflow-ai/langflow).
Fournit la serialisation de graphes d'agents en JSON, leur execution,
et leur exposition comme serveurs MCP pour l'effet reseau.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from agentmain.safe_eval import SafeExpressionEvaluator, SecurityError

logger = logging.getLogger("ga.agentmain.flow")


# ══════════════════════════════════════════════════════════════════════════════
#  Noeuds et aretes de flow
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FlowNode:
    """Noeud dans un graphe de flow.

    Attributes:
        id: Identifiant unique du noeud
        type: Type du noeud (llm, tool, condition, input, output, subflow)
        name: Nom descriptif du noeud
        config: Configuration specifique au type de noeud
        position: Position dans l'editeur visuel (x, y)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "llm"
    name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    position: Tuple[int, int] = (0, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "type": self.type, "name": self.name,
            "config": self.config, "position": list(self.position),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowNode":
        pos = data.get("position", [0, 0])
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=data.get("type", "llm"),
            name=data.get("name", ""),
            config=data.get("config", {}),
            position=(pos[0], pos[1]) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else (0, 0),
        )


@dataclass
class FlowEdge:
    """Arete dans un graphe de flow.

    Attributes:
        id: Identifiant unique de l'arete
        source: ID du noeud source
        target: ID du noeud cible
        source_port: Port de sortie du noeud source
        target_port: Port d'entree du noeud cible
        condition: Condition optionnelle pour le routing conditionnel
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = ""
    target: str = ""
    source_port: str = "output"
    target_port: str = "input"
    condition: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"id": self.id, "source": self.source, "target": self.target,
             "source_port": self.source_port, "target_port": self.target_port}
        if self.condition:
            d["condition"] = self.condition
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowEdge":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            source=data.get("source", ""),
            target=data.get("target", ""),
            source_port=data.get("source_port", "output"),
            target_port=data.get("target_port", "input"),
            condition=data.get("condition"),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Flow — Graphe d'agents serialisable
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Flow:
    """Graphe d'agents serialisable en JSON.

    Represente un workflow complet d'agents avec des noeuds (etapes)
    et des aretes (flux de controle).

    Attributes:
        id: Identifiant unique du flow
        name: Nom du flow
        description: Description detaillee
        nodes: Liste des noeuds du graphe
        edges: Liste des aretes du graphe
        metadata: Metadonnees supplementaires
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "unnamed_flow"
    description: str = ""
    nodes: List[FlowNode] = field(default_factory=list)
    edges: List[FlowEdge] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize le flow en JSON."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, json_str: str) -> "Flow":
        """Deserialize depuis JSON."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Flow":
        """Deserialize depuis un dictionnaire."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "unnamed_flow"),
            description=data.get("description", ""),
            nodes=[FlowNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[FlowEdge.from_dict(e) for e in data.get("edges", [])],
            metadata=data.get("metadata", {}),
        )

    def validate(self) -> List[str]:
        """Valide l'integrite du flow.

        Returns:
            Liste d'erreurs (vide si valide)
        """
        errors: List[str] = []
        node_ids = {n.id for n in self.nodes}

        if not self.nodes:
            errors.append("Le flow ne contient aucun noeud")

        # Verifier les aretes
        for edge in self.edges:
            if edge.source not in node_ids:
                errors.append(f"Arete {edge.id} : source '{edge.source}' introuvable")
            if edge.target not in node_ids:
                errors.append(f"Arete {edge.id} : cible '{edge.target}' introuvable")

        # Verifier qu'il y a au moins un noeud d'entree
        input_nodes = [n for n in self.nodes if n.type == "input"]
        if not input_nodes:
            errors.append("Aucun noeud d'entree (type='input') trouve")

        # Verifier qu'il y a au moins un noeud de sortie
        output_nodes = [n for n in self.nodes if n.type == "output"]
        if not output_nodes:
            errors.append("Aucun noeud de sortie (type='output') trouve")

        # Verifier les cycles infinis (sans condition)
        if self._has_unconditional_cycle():
            errors.append("Cycle inconditionnel detecte (boucle infinie potentielle)")

        return errors

    def _has_unconditional_cycle(self) -> bool:
        """Detecte les cycles inconditionnels dans le graphe."""
        adj: Dict[str, List[str]] = {n.id: [] for n in self.nodes}
        for edge in self.edges:
            if edge.source in adj:
                adj[edge.source].append(edge.target)

        visited: set = set()
        rec_stack: set = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node_id in adj:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  FlowExecutor — Execution de flows
# ══════════════════════════════════════════════════════════════════════════════

class FlowExecutor:
    """Execute un flow etape par etape avec streaming.

    Supporte le routing conditionnel, le fan-out parallele, et
    la composition de sous-flows.
    """

    def __init__(self, llm_callback: Optional[Callable] = None) -> None:
        """Initialise l'executeur.

        Args:
            llm_callback: Fonction (prompt) -> str pour les noeuds LLM
        """
        self.llm_callback = llm_callback
        self._node_registry: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Enregistre les handlers par defaut pour chaque type de noeud."""
        self._node_registry = {
            "input": self._handle_input,
            "output": self._handle_output,
            "llm": self._handle_llm,
            "tool": self._handle_tool,
            "condition": self._handle_condition,
        }

    def register_node_handler(self, node_type: str, handler: Callable) -> None:
        """Enregistre un handler personnalise pour un type de noeud."""
        self._node_registry[node_type] = handler

    def execute_flow(self, flow: Flow, initial_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute un flow complet.

        Args:
            flow: Flow a executer
            initial_state: Etat initial du flow

        Returns:
            Resultat final avec trace d'execution
        """
        errors = flow.validate()
        if errors:
            return {"status": "error", "errors": errors}

        state = initial_state or {}
        state["_flow_id"] = flow.id
        state["_execution_trace"] = []

        # Trouver le noeud d'entree
        input_nodes = [n for n in flow.nodes if n.type == "input"]
        if not input_nodes:
            return {"status": "error", "errors": ["Aucun noeud d'entree"]}

        current_node_id = input_nodes[0].id
        visited_count: Dict[str, int] = {}
        max_visits = 50  # Prevention de boucle infinie

        try:
            while current_node_id:
                # Prevention de boucle infinie
                visited_count[current_node_id] = visited_count.get(current_node_id, 0) + 1
                if visited_count[current_node_id] > max_visits:
                    return {"status": "error", "errors": [f"Boucle infinie detectee au noeud {current_node_id}"]}

                # Trouver le noeud
                node = next((n for n in flow.nodes if n.id == current_node_id), None)
                if not node:
                    break

                # Executer le handler
                handler = self._node_registry.get(node.type, self._handle_default)
                node_result = handler(node, state)

                state["_execution_trace"].append({
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.type,
                    "result": str(node_result)[:500] if node_result else "",
                    "timestamp": time.monotonic(),
                })

                # Mettre a jour l'etat
                if isinstance(node_result, dict):
                    state.update(node_result)

                # Trouver le prochain noeud
                current_node_id = self._get_next_node(flow, current_node_id, state)

        except Exception as e:
            logger.error("Erreur execution flow : %s", e)
            return {"status": "error", "errors": [str(e)], "partial_state": state}

        return {"status": "success", "state": state}

    def stream_flow(self, flow: Flow, initial_state: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        """Execute un flow avec streaming d'evenements.

        Yields des evenements a chaque etape du flow.
        """
        errors = flow.validate()
        if errors:
            yield {"type": "error", "errors": errors}
            return

        state = initial_state or {}
        state["_flow_id"] = flow.id
        input_nodes = [n for n in flow.nodes if n.type == "input"]
        if not input_nodes:
            yield {"type": "error", "errors": ["Aucun noeud d'entree"]}
            return

        current_node_id = input_nodes[0].id

        while current_node_id:
            node = next((n for n in flow.nodes if n.id == current_node_id), None)
            if not node:
                break

            yield {"type": "node_start", "node_id": node.id, "node_name": node.name}

            handler = self._node_registry.get(node.type, self._handle_default)
            node_result = handler(node, state)

            if isinstance(node_result, dict):
                state.update(node_result)

            yield {"type": "node_end", "node_id": node.id, "result": str(node_result)[:500]}

            current_node_id = self._get_next_node(flow, current_node_id, state)

        yield {"type": "flow_end", "state": state}

    def _get_next_node(self, flow: Flow, current_id: str, state: Dict[str, Any]) -> Optional[str]:
        """Trouve le prochain noeud a executer."""
        outgoing = [e for e in flow.edges if e.source == current_id]
        if not outgoing:
            return None

        # Routing conditionnel — uses SafeExpressionEvaluator instead of eval()
        conditional = [e for e in outgoing if e.condition]
        if conditional:
            for edge in conditional:
                try:
                    if SafeExpressionEvaluator().evaluate(edge.condition, state):
                        return edge.target
                except (SecurityError, ValueError) as exc:
                    logger.warning(
                        "Security: blocked unsafe condition on edge %s: %s",
                        edge.id, exc,
                    )
                    continue
                except Exception:
                    logger.warning(
                        "Failed to evaluate condition on edge %s, skipping",
                        edge.id,
                    )
                    continue

        # Arete par defaut (premiere arete sans condition)
        default = [e for e in outgoing if not e.condition]
        if default:
            return default[0].target

        return None

    # ── Handlers de noeuds ───────────────────────────────────────────────

    def _handle_input(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"input_received": True}

    def _handle_output(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": state.get("last_result", ""), "done": True}

    def _handle_llm(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        prompt = node.config.get("prompt", "")
        if self.llm_callback:
            result = self.llm_callback(prompt)
        else:
            result = f"[LLM] {prompt}"
        return {"last_result": result}

    def _handle_tool(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = node.config.get("tool", "")
        args = node.config.get("args", {})
        return {"last_result": f"[Tool {tool_name}] args={args}"}

    def _handle_condition(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        condition = node.config.get("condition", "True")
        try:
            result = SafeExpressionEvaluator().evaluate(condition, state)
        except (SecurityError, ValueError) as exc:
            logger.warning(
                "Security: blocked unsafe condition on node %s: %s",
                node.id, exc,
            )
            result = False
        except Exception:
            logger.warning(
                "Failed to evaluate condition on node %s, defaulting to False",
                node.id,
            )
            result = False
        return {"condition_result": result}

    def _handle_default(self, node: FlowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"last_result": f"[{node.type}] {node.name}"}


# ══════════════════════════════════════════════════════════════════════════════
#  FlowMCPServer — Exposer un flow comme serveur MCP
# ══════════════════════════════════════════════════════════════════════════════

class FlowMCPServer:
    """Expose un Flow comme serveur MCP.

    Permet a n'importe quel flow d'etre consomme comme un outil MCP
    par d'autres agents, creant un effet reseau ou les agents
    auto-evolues peuvent s'enseigner mutuellement des competences.

    Utilisation ::
        flow = Flow(name="analyse_stock", ...)
        server = FlowMCPServer(flow, mcp_name="stock_analyzer")
        # Le flow est maintenant accessible comme outil MCP
    """

    def __init__(self, flow: Flow, mcp_name: str = "") -> None:
        """Initialise le serveur MCP pour le flow.

        Args:
            flow: Flow a exposer
            mcp_name: Nom du serveur MCP (defaut: nom du flow)
        """
        self.flow = flow
        self.mcp_name = mcp_name or flow.name
        self._executor = FlowExecutor()
        self._call_count = 0
        logger.info("FlowMCPServer cree : %s (flow: %s)", self.mcp_name, flow.name)

    def to_tool_schema(self) -> Dict[str, Any]:
        """Genere le schema d'outil MCP pour ce flow.

        Auto-detecte les entrees du flow (noeuds input) et les sorties (noeuds output).
        """
        input_nodes = [n for n in self.flow.nodes if n.type == "input"]
        properties: Dict[str, Any] = {}

        for node in input_nodes:
            config = node.config
            for key, value in config.items():
                properties[key] = {"type": "string", "description": f"Input: {key}"}

        return {
            "name": self.mcp_name,
            "description": self.flow.description or f"Flow : {self.flow.name}",
            "parameters": {
                "type": "object",
                "properties": properties if properties else {
                    "task": {"type": "string", "description": "Tache a executer"},
                },
                "required": list(properties.keys()) if properties else ["task"],
            },
        }

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute le flow avec les arguments donnes.

        Args:
            name: Nom de l'outil (doit correspondre au mcp_name)
            arguments: Arguments d'entree pour le flow

        Returns:
            Resultat de l'execution du flow
        """
        if name != self.mcp_name:
            return {"status": "error", "message": f"Outil inconnu : {name}"}

        self._call_count += 1
        logger.info("FlowMCPServer '%s' appele (appel #%d)", self.mcp_name, self._call_count)

        result = self._executor.execute_flow(self.flow, initial_state=arguments)
        return result

    def list_tools(self) -> List[Dict[str, Any]]:
        """Liste les outils MCP disponibles (le flow lui-meme)."""
        return [self.to_tool_schema()]

    def to_mcp_manifest(self) -> Dict[str, Any]:
        """Genere le manifeste MCP complet."""
        return {
            "name": self.mcp_name,
            "version": "1.0.0",
            "tools": self.list_tools(),
            "flow_id": self.flow.id,
        }

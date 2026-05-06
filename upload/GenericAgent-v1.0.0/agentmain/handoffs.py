"""GenericAgent v0.6.0 — Handoffs & Agent-as-Tool : Patterns de delegation multi-agent.

Inspire de l'OpenAI Agents SDK (openai/openai-agents-python).
Fournit Handoff (transfert de controle) et Agent-as-Tool (composition d'agents).
"""
from __future__ import annotations

import ast
import json
import logging
import os
import resource as _resource
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple, Union

logger = logging.getLogger("ga.agentmain.handoffs")


# ══════════════════════════════════════════════════════════════════════════════
#  Handoff — Transfert de controle entre agents
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Handoff:
    """Transfert de controle d'un agent a un autre.

    L'agent source transfere la conversation a l'agent cible (specialiste).
    Contrairement a Agent-as-Tool, le controle ne revient pas a l'agent source.

    Attributes:
        agent_name: Nom de l'agent cible
        description: Description de la capacite de l'agent cible
        transfer_fn: Fonction de transfert (state) -> dict, retourne l'etat initialise pour l'agent cible
    """
    agent_name: str
    description: str
    transfer_fn: Callable[[Dict[str, Any]], Dict[str, Any]]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute le transfert vers l'agent cible.

        Args:
            state: Etat actuel de la conversation

        Returns:
            Nouvel etat pour l'agent cible
        """
        logger.info("Handoff vers agent '%s'", self.agent_name)
        try:
            new_state = self.transfer_fn(state)
            new_state["_handoff_from"] = state.get("_current_agent", "unknown")
            new_state["_current_agent"] = self.agent_name
            return new_state
        except Exception as e:
            logger.error("Erreur handoff vers '%s' : %s", self.agent_name, e)
            raise


class AgentHandoff:
    """Gestionnaire de handoffs pour un agent.

    Enregistre les handoffs possibles et determine quand les declencher.
    """

    def __init__(self) -> None:
        self._handoffs: Dict[str, Handoff] = {}
        self._routing_fn: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None

    def register_handoff(self, agent_name: str, description: str,
                         transfer_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Enregistre un handoff possible.

        Args:
            agent_name: Nom de l'agent cible
            description: Description de la capacite de l'agent cible
            transfer_fn: Fonction de transfert (state) -> new_state
        """
        self._handoffs[agent_name] = Handoff(
            agent_name=agent_name,
            description=description,
            transfer_fn=transfer_fn,
        )
        logger.debug("Handoff enregistre : %s", agent_name)

    def set_routing_fn(self, fn: Callable[[Dict[str, Any]], Optional[str]]) -> None:
        """Definit la fonction de routage qui determine le handoff.

        La fonction recoit l'etat et retourne le nom de l'agent cible, ou None.
        """
        self._routing_fn = fn

    def should_handoff(self, state: Dict[str, Any]) -> Optional[Handoff]:
        """Determine si un handoff doit etre effectue.

        Args:
            state: Etat actuel de la conversation

        Returns:
            Le Handoff a effectuer, ou None
        """
        if self._routing_fn is None:
            return None
        try:
            target_name = self._routing_fn(state)
            if target_name and target_name in self._handoffs:
                return self._handoffs[target_name]
        except Exception as e:
            logger.error("Erreur routage handoff : %s", e)
        return None

    def execute_handoff(self, handoff: Handoff, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute un handoff.

        Args:
            handoff: Le handoff a executer
            state: Etat actuel

        Returns:
            Nouvel etat pour l'agent cible
        """
        return handoff.execute(state)

    def list_handoffs(self) -> List[Dict[str, str]]:
        """Liste les handoffs disponibles."""
        return [{"agent_name": h.agent_name, "description": h.description} for h in self._handoffs.values()]

    def to_tool_schema(self) -> Dict[str, Any]:
        """Genere le schema d'outil pour les handoffs (utilisable par le LLM)."""
        agent_options = list(self._handoffs.keys())
        return {
            "name": "handoff",
            "description": "Transfere la conversation a un agent specialiste",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": agent_options,
                        "description": "Nom de l'agent cible",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Raison du transfert",
                    },
                },
                "required": ["agent_name"],
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Agent-as-Tool — Composition d'agents
# ══════════════════════════════════════════════════════════════════════════════

class AgentAsTool:
    """Encapsule un agent comme un outil appelable par un autre agent.

    Contrairement au Handoff, le controle revient a l'agent appelant
    apres l'execution de l'agent outil (pattern manager).

    Utilisation ::
        sub_agent = GenericAgent(...)
        tool = AgentAsTool(sub_agent, "researcher", "Agent de recherche")
        result = tool({"query": "latest AI news"})
    """

    def __init__(self, agent: Any, tool_name: str, description: str = "") -> None:
        """Initialise l'agent comme outil.

        Args:
            agent: Instance de l'agent a encapsuler
            tool_name: Nom de l'outil
            description: Description de la capacite de l'agent
        """
        self.agent = agent
        self.tool_name = tool_name
        self.description = description
        self._call_count = 0

    def __call__(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute l'agent outil avec les arguments donnes.

        Args:
            arguments: Arguments passes a l'agent

        Returns:
            Resultat de l'execution de l'agent
        """
        self._call_count += 1
        logger.info("AgentAsTool '%s' appele (appel #%d)", self.tool_name, self._call_count)

        try:
            # Construire le prompt a partir des arguments
            prompt_parts = []
            for key, value in arguments.items():
                prompt_parts.append(f"{key}: {value}")
            prompt = "\n".join(prompt_parts)

            # Executer l'agent
            if hasattr(self.agent, "put_task"):
                queue = self.agent.put_task(prompt)
                results = []
                while True:
                    try:
                        item = queue.get(timeout=300)
                        if item.get("type") == "done":
                            break
                        results.append(item)
                    except Exception:
                        break
                return {"status": "success", "tool_name": self.tool_name, "results": results}
            else:
                return {"status": "error", "message": "Agent n'a pas de methode put_task"}

        except Exception as e:
            logger.error("Erreur AgentAsTool '%s' : %s", self.tool_name, e)
            return {"status": "error", "message": str(e)}

    def to_tool_schema(self) -> Dict[str, Any]:
        """Genere le schema d'outil pour l'agent."""
        return {
            "name": self.tool_name,
            "description": self.description or f"Agent specialiste : {self.tool_name}",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": f"Tache a confier a l'agent {self.tool_name}",
                    },
                },
                "required": ["task"],
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Sandbox — Execution isolee et securisee
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SandboxConfig:
    """Configuration de securite pour l'execution sandboxee.

    Definit les permissions et limites pour l'execution de code
    dans un environnement isole.

    Attributes:
        allowed_paths: Repertoires accessibles en lecture/ecriture
        allowed_commands: Commandes shell autorisees
        allowed_network: Domaines reseau autorises
        max_memory_mb: Limite memoire en MB
        timeout_seconds: Temps d'execution maximum
        allow_subprocess: Autorise les sous-processus
        allow_imports: Modules Python autorises (vide = tous)
    """
    allowed_paths: List[str] = field(default_factory=lambda: [tempfile.gettempdir()])
    allowed_commands: List[str] = field(default_factory=lambda: ["python3", "pip"])
    allowed_network: List[str] = field(default_factory=list)
    max_memory_mb: int = 512
    timeout_seconds: int = 60
    allow_subprocess: bool = False
    allow_imports: List[str] = field(default_factory=list)

    def validate(self, code_or_command: str) -> bool:
        """Valide si un code ou une commande respecte les restrictions de securite.

        Args:
            code_or_command: Code Python ou commande shell a verifier

        Returns:
            True si autorise, False sinon
        """
        # ── Expanded blocklist of dangerous patterns ────────────────────────
        # These patterns cover common Python sandbox escape vectors, dangerous
        # builtins, introspection dunder attributes, system calls, and network
        # access patterns.
        dangerous_patterns = [
            # Shell injection / destructive commands
            "rm ", "del ", "rmdir", "format ", "shutdown",
            # Dangerous builtins and dunder attributes
            "__builtins__", "__import__", "__class__", "__bases__",
            "__subclasses__", "__mro__",
            # Dangerous builtin functions
            "globals(", "locals(", "getattr(", "setattr(", "delattr(", "hasattr(",
            # Code execution / compilation
            "eval(", "exec(", "compile(",
            # File I/O and system access
            "open(", "write(",
            # OS-level command execution
            "os.system", "os.exec", "os.spawn", "os.popen",
            # Subprocess and shell utilities
            "subprocess", "shutil",
            # Resource limit manipulation (escape rlimit)
            "resource.setrlimit", "resource.getrlimit",
            # Dynamic loading / import manipulation
            "ctypes", "importlib", "sys.modules", "sys.path",
            # Network access
            "socket", "http", "urllib", "requests",
        ]
        code_lower = code_or_command.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                logger.warning("Pattern dangereux detecte : %s", pattern)
                return False

        # ── Pre-execution AST check: reject all import nodes ────────────────
        # Parse the code and walk the AST to detect any Import or ImportFrom
        # nodes. This catches obfuscated imports that the string-based
        # blocklist above might miss (e.g. dynamic import constructions).
        try:
            tree = ast.parse(code_or_command)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_name = ""
                    if isinstance(node, ast.ImportFrom) and node.module:
                        module_name = node.module
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name
                            break
                    logger.warning(
                        "Import AST node detecte (bloque) : module=%s",
                        module_name or "<unknown>",
                    )
                    return False
        except SyntaxError:
            # If the code is not valid Python syntax, it might be a shell
            # command — let the string-based checks above handle it.
            pass

        # Verifier les imports restreints (legacy, but AST check above is
        # more comprehensive and catches obfuscated imports)
        if self.allow_imports:
            import re as _re
            imports = _re.findall(r"(?:import|from)\s+(\w+)", code_or_command)
            for imp in imports:
                if imp not in self.allow_imports and imp not in ("os", "sys", "json", "math", "re", "datetime", "collections", "itertools"):
                    logger.warning("Import non autorise : %s", imp)
                    return False

        return True


class SandboxExecutor:
    """Execute code in a restricted environment.
    
    ⚠️  WARNING: This is NOT a real security boundary!
    This executor provides only basic sandboxing for TRUSTED code.
    For UNTRUSTED code execution, use Docker, nsjail, or Firecracker.
    
    The string-based blocklist is trivially bypassable via:
    - String concatenation: __import__('o'+'s').system('id')
    - Builtins recovery: [x for x in (1).__class__.__base__.__subclasses__() if 'wrap' in x.__name__]
    - And many other Python sandbox escape techniques
    """

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        """Initialise l'executeur avec la configuration de securite.

        Args:
            config: Configuration de sandbox (defaut si None)
        """
        self.config = config or SandboxConfig()

    def execute(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Execute du code dans un environnement isole.

        Args:
            code: Code a executer
            language: Langage du code ("python" ou "bash")

        Returns:
            Dict avec status, stdout, stderr, exit_code, duration_ms
        """
        # Validation pre-execution
        if not self.config.validate(code):
            return {
                "status": "blocked",
                "stdout": "",
                "stderr": "Code bloque par la politique de securite sandbox",
                "exit_code": -1,
                "duration_ms": 0,
            }

        import time
        start_time = time.monotonic()

        try:
            if language == "python":
                return self._execute_python(code, start_time)
            elif language == "bash":
                return self._execute_bash(code, start_time)
            else:
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"Langage non supporte : {language}",
                    "exit_code": -1,
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                }
        except Exception as e:
            return {
                "status": "error",
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": int((time.monotonic() - start_time) * 1000),
            }

    def _execute_python(self, code: str, start_time: float) -> Dict[str, Any]:
        """Execute du code Python en sous-processus isole.

        .. warning::

            This sandbox is NOT a real security boundary. The subprocess-based
            isolation with resource limits can be trivially escaped by any
            determined attacker. The string-based blocklist and AST check in
            ``SandboxConfig.validate()`` reduce the attack surface but are
            fundamentally insufficient for untrusted code.

            **For production use, you MUST use proper OS-level isolation**
            such as Docker containers, nsjail, Firecracker microVMs, or
            gVisor. See the deployment documentation for recommended
            sandboxing strategies.
        """
        import time

        # Ajouter les restrictions au debut du code
        # NOTE: __import__ = None prevents re-importing after `del resource`
        # but this is still just defense-in-depth, not a real sandbox.
        sandbox_header = (
            "import resource, sys\n"
            f"resource.setrlimit(resource.RLIMIT_AS, ({self.config.max_memory_mb * 1024 * 1024}, {self.config.max_memory_mb * 1024 * 1024}))\n"
            "del resource\n"
            "__import__ = None\n"  # Prevent re-importing to escape limits
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="ga_sandbox_") as f:
            f.write(sandbox_header + code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                cwd=tempfile.gettempdir(),
                env={k: v for k, v in os.environ.items()
                     if k not in ("GA_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                     and not (k.endswith("_API_KEY") or k.endswith("_SECRET")
                              or k.endswith("_TOKEN") or k.endswith("_PASSWORD"))},
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "status": "timeout",
                "stdout": "",
                "stderr": f"[TIMEOUT] Command exceeded {self.config.timeout_seconds}s limit",
                "exit_code": -1,
                "duration_ms": duration_ms,
            }
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _execute_bash(self, command: str, start_time: float, timeout: int = 30) -> Dict[str, Any]:
        """Execute a bash command with timeout."""
        import time

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
                env={k: v for k, v in os.environ.items()
                     if k not in ("GA_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                     and not (k.endswith("_API_KEY") or k.endswith("_SECRET")
                              or k.endswith("_TOKEN") or k.endswith("_PASSWORD"))},
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "status": "timeout",
                "stdout": "",
                "stderr": f"[TIMEOUT] Command exceeded {timeout}s limit",
                "exit_code": -1,
                "duration_ms": duration_ms,
            }

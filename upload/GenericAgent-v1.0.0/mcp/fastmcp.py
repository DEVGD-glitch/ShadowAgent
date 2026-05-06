"""GenericAgent v0.6.0 — FastMCP : API decorateur pour enregistrement zero-boilerplate des capacites MCP.

Inspire du MCP Python SDK (modelcontextprotocol/python-sdk).
Fournit @mcp.tool(), @mcp.resource(), @mcp.prompt() pour enregistrer
les capacites de l'agent sans configuration manuelle.
"""
from __future__ import annotations

import inspect
import json
import logging
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from collections import OrderedDict

logger = logging.getLogger("ga.mcp.fastmcp")

# ══════════════════════════════════════════════════════════════════════════════
#  Types et schemas
# ══════════════════════════════════════════════════════════════════════════════

_PYTHON_TYPE_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Convertit un type Python en schema JSON basique."""
    if py_type in _PYTHON_TYPE_TO_JSON:
        return {"type": _PYTHON_TYPE_TO_JSON[py_type]}
    origin = getattr(py_type, "__origin__", None)
    if origin is list:
        args = getattr(py_type, "__args__", (Any,))
        return {"type": "array", "items": _python_type_to_json_schema(args[0]) if args else {}}
    if origin is dict:
        return {"type": "object"}
    if py_type is Any:
        return {}
    return {"type": "string"}


def _generate_tool_schema(fn: Callable, name: Optional[str] = None) -> Dict[str, Any]:
    """Genere automatiquement un schema JSON a partir des type hints d'une fonction."""
    sig = inspect.signature(fn)
    func_name = name or fn.__name__
    description = inspect.getdoc(fn) or f"Outil {func_name}"
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "args", "kwargs"):
            continue
        param_type = param.annotation if param.annotation is not inspect.Parameter.empty else str
        schema = _python_type_to_json_schema(param_type)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
            schema["description"] = f"Parametre {param_name}"
        else:
            schema["description"] = f"Parametre {param_name} (defaut: {param.default})"
            schema["default"] = param.default
        properties[param_name] = schema

    return {
        "name": func_name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Enregistrements de capacites
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolRegistration:
    """Enregistrement d'un outil MCP."""
    name: str
    fn: Callable
    schema: Dict[str, Any]
    description: str = ""


@dataclass
class ResourceRegistration:
    """Enregistrement d'une ressource MCP."""
    uri_template: str
    fn: Callable
    name: str = ""
    description: str = ""
    mime_type: str = "text/plain"


@dataclass
class PromptRegistration:
    """Enregistrement d'un prompt MCP."""
    name: str
    fn: Callable
    schema: Dict[str, Any]
    description: str = ""


# ══════════════════════════════════════════════════════════════════════════════
#  FastMCP — API decorateur principale
# ══════════════════════════════════════════════════════════════════════════════

class FastMCP:
    """API decorateur pour enregistrement zero-boilerplate des capacites MCP.

    Utilisation ::
        mcp = FastMCP("genericagent")

        @mcp.tool()
        def search_web(query: str, num_results: int = 10) -> str:
            \"\"\"Recherche web.\"\"\"
            return do_search(query, num_results)

        @mcp.resource("memory://{domain}/insights")
        def get_domain_insights(domain: str) -> str:
            return load_insights(domain)

        @mcp.prompt()
        def code_review(code: str, language: str = "python") -> str:
            return f"Review this {language} code:\\n{code}"
    """

    def __init__(self, name: str, version: str = "1.0.0") -> None:
        self.name = name
        self.version = version
        self._tools: OrderedDict[str, ToolRegistration] = OrderedDict()
        self._resources: OrderedDict[str, ResourceRegistration] = OrderedDict()
        self._prompts: OrderedDict[str, PromptRegistration] = OrderedDict()
        logger.info("FastMCP '%s' v%s initialise", name, version)

    # ── Decorateurs ──────────────────────────────────────────────────────

    def tool(self, name: Optional[str] = None, description: Optional[str] = None) -> Callable:
        """Decorateur pour enregistrer une fonction comme outil MCP.

        Le schema JSON est genere automatiquement a partir des type hints.
        """
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            schema = _generate_tool_schema(fn, tool_name)
            if description:
                schema["description"] = description
            self._tools[tool_name] = ToolRegistration(
                name=tool_name,
                fn=fn,
                schema=schema,
                description=description or schema.get("description", ""),
            )
            logger.debug("Outil MCP enregistre : %s", tool_name)
            return fn
        return decorator

    def resource(self, uri_template: str, name: Optional[str] = None,
                 description: str = "", mime_type: str = "text/plain") -> Callable:
        """Decorateur pour enregistrer une source de donnees MCP.

        Args:
            uri_template: Modele URI avec variables (ex: "memory://{domain}/insights")
        """
        def decorator(fn: Callable) -> Callable:
            res_name = name or fn.__name__
            self._resources[res_name] = ResourceRegistration(
                uri_template=uri_template,
                fn=fn,
                name=res_name,
                description=description or inspect.getdoc(fn) or "",
                mime_type=mime_type,
            )
            logger.debug("Ressource MCP enregistree : %s (%s)", res_name, uri_template)
            return fn
        return decorator

    def prompt(self, name: Optional[str] = None, description: Optional[str] = None) -> Callable:
        """Decorateur pour enregistrer un template de prompt MCP."""
        def decorator(fn: Callable) -> Callable:
            prompt_name = name or fn.__name__
            schema = _generate_tool_schema(fn, prompt_name)
            self._prompts[prompt_name] = PromptRegistration(
                name=prompt_name,
                fn=fn,
                schema=schema,
                description=description or inspect.getdoc(fn) or "",
            )
            logger.debug("Prompt MCP enregistre : %s", prompt_name)
            return fn
        return decorator

    # ── Listage des capacites ────────────────────────────────────────────

    def list_tools(self) -> List[Dict[str, Any]]:
        """Retourne les schemas de tous les outils enregistres."""
        return [reg.schema for reg in self._tools.values()]

    def list_resources(self) -> List[Dict[str, Any]]:
        """Retourne les schemas de toutes les ressources enregistrees."""
        return [
            {
                "uri": reg.uri_template,
                "name": reg.name,
                "description": reg.description,
                "mimeType": reg.mime_type,
            }
            for reg in self._resources.values()
        ]

    def list_prompts(self) -> List[Dict[str, Any]]:
        """Retourne les schemas de tous les prompts enregistres."""
        return [
            {
                "name": reg.name,
                "description": reg.description,
                "arguments": reg.schema.get("parameters", {}),
            }
            for reg in self._prompts.values()
        ]

    # ── Execution des capacites ──────────────────────────────────────────

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Appelle un outil enregistre par son nom.

        Args:
            name: Nom de l'outil
            arguments: Arguments passes a la fonction

        Returns:
            Resultat de l'execution

        Raises:
            KeyError: Si l'outil n'existe pas
        """
        if name not in self._tools:
            raise KeyError(f"Outil MCP inconnu : {name}")
        reg = self._tools[name]
        try:
            result = reg.fn(**arguments)
            logger.debug("Outil %s execute avec succes", name)
            return result
        except Exception as e:
            logger.error("Erreur execution outil %s : %s", name, e)
            raise

    def read_resource(self, uri: str) -> str:
        """Lit une ressource enregistree par son URI.

        Supporte les templates URI avec variables (ex: memory://{domain}/insights).
        """
        for reg in self._resources.values():
            if self._uri_matches(reg.uri_template, uri):
                params = self._extract_uri_params(reg.uri_template, uri)
                try:
                    result = reg.fn(**params)
                    logger.debug("Ressource lue : %s", uri)
                    return result
                except Exception as e:
                    logger.error("Erreur lecture ressource %s : %s", uri, e)
                    raise
        raise KeyError(f"Aucune ressource MCP pour l'URI : {uri}")

    def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Recupere un prompt enregistre par son nom.

        Args:
            name: Nom du prompt
            arguments: Arguments pour parametriser le prompt

        Returns:
            Le texte du prompt genere
        """
        if name not in self._prompts:
            raise KeyError(f"Prompt MCP inconnu : {name}")
        reg = self._prompts[name]
        try:
            result = reg.fn(**(arguments or {}))
            logger.debug("Prompt %s genere avec succes", name)
            return result
        except Exception as e:
            logger.error("Erreur generation prompt %s : %s", name, e)
            raise

    # ── Helpers URI ──────────────────────────────────────────────────────

    @staticmethod
    def _uri_matches(template: str, uri: str) -> bool:
        """Verifie si une URI correspond a un template."""
        import re
        pattern = re.sub(r"\{(\w+)\}", r"[^/]+", template)
        return bool(re.fullmatch(pattern, uri))

    @staticmethod
    def _extract_uri_params(template: str, uri: str) -> Dict[str, str]:
        """Extrait les parametres d'une URI selon un template."""
        import re
        param_names = re.findall(r"\{(\w+)\}", template)
        pattern = re.sub(r"\{(\w+)\}", r"([^/]+)", template)
        match = re.fullmatch(pattern, uri)
        if not match:
            return {}
        return dict(zip(param_names, match.groups()))

    # ── Serveur MCP ──────────────────────────────────────────────────────

    def to_mcp_manifest(self) -> Dict[str, Any]:
        """Genere le manifeste MCP complet pour ce serveur."""
        return {
            "name": self.name,
            "version": self.version,
            "tools": self.list_tools(),
            "resources": self.list_resources(),
            "prompts": self.list_prompts(),
        }

    def serve_stdio(self) -> None:
        """Lance le serveur MCP en mode stdio (entree/sortie standard).

        Lit les requetes JSON-RPC sur stdin, ecrit les reponses sur stdout.
        """
        logger.info("FastMCP '%s' demarre en mode stdio", self.name)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self._handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                error_resp = {"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}, "id": None}
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error("Erreur traitement requete stdio : %s", e)

    def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Traite une requete JSON-RPC."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "tools/list":
            return {"jsonrpc": "2.0", "result": {"tools": self.list_tools()}, "id": req_id}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                result = self.call_tool(tool_name, arguments)
                return {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": str(result)}]}, "id": req_id}
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": req_id}
        elif method == "resources/list":
            return {"jsonrpc": "2.0", "result": {"resources": self.list_resources()}, "id": req_id}
        elif method == "resources/read":
            uri = params.get("uri", "")
            try:
                content = self.read_resource(uri)
                return {"jsonrpc": "2.0", "result": {"contents": [{"uri": uri, "text": content}]}, "id": req_id}
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": req_id}
        elif method == "prompts/list":
            return {"jsonrpc": "2.0", "result": {"prompts": self.list_prompts()}, "id": req_id}
        elif method == "prompts/get":
            prompt_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                text = self.get_prompt(prompt_name, arguments)
                return {"jsonrpc": "2.0", "result": {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}, "id": req_id}
            except Exception as e:
                return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": req_id}
        elif method == "initialize":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True, "listChanged": True},
                        "prompts": {"listChanged": True},
                    },
                    "serverInfo": {"name": self.name, "version": self.version},
                },
                "id": req_id,
            }
        else:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Methode inconnue : {method}"}, "id": req_id}


# ══════════════════════════════════════════════════════════════════════════════
#  Instance globale pour enregistrement facile
# ══════════════════════════════════════════════════════════════════════════════

_default_mcp: Optional[FastMCP] = None


def get_default_mcp() -> FastMCP:
    """Retourne l'instance FastMCP par defaut (creee si necessaire)."""
    global _default_mcp
    if _default_mcp is None:
        _default_mcp = FastMCP("genericagent")
    return _default_mcp


def tool(name: Optional[str] = None, description: Optional[str] = None) -> Callable:
    """Raccourci pour enregistrer un outil sur l'instance MCP par defaut."""
    return get_default_mcp().tool(name=name, description=description)


def resource(uri_template: str, **kwargs: Any) -> Callable:
    """Raccourci pour enregistrer une ressource sur l'instance MCP par defaut."""
    return get_default_mcp().resource(uri_template, **kwargs)


def prompt(name: Optional[str] = None, **kwargs: Any) -> Callable:
    """Raccourci pour enregistrer un prompt sur l'instance MCP par defaut."""
    return get_default_mcp().prompt(name=name, **kwargs)

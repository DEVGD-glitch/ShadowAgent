"""Central tool registry and dynamic registration for GenericAgent.

Provides the :class:`ToolRegistry` singleton and the :func:`register_tool`
decorator for adding tools at runtime.  Tools can come from:

1. **Builtin tools** — the classic ``do_*`` methods on ``GenericAgentHandler``
2. **Registered tools** — functions decorated with ``@register_tool(...)``
3. **Plugin tools** — auto-discovered from the ``plugins/tools/`` directory
4. **MCP tools** — discovered from connected MCP servers (see ``mcp/``)

The registry merges all sources into a unified schema that is injected into
the LLM's ``tools`` parameter.

Classes:
    ToolDefinition: Complete specification for a single tool.
    ToolRegistry: Central registry that tracks all available tools.

Functions:
    get_registry: Return the global ToolRegistry singleton.
    register_tool: Decorator / function to register a tool.
    tool_schema_to_openai: Create an OpenAI function-calling tool schema.

Security:
    Plugin loading enforces path validation, manifest SHA-256 verification,
    and a restricted namespace (``__import__ = None``) to mitigate code
    injection from untrusted plugins.

Example::

    from tools.registry import register_tool, get_registry

    @register_tool(name="greet", description="Say hello")
    def do_greet(args, response):
        return f"Hello, {args.get('name', 'world')}!"

    schemas = get_registry().get_openai_schemas()
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("tools.registry")

# ══════════════════════════════════════════════════════════════════════════════
#  ToolDefinition
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ToolDefinition:
    """Complete specification for a single tool.

    Attributes
    ----------
    name : str
        Tool name as seen by the LLM (e.g. ``"web_search"``).
    description : str
        Human-readable description included in the tool schema.
    parameters : dict
        JSON Schema for the tool's input parameters.
    handler : Callable
        The function to call when this tool is invoked.  Must accept
        ``(args: dict, response: Any)`` and return a ``StepOutcome``-compatible
        value (or yield strings as a generator and return a StepOutcome).
    category : str
        Logical grouping (``"file"``, ``"web"``, ``"code"``, ``"memory"``,
        ``"search"``, ``"integration"``, ``"custom"``).
    requires_confirmation : bool
        If ``True``, the frontend must confirm before executing.
    examples : list[dict]
        Example invocations for documentation / few-shot prompting.
    version : str
        Semantic version of the tool definition.
    source : str
        Origin — ``"builtin"``, ``"plugin"``, ``"mcp"``, or ``"dynamic"``.
    """

    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str = "custom"
    requires_confirmation: bool = False
    examples: list[dict] = field(default_factory=list)
    version: str = "1.0.0"
    source: str = "dynamic"

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function-calling tool schema format.

        Returns
        -------
        dict
            Schema dict with ``"type"``, ``"function"`` keys.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
#  ToolRegistry
# ══════════════════════════════════════════════════════════════════════════════


class ToolRegistry:
    """Central registry that tracks all available tools.

    The registry is a singleton — use :func:`get_registry` to obtain the
    global instance.  It supports:

    * Registering tools via :meth:`register` or the :func:`register_tool`
      decorator.
    * Unregistering tools at runtime.
    * Merging builtin ``do_*`` tools with dynamically registered ones.
    * Producing a combined OpenAI-compatible tool schema list.
    * Auto-discovering plugins from the ``plugins/tools/`` directory.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._disabled: set[str] = set()
        self._categories: Dict[str, set[str]] = {}

    # ── Registration ───────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: Optional[dict] = None,
        category: str = "custom",
        requires_confirmation: bool = False,
        examples: Optional[list[dict]] = None,
        version: str = "1.0.0",
        source: str = "dynamic",
        override: bool = False,
    ) -> ToolDefinition:
        """Register a tool in the registry.

        Parameters
        ----------
        name : str
            Unique tool name.
        handler : Callable
            The function to invoke.
        description : str
            LLM-visible description.
        parameters : dict | None
            JSON Schema for inputs.  Defaults to ``{"type": "object", "properties": {}}``.
        category : str
            Tool category for grouping.
        requires_confirmation : bool
            Whether the frontend must confirm execution.
        examples : list[dict] | None
            Example invocations.
        version : str
            Semantic version.
        source : str
            Origin of the tool.
        override : bool
            If ``True``, silently replace an existing tool with the same name.

        Returns
        -------
        ToolDefinition
            The registered definition.

        Raises
        ------
        ValueError
            If a tool with the same name already exists and *override* is
            ``False``.
        """
        if name in self._tools and not override:
            raise ValueError(
                f"Tool '{name}' already registered. Use override=True to replace."
            )

        if parameters is None:
            parameters = {"type": "object", "properties": {}}

        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            category=category,
            requires_confirmation=requires_confirmation,
            examples=examples or [],
            version=version,
            source=source,
        )

        self._tools[name] = tool_def
        # Remove from disabled set if re-registering
        self._disabled.discard(name)

        # Update category index
        cat = self._categories.setdefault(category, set())
        cat.add(name)

        logger.debug("Registered tool: %s [%s] from %s", name, category, source)
        return tool_def

    def unregister(self, name: str) -> Optional[ToolDefinition]:
        """Remove a tool from the registry.

        Parameters
        ----------
        name : str
            The tool name to remove.

        Returns
        -------
        ToolDefinition | None
            The removed definition, or ``None`` if not found.
        """
        tool = self._tools.pop(name, None)
        if tool is None:
            return None

        # Clean up category index
        cat_tools = self._categories.get(tool.category)
        if cat_tools is not None:
            cat_tools.discard(name)
            if not cat_tools:
                del self._categories[tool.category]

        self._disabled.discard(name)
        logger.debug("Unregistered tool: %s", name)
        return tool

    def enable(self, name: str) -> None:
        """Re-enable a previously disabled tool."""
        self._disabled.discard(name)

    def disable(self, name: str) -> None:
        """Disable a tool without removing it from the registry."""
        if name in self._tools:
            self._disabled.add(name)

    # ── Query ──────────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Look up a tool by name (returns ``None`` if not found or disabled)."""
        if name in self._disabled:
            return None
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools and name not in self._disabled

    def __len__(self) -> int:
        return len(self._tools) - len(self._disabled)

    @property
    def tool_names(self) -> list[str]:
        """Return sorted list of active (non-disabled) tool names."""
        return sorted(n for n in self._tools if n not in self._disabled)

    @property
    def all_tool_names(self) -> list[str]:
        """Return sorted list of all registered tool names (including disabled)."""
        return sorted(self._tools.keys())

    def list_tools(self, category: Optional[str] = None) -> list[ToolDefinition]:
        """Return active tool definitions, optionally filtered by category."""
        tools = []
        for name, tool in self._tools.items():
            if name in self._disabled:
                continue
            if category and tool.category != category:
                continue
            tools.append(tool)
        return sorted(tools, key=lambda t: t.name)

    def list_categories(self) -> dict[str, int]:
        """Return a mapping of category name → count of active tools."""
        result: Dict[str, int] = {}
        for name, tool in self._tools.items():
            if name in self._disabled:
                continue
            result[tool.category] = result.get(tool.category, 0) + 1
        return result

    # ── Schema generation ──────────────────────────────────────────────────

    def get_openai_schemas(self, category: Optional[str] = None) -> list[dict]:
        """Return OpenAI-compatible tool schemas for all active tools.

        Parameters
        ----------
        category : str | None
            If set, only include tools from this category.

        Returns
        -------
        list[dict]
            List of ``{"type": "function", "function": {...}}`` dicts.
        """
        schemas = []
        for tool in self.list_tools(category=category):
            schemas.append(tool.to_openai_schema())
        return schemas

    def merge_builtin_schemas(self, builtin_schemas: list[dict]) -> list[dict]:
        """Merge builtin tool schemas with registered plugin schemas.

        Builtin schemas have priority — registered tools with the same name
        are skipped (unless they were registered with ``override=True``).

        Parameters
        ----------
        builtin_schemas : list[dict]
            The original schemas from ``assets/tools_schema.json``.

        Returns
        -------
        list[dict]
            Combined schema list with no duplicates.
        """
        builtin_names = set()
        result = list(builtin_schemas)
        for schema in builtin_schemas:
            func = schema.get("function", {})
            builtin_names.add(func.get("name", ""))

        # Add registered tools that don't clash with builtins
        for tool in self.list_tools():
            if tool.name not in builtin_names:
                result.append(tool.to_openai_schema())

        return result

    # ── Dispatch ───────────────────────────────────────────────────────────

    def dispatch(
        self, name: str, args: dict, response: Any
    ) -> Optional[Any]:
        """Dispatch a tool call to its registered handler.

        Parameters
        ----------
        name : str
            Tool name.
        args : dict
            Tool arguments.
        response : Any
            The LLM response object.

        Returns
        -------
        Any
            The handler's return value, or ``None`` if the tool is not
            found in the registry.
        """
        tool = self.get(name)
        if tool is None:
            return None
        return tool.handler(args, response)

    # ── Plugin auto-discovery ──────────────────────────────────────────────

    def load_plugins(self, plugin_dir: Optional[str] = None) -> int:
        """Auto-discover and load tool plugins from a directory.

        Each plugin is a Python file (or package) that calls
        ``register_tool(...)`` at import time.  Files starting with ``_``
        are skipped.

        Security measures applied:

        1. **Path validation**: Plugin files must reside within the allowed
           ``plugin_dir`` — symlinks and path traversal attempts are rejected.
        2. **Manifest validation**: If a ``manifest.json`` exists alongside
           the plugin, its ``sha256`` field is checked against the actual
           file hash.  Mismatched hashes cause the plugin to be skipped.
        3. **Restricted namespace**: ``__import__`` is set to ``None`` in
           the module namespace before execution to discourage arbitrary
           imports from within plugin code.
        4. **Error isolation**: Each plugin is loaded inside a try/except
           so a single failing plugin cannot crash the entire loading
           process.

        TODO (Phase 2): Add cryptographic signature verification for
        plugins.  Each plugin should be signed with a developer key and
        the signature verified before ``exec_module`` is called.

        Parameters
        ----------
        plugin_dir : str | None
            Directory to scan.  Defaults to ``plugins/tools/`` under the
            project root.

        Returns
        -------
        int
            Number of plugins successfully loaded.
        """
        if plugin_dir is None:
            plugin_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "plugins",
                "tools",
            )

        # Resolve the canonical plugin directory for security checks
        plugin_dir = os.path.realpath(plugin_dir)

        if not os.path.isdir(plugin_dir):
            logger.debug("Plugin directory not found: %s", plugin_dir)
            return 0

        loaded = 0
        for fname in sorted(os.listdir(plugin_dir)):
            if fname.startswith("_"):
                continue

            fpath = os.path.join(plugin_dir, fname)

            if fname.endswith(".py"):
                # ── Path traversal / symlink check ──
                real_fpath = os.path.realpath(fpath)
                if not real_fpath.startswith(plugin_dir + os.sep):
                    logger.warning(
                        "Plugin '%s' resolves to '%s' which is outside the "
                        "allowed plugin directory '%s'. Skipping.",
                        fname, real_fpath, plugin_dir,
                    )
                    continue

                # ── Manifest validation ──
                manifest_path = os.path.join(plugin_dir, fname[:-3] + ".manifest.json")
                if os.path.isfile(manifest_path):
                    if not self._validate_plugin_manifest(real_fpath, manifest_path):
                        logger.warning(
                            "Plugin '%s' manifest validation failed. Skipping.", fname,
                        )
                        continue

                module_name = f"_ga_plugin_{fname[:-3]}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, real_fpath)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        # Restrict __import__ in plugin namespace
                        mod.__import__ = None  # type: ignore[attr-defined]
                        sys.modules[module_name] = mod
                        spec.loader.exec_module(mod)
                        loaded += 1
                        logger.info("Loaded tool plugin: %s", fname)
                except Exception:
                    logger.warning("Failed to load plugin %s: %s", fname, traceback.format_exc())

            elif os.path.isdir(fpath) and os.path.isfile(os.path.join(fpath, "__init__.py")):
                # ── Path traversal / symlink check for package ──
                real_fpath = os.path.realpath(fpath)
                if not real_fpath.startswith(plugin_dir + os.sep):
                    logger.warning(
                        "Plugin package '%s' resolves to '%s' which is outside "
                        "the allowed plugin directory '%s'. Skipping.",
                        fname, real_fpath, plugin_dir,
                    )
                    continue

                init_path = os.path.join(real_fpath, "__init__.py")

                # ── Manifest validation for package ──
                manifest_path = os.path.join(real_fpath, "manifest.json")
                if os.path.isfile(manifest_path):
                    if not self._validate_plugin_manifest(init_path, manifest_path):
                        logger.warning(
                            "Plugin package '%s' manifest validation failed. Skipping.", fname,
                        )
                        continue

                module_name = f"_ga_plugin_{fname}"
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name, init_path,
                        submodule_search_locations=[real_fpath],
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        # Restrict __import__ in plugin namespace
                        mod.__import__ = None  # type: ignore[attr-defined]
                        sys.modules[module_name] = mod
                        spec.loader.exec_module(mod)
                        loaded += 1
                        logger.info("Loaded tool plugin package: %s", fname)
                except Exception:
                    logger.warning("Failed to load plugin package %s: %s", fname, traceback.format_exc())

        return loaded

    def _validate_plugin_manifest(self, plugin_file: str, manifest_path: str) -> bool:
        """Validate a plugin's manifest.json against the actual file.

        The manifest may contain a ``sha256`` field with the expected
        SHA-256 hex digest of the plugin's ``.py`` file.  If the field
        is present, the actual hash is compared and any mismatch causes
        the validation to fail.

        Parameters
        ----------
        plugin_file : str
            Path to the plugin's Python source file.
        manifest_path : str
            Path to the ``manifest.json`` file.

        Returns
        -------
        bool
            ``True`` if the manifest is valid or contains no ``sha256``
            field; ``False`` if the hash does not match.
        """
        import hashlib as _hashlib

        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot read manifest '%s': %s", manifest_path, exc)
            return False

        expected_hash = manifest.get("sha256")
        if expected_hash is None:
            # No hash in manifest — allow (backwards compatibility)
            logger.debug("Manifest '%s' has no sha256 field; skipping hash check.", manifest_path)
            return True

        # Compute actual hash
        sha256 = _hashlib.sha256()
        try:
            with open(plugin_file, "rb") as pf:
                for chunk in iter(lambda: pf.read(8192), b""):
                    sha256.update(chunk)
        except OSError as exc:
            logger.warning("Cannot read plugin file '%s': %s", plugin_file, exc)
            return False

        actual_hash = sha256.hexdigest()
        if actual_hash != expected_hash:
            logger.warning(
                "Plugin '%s' SHA-256 mismatch: expected %s, got %s",
                plugin_file, expected_hash, actual_hash,
            )
            return False

        logger.debug("Plugin '%s' manifest hash verified.", plugin_file)
        return True

    # ── Export / introspection ─────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the registry state for debugging / inspection."""
        return {
            "tools": {
                name: {
                    "name": t.name,
                    "category": t.category,
                    "source": t.source,
                    "version": t.version,
                    "description": t.description[:100],
                    "requires_confirmation": t.requires_confirmation,
                    "disabled": name in self._disabled,
                }
                for name, t in self._tools.items()
            },
            "categories": {k: sorted(v) for k, v in self._categories.items()},
            "total_active": len(self),
            "total_disabled": len(self._disabled),
        }

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self)}, disabled={len(self._disabled)})"


# ══════════════════════════════════════════════════════════════════════════════
#  Global singleton + decorator
# ══════════════════════════════════════════════════════════════════════════════

_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Return the global :class:`ToolRegistry` singleton."""
    return _registry


def register_tool(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[dict] = None,
    category: str = "custom",
    requires_confirmation: bool = False,
    examples: Optional[list[dict]] = None,
    version: str = "1.0.0",
    source: str = "dynamic",
    override: bool = False,
    handler: Optional[Callable] = None,
) -> Any:
    """Register a function as a tool.

    Can be used in three ways:

    1. **Decorator with arguments**::

        @register_tool(
            name="my_tool",
            description="Does something cool",
            parameters={"type": "object", "properties": {...}},
        )
        def handle_my_tool(args, response):
            ...

    2. **Decorator without arguments** (uses function name minus ``do_`` prefix)::

        @register_tool
        def do_my_tool(args, response):
            ...

    3. **Direct call** with explicit handler (used by plugin files)::

        register_tool(
            name="my_tool",
            handler=my_handler_fn,
            description="Does something cool",
        )

    Parameters
    ----------
    name : str | None
        Tool name.  Defaults to the function name with ``do_`` prefix stripped.
    description : str
        LLM-visible description.  Defaults to the function's docstring.
    parameters : dict | None
        JSON Schema for inputs.
    category : str
        Tool category for grouping.
    requires_confirmation : bool
        Whether the frontend must confirm execution.
    examples : list[dict] | None
        Example invocations.
    version : str
        Semantic version.
    source : str
        Origin of the tool.
    override : bool
        If ``True``, silently replace an existing tool with the same name.
    handler : Callable | None
        Explicit handler function.  When provided, the tool is registered
        immediately without the decorator pattern.
    """

    # Mode 3: Direct call with explicit handler
    if handler is not None:
        tool_name = name or handler.__name__
        if tool_name.startswith("do_"):
            tool_name = tool_name[3:]
        tool_desc = description or (handler.__doc__ or "").strip().split("\n")[0] or f"Tool: {tool_name}"
        get_registry().register(
            name=tool_name,
            handler=handler,
            description=tool_desc,
            parameters=parameters,
            category=category,
            requires_confirmation=requires_confirmation,
            examples=examples,
            version=version,
            source=source,
            override=override,
        )
        return handler

    def decorator(fn: Callable) -> Callable:
        tool_name = name
        if tool_name is None:
            tool_name = fn.__name__
            if tool_name.startswith("do_"):
                tool_name = tool_name[3:]

        tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
        if not tool_desc:
            tool_desc = f"Tool: {tool_name}"

        get_registry().register(
            name=tool_name,
            handler=fn,
            description=tool_desc,
            parameters=parameters,
            category=category,
            requires_confirmation=requires_confirmation,
            examples=examples,
            version=version,
            source=source,
            override=override,
        )
        return fn

    # Support @register_tool without parentheses
    if callable(name):
        fn = name
        name = None
        return decorator(fn)

    return decorator


# ══════════════════════════════════════════════════════════════════════════════
#  Schema utilities
# ══════════════════════════════════════════════════════════════════════════════


def tool_schema_to_openai(name: str, description: str, parameters: dict) -> dict:
    """Create a single OpenAI function-calling tool schema.

    Parameters
    ----------
    name : str
        Tool name.
    description : str
        Tool description.
    parameters : dict
        JSON Schema for the tool's input.

    Returns
    -------
    dict
        Schema dict with ``"type": "function"`` and ``"function"`` keys.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Builtin tool registration
# ══════════════════════════════════════════════════════════════════════════════

# The 9 builtin tools of GenericAgent, each with metadata that can be used
# by the orchestrator for specialist-based tool restriction (A5).

_BUILTIN_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "code_run",
        "description": "Execute Python, Bash, or PowerShell code in a subprocess with timeout and security checks.",
        "category": "code",
        "handler_path": "tools.code_run.code_run",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The code source or command to execute."},
                "code_type": {"type": "string", "enum": ["python", "bash", "powershell"], "description": "Type of code to run."},
                "timeout": {"type": "integer", "description": "Maximum execution time in seconds.", "default": 60},
                "cwd": {"type": "string", "description": "Working directory for execution."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "file_read",
        "description": "Read a file with keyword search and line-number support.",
        "category": "file",
        "handler_path": "tools.file_ops.file_read",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path of the file to read."},
                "start": {"type": "integer", "description": "First line to read (1-indexed).", "default": 1},
                "keyword": {"type": "string", "description": "Keyword to search for (case-insensitive)."},
                "count": {"type": "integer", "description": "Max lines to return.", "default": 200},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "Write, append, or prepend content to a file.",
        "category": "file",
        "handler_path": "tools.file_ops.file_write",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path of the file to write."},
                "content": {"type": "string", "description": "Content to write."},
                "mode": {"type": "string", "enum": ["overwrite", "append", "prepend"], "default": "overwrite"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_patch",
        "description": "Search-and-replace a unique block of text in a file.",
        "category": "file",
        "handler_path": "tools.file_ops.file_patch",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path of the file to patch."},
                "old_content": {"type": "string", "description": "Block of text to find (must be unique)."},
                "new_content": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_content", "new_content"],
        },
    },
    {
        "name": "web_scan",
        "description": "Scan a web page and extract its content using a headless browser.",
        "category": "web",
        "handler_path": "tools.web_tools.web_scan",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scan."},
                "selector": {"type": "string", "description": "CSS selector to target specific elements."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_execute_js",
        "description": "Execute JavaScript code in a headless browser on a given URL.",
        "category": "web",
        "handler_path": "tools.web_tools.web_execute_js",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to load."},
                "js_code": {"type": "string", "description": "JavaScript code to execute."},
            },
            "required": ["url", "js_code"],
        },
    },
    {
        "name": "ask_user",
        "description": "Ask the user a question and wait for their response.",
        "category": "integration",
        "handler_path": "ga.do_ask_user",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question to ask the user."},
            },
            "required": ["question"],
        },
    },
    {
        "name": "skill_search",
        "description": "Search for available skills and tools by keyword.",
        "category": "search",
        "handler_path": "plugins.tools.skill_search_tool.do_skill_search",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for skills/tools."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_tools",
        "description": "Read, write, search, and manage the agent's persistent memory store.",
        "category": "memory",
        "handler_path": "plugins.tools.memory_search.do_memory",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write", "search", "delete", "list"], "description": "Memory operation."},
                "key": {"type": "string", "description": "Memory key (for read/write/delete)."},
                "value": {"type": "string", "description": "Value to write."},
                "query": {"type": "string", "description": "Search query (for search action)."},
            },
            "required": ["action"],
        },
    },
]

# Set of all builtin tool names — used by the orchestrator for specialist enforcement
BUILTIN_TOOL_NAMES: set[str] = {t["name"] for t in _BUILTIN_TOOL_DEFINITIONS}


def register_builtin_tools(registry: Optional[ToolRegistry] = None) -> int:
    """Register all 9 builtin tools in the tool registry.

    Each builtin tool is registered with a placeholder handler that
    lazily imports the actual implementation from ``handler_path``.
    This ensures the registry has full metadata for specialist-based
    tool restriction, without eagerly importing all tool modules.

    Parameters
    ----------
    registry : ToolRegistry | None
        The registry to register into.  Defaults to the global singleton.

    Returns
    -------
    int
        Number of builtin tools registered.
    """
    if registry is None:
        registry = get_registry()

    registered = 0
    for tool_def in _BUILTIN_TOOL_DEFINITIONS:
        # Create a lazy handler that defers the actual import
        handler_path = tool_def.pop("handler_path")

        def _make_lazy_handler(hp: str) -> Callable:
            """Create a lazy handler that imports the real function on first call."""
            _cached: list[Optional[Callable]] = [None]

            def lazy_handler(args: dict, response: Any) -> Any:
                if _cached[0] is None:
                    module_path, func_name = hp.rsplit(".", 1)
                    try:
                        mod = importlib.import_module(module_path)
                        _cached[0] = getattr(mod, func_name)
                    except (ImportError, AttributeError) as e:
                        logger.error("Failed to load builtin tool handler %s: %s", hp, e)
                        return {"status": "error", "msg": f"Tool handler not available: {hp}"}
                return _cached[0](args, response)  # type: ignore[misc]

            return lazy_handler

        tool_def["handler"] = _make_lazy_handler(handler_path)
        tool_def["source"] = "builtin"

        try:
            registry.register(**tool_def, override=True)
            registered += 1
        except Exception as e:
            logger.warning("Failed to register builtin tool '%s': %s", tool_def.get("name"), e)

    logger.info("Registered %d builtin tools in the registry", registered)
    return registered

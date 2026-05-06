"""tools — Dynamic Tool Plugin System for GenericAgent.

This package provides a registry-based tool system that allows tools to be
registered, discovered, and validated at runtime. It replaces the hardcoded
``do_*`` convention with a flexible plugin architecture while maintaining
full backward compatibility.

Key Components
--------------
- :class:`ToolDefinition` — Schema + handler for a single tool
- :class:`ToolRegistry` — Central registry for all tools (builtin + plugins)
- :func:`register_tool` — Decorator to register a function as a tool
- :func:`load_plugins` — Auto-discover and load tool plugins from ``plugins/``

Example
-------
::

    from tools import register_tool, ToolRegistry

    @register_tool(
        name="web_search",
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
    def do_web_search(args: dict, response: Any) -> dict:
        query = args["query"]
        # ... perform search ...
        return {"status": "success", "results": [...]}
"""

from __future__ import annotations

from tools.registry import (
    ToolDefinition,
    ToolRegistry,
    get_registry,
    register_tool,
    tool_schema_to_openai,
)

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "get_registry",
    "register_tool",
    "tool_schema_to_openai",
]

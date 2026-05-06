"""mcp — Model Context Protocol client for GenericAgent.

MCP (Model Context Protocol) is Anthropic's open standard for connecting
AI agents to external tool servers.  This package provides a lightweight
MCP client that can discover and call tools exposed by MCP servers,
making them available as regular tools in the GenericAgent tool registry.

Key Components
--------------
- :class:`MCPClient` — Connect to MCP servers and discover their tools
- :class:`MCPServerConfig` — Configuration for a single MCP server
- :func:`connect_mcp_server` — Connect and register tools from an MCP server
- :func:`load_mcp_config` — Load MCP server configs from a JSON file

MCP Server Types
----------------
- **stdio** — Server launched as a subprocess (e.g. ``npx @modelcontextprotocol/server-filesystem``)
- **sse** — Server accessed via HTTP Server-Sent Events
- **streamable_http** — Server accessed via HTTP with streaming support

Example
-------
::

    from mcp import MCPClient, MCPServerConfig

    config = MCPServerConfig(
        name="filesystem",
        transport="stdio",
        command="npx",
        args=["@modelcontextprotocol/server-filesystem", "/tmp"],
    )

    client = MCPClient()
    tools = client.connect(config)
    for tool in tools:
        print(f"Discovered: {tool.name} — {tool.description}")
"""

from __future__ import annotations

from mcp.client import (
    MCPClient,
    MCPServerConfig,
    MCPServerStatus,
    connect_mcp_server,
    load_mcp_config,
)

__all__ = [
    "MCPClient",
    "MCPServerConfig",
    "MCPServerStatus",
    "connect_mcp_server",
    "load_mcp_config",
]

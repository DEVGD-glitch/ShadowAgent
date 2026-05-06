"""mcp/client.py — MCP (Model Context Protocol) client implementation.

Connects to MCP servers via stdio or SSE transport, discovers their
available tools, and registers them in the GenericAgent tool registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("mcp.client")


# ══════════════════════════════════════════════════════════════════════════════
#  MCPServerConfig
# ══════════════════════════════════════════════════════════════════════════════


class MCPServerStatus(Enum):
    """Status of an MCP server connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server connection.

    Attributes
    ----------
    name : str
        Unique identifier for this server.
    transport : str
        Transport type — ``"stdio"`` or ``"sse"``.
    command : str
        Command to launch the server (stdio transport only).
    args : list[str]
        Command arguments (stdio transport only).
    url : str
        Server URL (SSE transport only).
    env : dict[str, str]
        Additional environment variables for the server process.
    disabled : bool
        If ``True``, this server is skipped during auto-connect.
    """

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    disabled: bool = False


# ══════════════════════════════════════════════════════════════════════════════
#  MCP Tool representation
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class MCPTool:
    """A tool discovered from an MCP server.

    Attributes
    ----------
    name : str
        Tool name as defined by the MCP server.
    description : str
        Human-readable description.
    input_schema : dict
        JSON Schema for the tool's input parameters.
    server_name : str
        Name of the MCP server that provides this tool.
    """

    name: str
    description: str
    input_schema: dict
    server_name: str

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
#  MCPClient
# ══════════════════════════════════════════════════════════════════════════════


class MCPClient:
    """Client for connecting to MCP servers and discovering their tools.

    The client manages a collection of MCP server connections and provides
    methods to:

    * Connect to servers (stdio or SSE)
    * Discover available tools
    * Call tools on connected servers
    * Register discovered tools in the GenericAgent tool registry

    Usage
    -----
    ::

        client = MCPClient()
        tools = client.connect(MCPServerConfig(
            name="filesystem",
            transport="stdio",
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", "/tmp"],
        ))
        result = client.call_tool("filesystem", "read_file", {"path": "/tmp/test.txt"})
    """

    def __init__(self) -> None:
        self._servers: Dict[str, MCPServerConnection] = {}
        self._tools: Dict[str, MCPTool] = {}  # tool_name → MCPTool
        self._lock = threading.Lock()

    # ── Connection management ─────────────────────────────────────────────

    def connect(self, config: MCPServerConfig) -> list[MCPTool]:
        """Connect to an MCP server and discover its tools.

        Parameters
        ----------
        config : MCPServerConfig
            Server configuration.

        Returns
        -------
        list[MCPTool]
            Tools discovered from the server.

        Raises
        ------
        ConnectionError
            If the server cannot be reached.
        """
        if config.disabled:
            logger.info("MCP server %s is disabled, skipping", config.name)
            return []

        with self._lock:
            # Disconnect existing if reconnecting
            if config.name in self._servers:
                self._servers[config.name].disconnect()

            conn = MCPServerConnection(config)
            self._servers[config.name] = conn

        try:
            tools = conn.connect()
            with self._lock:
                for tool in tools:
                    self._tools[tool.name] = tool
            logger.info(
                "Connected to MCP server '%s': %d tools discovered",
                config.name,
                len(tools),
            )
            return tools
        except Exception as exc:
            logger.error("Failed to connect to MCP server '%s': %s", config.name, exc)
            raise ConnectionError(f"MCP server '{config.name}': {exc}") from exc

    def disconnect(self, server_name: str) -> None:
        """Disconnect from an MCP server."""
        with self._lock:
            conn = self._servers.pop(server_name, None)
            if conn:
                conn.disconnect()
                # Remove tools from this server
                self._tools = {
                    n: t for n, t in self._tools.items()
                    if t.server_name != server_name
                }

    def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        with self._lock:
            for conn in self._servers.values():
                conn.disconnect()
            self._servers.clear()
            self._tools.clear()

    # ── Tool discovery ────────────────────────────────────────────────────

    def list_tools(self, server_name: Optional[str] = None) -> list[MCPTool]:
        """List discovered tools, optionally filtered by server."""
        with self._lock:
            tools = list(self._tools.values())
        if server_name:
            tools = [t for t in tools if t.server_name == server_name]
        return sorted(tools, key=lambda t: t.name)

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Look up a discovered tool by name."""
        with self._lock:
            return self._tools.get(tool_name)

    # ── Tool invocation ───────────────────────────────────────────────────

    def call_tool(
        self, server_name: str, tool_name: str, arguments: dict
    ) -> Any:
        """Call a tool on a connected MCP server.

        Parameters
        ----------
        server_name : str
            The MCP server to call.
        tool_name : str
            The tool to invoke.
        arguments : dict
            Tool arguments.

        Returns
        -------
        Any
            The tool's return value.
        """
        with self._lock:
            conn = self._servers.get(server_name)

        if conn is None:
            raise ValueError(f"MCP server '{server_name}' is not connected")

        return conn.call_tool(tool_name, arguments)

    def call_tool_by_name(self, tool_name: str, arguments: dict) -> Any:
        """Call a tool by its name (auto-resolves the server).

        Parameters
        ----------
        tool_name : str
            The tool to invoke.
        arguments : dict
            Tool arguments.

        Returns
        -------
        Any
            The tool's return value.
        """
        tool = self.get_tool(tool_name)
        if tool is None:
            raise ValueError(f"MCP tool '{tool_name}' not found")
        return self.call_tool(tool.server_name, tool_name, arguments)

    # ── Registry integration ──────────────────────────────────────────────

    def register_tools_in_registry(self) -> int:
        """Register all discovered MCP tools in the GenericAgent tool registry.

        Returns
        -------
        int
            Number of tools registered.
        """
        from tools.registry import get_registry

        registry = get_registry()
        count = 0
        for tool in self.list_tools():
            # Create a closure to capture the tool name
            def make_handler(tn: str) -> Callable:
                def handler(args: dict, response: Any) -> dict:
                    try:
                        result = self.call_tool_by_name(tn, args)
                        return {"status": "success", "data": result}
                    except Exception as exc:
                        return {"status": "error", "msg": str(exc)}
                return handler

            registry.register(
                name=tool.name,
                handler=make_handler(tool.name),
                description=tool.description,
                parameters=tool.input_schema,
                category="mcp",
                source="mcp",
            )
            count += 1

        logger.info("Registered %d MCP tools in tool registry", count)
        return count

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return status information about all MCP connections."""
        status = {}
        with self._lock:
            for name, conn in self._servers.items():
                status[name] = {
                    "status": conn.status.value,
                    "transport": conn.config.transport,
                    "tools_count": sum(
                        1 for t in self._tools.values()
                        if t.server_name == name
                    ),
                }
        return status


# ══════════════════════════════════════════════════════════════════════════════
#  MCPServerConnection — manages a single MCP server connection
# ══════════════════════════════════════════════════════════════════════════════


class MCPServerConnection:
    """Manages a single MCP server connection via stdio or SSE transport.

    This implements a minimal JSON-RPC 2.0 client that communicates with
    the MCP server over stdin/stdout (stdio) or HTTP Server-Sent Events (SSE).

    SSE Transport
    -------------
    The SSE transport connects to an MCP server that exposes an HTTP endpoint.
    The client sends JSON-RPC requests via HTTP POST and receives responses
    via SSE streaming.  This is the standard transport for remote MCP servers.

    The flow is:

    1. ``POST /sse`` — open an SSE stream to receive the server's endpoint URL
    2. ``POST <endpoint>`` — send JSON-RPC requests
    3. Responses arrive as SSE events on the stream from step 1
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.status = MCPServerStatus.DISCONNECTED
        self._process: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._tools_cache: list[MCPTool] = []
        # SSE transport state
        self._sse_session: Any = None  # requests.Session
        self._sse_endpoint: str = ""   # Server's message endpoint URL
        self._sse_thread: Optional[threading.Thread] = None
        self._sse_responses: Dict[int, Any] = {}  # id → response
        self._sse_lock = threading.Lock()
        self._sse_stop_event = threading.Event()

    def connect(self) -> list[MCPTool]:
        """Connect to the MCP server and discover tools.

        Returns
        -------
        list[MCPTool]
            Discovered tools.
        """
        self.status = MCPServerStatus.CONNECTING

        try:
            if self.config.transport == "stdio":
                self._connect_stdio()
            elif self.config.transport == "sse":
                self._connect_sse()
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")

            # Discover tools
            tools = self._discover_tools()
            self._tools_cache = tools
            self.status = MCPServerStatus.CONNECTED
            return tools

        except Exception as exc:
            self.status = MCPServerStatus.ERROR
            logger.error("MCP connection failed for '%s': %s", self.config.name, exc)
            raise

    def _connect_stdio(self) -> None:
        """Launch the MCP server as a subprocess."""
        env = os.environ.copy()
        env.update(self.config.env)

        cmd = [self.config.command] + self.config.args
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        logger.info(
            "Launched MCP server '%s': %s (PID %d)",
            self.config.name,
            " ".join(cmd),
            self._process.pid,
        )

        # Initialize the MCP connection
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "GenericAgent",
                "version": "0.5.0",
            },
        })

        # Send initialized notification
        self._send_notification("notifications/initialized", {})

    def _connect_sse(self) -> None:
        """Connect to an MCP server via SSE (Server-Sent Events).

        This opens an SSE stream to the server's ``/sse`` endpoint to
        receive the message endpoint URL, then starts a background thread
        to listen for incoming SSE events (JSON-RPC responses).

        Raises
        ------
        ConnectionError
            If the SSE connection cannot be established.
        """
        try:
            import requests
        except ImportError:
            raise ConnectionError(
                "SSE transport requires the 'requests' package. "
                "Install it with: pip install requests"
            )

        base_url = self.config.url.rstrip("/")
        sse_url = f"{base_url}/sse"

        self._sse_session = requests.Session()

        # Set up environment variables for authentication
        for key, value in self.config.env.items():
            if key.upper().endswith("TOKEN") or key.upper().endswith("KEY"):
                self._sse_session.headers[key] = value

        logger.info("Connecting to MCP server '%s' via SSE at %s", self.config.name, sse_url)

        # Start the SSE listener thread — it will receive the endpoint
        # and all subsequent JSON-RPC responses
        self._sse_stop_event.clear()
        self._sse_thread = threading.Thread(
            target=self._sse_listener,
            args=(sse_url,),
            daemon=True,
        )
        self._sse_thread.start()

        # Wait for the endpoint URL to arrive (with timeout)
        import time
        deadline = time.time() + 15  # 15 second timeout
        while not self._sse_endpoint and time.time() < deadline:
            time.sleep(0.1)

        if not self._sse_endpoint:
            self._sse_stop_event.set()
            raise ConnectionError(
                f"MCP SSE server '{self.config.name}' did not send endpoint URL "
                f"within 15 seconds"
            )

        # Initialize the MCP connection via SSE
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "GenericAgent",
                "version": "0.5.0",
            },
        })

        # Send initialized notification
        self._send_notification("notifications/initialized", {})

        logger.info(
            "Connected to MCP server '%s' via SSE (endpoint: %s)",
            self.config.name, self._sse_endpoint,
        )

    def _sse_listener(self, sse_url: str) -> None:
        """Background thread that listens for SSE events.

        Parses the SSE stream for two types of events:

        - ``endpoint`` — contains the server's message endpoint URL
        - ``message`` — contains a JSON-RPC response

        Supports multi-line ``data:`` fields (per SSE spec) by
        concatenating consecutive ``data:`` lines with newlines.
        Includes automatic reconnection with exponential backoff.

        Parameters
        ----------
        sse_url : str
            The SSE stream URL (typically ``<base_url>/sse``).
        """
        try:
            import requests
        except ImportError:
            logger.error("SSE listener: 'requests' package not available")
            return

        max_retries = 5
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            if self._sse_stop_event.is_set():
                return

            try:
                response = self._sse_session.get(
                    sse_url,
                    stream=True,
                    timeout=30,
                    headers={"Accept": "text/event-stream"},
                )
                response.raise_for_status()

                current_event = ""
                current_data_lines: list[str] = []  # Support multi-line data

                for line in response.iter_lines(decode_unicode=True):
                    if self._sse_stop_event.is_set():
                        return

                    if line is None:
                        continue

                    # SSE spec: lines starting with "data:" accumulate
                    # Do NOT strip — only strip the "data:" prefix
                    if line.startswith("data:"):
                        data_content = line[5:]
                        # Remove exactly one leading space if present (SSE spec)
                        if data_content.startswith(" "):
                            data_content = data_content[1:]
                        current_data_lines.append(data_content)
                    elif line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith(":"):
                        # Comment line — skip (SSE heartbeat keep-alive)
                        continue
                    elif line.strip() == "":
                        # End of event — process it
                        current_data = "\n".join(current_data_lines)

                        if current_event == "endpoint" and current_data:
                            self._sse_endpoint = current_data
                            logger.debug("SSE endpoint received: %s", self._sse_endpoint)
                        elif current_event == "message" and current_data:
                            try:
                                msg = json.loads(current_data)
                                msg_id = msg.get("id")
                                if msg_id is not None:
                                    with self._sse_lock:
                                        self._sse_responses[msg_id] = msg
                            except json.JSONDecodeError:
                                logger.warning("SSE: invalid JSON in message event")
                        elif not current_event and current_data:
                            # Default event type (no "event:" line) — treat as message
                            try:
                                msg = json.loads(current_data)
                                msg_id = msg.get("id")
                                if msg_id is not None:
                                    with self._sse_lock:
                                        self._sse_responses[msg_id] = msg
                            except json.JSONDecodeError:
                                pass

                        # Reset for next event
                        current_event = ""
                        current_data_lines = []

                # If we exit the loop without stop signal, the stream ended
                if not self._sse_stop_event.is_set():
                    logger.warning("SSE stream ended for '%s', attempting reconnect", self.config.name)

            except Exception as exc:
                if self._sse_stop_event.is_set():
                    return
                logger.error("SSE listener for '%s' failed: %s", self.config.name, exc)

            # Exponential backoff before reconnect
            if attempt < max_retries - 1 and not self._sse_stop_event.is_set():
                delay = base_delay * (2 ** attempt)
                logger.info("SSE reconnect in %.1fs (attempt %d/%d)", delay, attempt + 2, max_retries)
                self._sse_stop_event.wait(timeout=delay)
                if self._sse_stop_event.is_set():
                    return

    def _discover_tools(self) -> list[MCPTool]:
        """Discover tools available on the connected server."""
        response = self._send_request("tools/list", {})
        tools_data = response.get("tools", [])

        tools = []
        for tool_info in tools_data:
            tool = MCPTool(
                name=tool_info.get("name", "unknown"),
                description=tool_info.get("description", ""),
                input_schema=tool_info.get("inputSchema", {"type": "object", "properties": {}}),
                server_name=self.config.name,
            )
            tools.append(tool)

        return tools

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call a tool on this server."""
        if self.status != MCPServerStatus.CONNECTED:
            raise ConnectionError(f"Server '{self.config.name}' is not connected")

        response = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        # MCP returns content as a list of content blocks
        content = response.get("content", [])
        if isinstance(content, list) and len(content) == 1:
            block = content[0]
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except (json.JSONDecodeError, TypeError):
                    return block["text"]
        return content

    def disconnect(self) -> None:
        """Disconnect from the server.

        For stdio transport, terminates the subprocess.
        For SSE transport, stops the listener thread and closes the session.
        """
        # Stop SSE listener
        self._sse_stop_event.set()
        if self._sse_thread is not None and self._sse_thread.is_alive():
            self._sse_thread.join(timeout=5)
        self._sse_thread = None
        self._sse_endpoint = ""

        # Close SSE session
        if self._sse_session is not None:
            try:
                self._sse_session.close()
            except Exception:
                logger.debug("Error closing SSE session for '%s'", self.config.name, exc_info=True)
            self._sse_session = None

        # Clear SSE responses
        with self._sse_lock:
            self._sse_responses.clear()

        # Terminate stdio process
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                logger.debug("Failed to terminate MCP server process, attempting kill", exc_info=True)
                try:
                    self._process.kill()
                except Exception:
                    logger.debug("Failed to kill MCP server process", exc_info=True)
            self._process = None

        self.status = MCPServerStatus.DISCONNECTED

    # ── JSON-RPC communication ────────────────────────────────────────────

    def _send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and return the response.

        For stdio transport, writes to the process stdin and reads from stdout.
        For SSE transport, POSTs to the endpoint and waits for the SSE response.
        """
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        if self.config.transport == "stdio":
            return self._send_request_stdio(request)
        elif self.config.transport == "sse":
            return self._send_request_sse(request)
        else:
            raise ConnectionError(f"Unsupported transport: {self.config.transport}")

    def _send_request_stdio(self, request: dict) -> dict:
        """Send a JSON-RPC request via stdio transport."""
        if self._process is None or self._process.stdin is None:
            raise ConnectionError("MCP server process not available")

        # Send request
        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str.encode("utf-8"))
        self._process.stdin.flush()

        # Read response
        if self._process.stdout is None:
            raise ConnectionError("MCP server stdout not available")

        response_line = self._process.stdout.readline()
        if not response_line:
            raise ConnectionError("MCP server closed connection")

        try:
            response = json.loads(response_line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ConnectionError(f"Invalid MCP response: {exc}") from exc

        # Check for errors
        if "error" in response:
            error = response["error"]
            raise ConnectionError(
                f"MCP error {error.get('code')}: {error.get('message')}"
            )

        return response.get("result", {})

    def _send_request_sse(self, request: dict) -> dict:
        """Send a JSON-RPC request via SSE transport.

        POSTs the request to the server's message endpoint and waits
        for the response to arrive on the SSE stream.
        """
        if not self._sse_endpoint:
            raise ConnectionError("SSE endpoint not available — not connected")

        try:
            import requests as req_module
        except ImportError:
            raise ConnectionError("SSE transport requires the 'requests' package")

        # POST the request to the endpoint
        try:
            post_resp = self._sse_session.post(
                self._sse_endpoint,
                json=request,
                timeout=30,
            )
            post_resp.raise_for_status()
        except req_module.RequestException as exc:
            raise ConnectionError(
                f"MCP SSE request failed for '{self.config.name}': {exc}"
            ) from exc

        # Wait for the response on the SSE stream (with timeout)
        request_id = request["id"]
        import time
        deadline = time.time() + 30  # 30 second timeout

        while time.time() < deadline:
            with self._sse_lock:
                if request_id in self._sse_responses:
                    response = self._sse_responses.pop(request_id)
                    break
            time.sleep(0.05)
        else:
            raise ConnectionError(
                f"MCP SSE request timed out for '{self.config.name}' "
                f"(method: {request['method']})"
            )

        # Check for errors
        if "error" in response:
            error = response["error"]
            raise ConnectionError(
                f"MCP error {error.get('code')}: {error.get('message')}"
            )

        return response.get("result", {})

    def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected).

        For stdio transport, writes to the process stdin.
        For SSE transport, POSTs to the endpoint (fire-and-forget).
        """
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        if self.config.transport == "stdio":
            if self._process is None or self._process.stdin is None:
                return
            notification_str = json.dumps(notification) + "\n"
            self._process.stdin.write(notification_str.encode("utf-8"))
            self._process.stdin.flush()
        elif self.config.transport == "sse":
            if self._sse_endpoint and self._sse_session:
                try:
                    self._sse_session.post(
                        self._sse_endpoint,
                        json=notification,
                        timeout=10,
                    )
                except Exception as exc:
                    logger.debug("SSE notification send failed: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
#  Convenience functions
# ══════════════════════════════════════════════════════════════════════════════


def load_mcp_config(config_path: Optional[str] = None) -> list[MCPServerConfig]:
    """Load MCP server configurations from a JSON file.

    The file should follow the MCP config format::

        {
            "mcpServers": {
                "filesystem": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-filesystem", "/tmp"]
                },
                "github": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "xxx"}
                }
            }
        }

    Parameters
    ----------
    config_path : str | None
        Path to the config file.  Defaults to ``mcp_config.json`` in the
        project root.

    Returns
    -------
    list[MCPServerConfig]
        Parsed server configurations.
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mcp_config.json",
        )

    if not os.path.isfile(config_path):
        logger.debug("MCP config file not found: %s", config_path)
        return []

    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load MCP config: %s", exc)
        return []

    servers = data.get("mcpServers", {})
    configs = []
    for name, server_data in servers.items():
        if not isinstance(server_data, dict):
            continue
        try:
            config = MCPServerConfig(
                name=name,
                transport=server_data.get("transport", "stdio"),
                command=server_data.get("command", ""),
                args=server_data.get("args", []),
                url=server_data.get("url", ""),
                env=server_data.get("env", {}),
                disabled=server_data.get("disabled", False),
            )
            configs.append(config)
        except Exception as exc:
            logger.warning("Skipping MCP server config '%s': %s", name, exc)

    return configs


def connect_mcp_server(config: MCPServerConfig) -> list[MCPTool]:
    """Connect to an MCP server and register its tools.

    This is a convenience function that creates a client, connects,
    and registers the tools in the global registry.

    Parameters
    ----------
    config : MCPServerConfig
        Server configuration.

    Returns
    -------
    list[MCPTool]
        Discovered tools.
    """
    client = MCPClient()
    tools = client.connect(config)
    client.register_tools_in_registry()
    return tools

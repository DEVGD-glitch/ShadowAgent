"""server.py — FastAPI + SSE API server for Shadow Agent.

Exposes the Shadow Agent as a REST API with Server-Sent Events streaming,
enabling third-party integrations, web UIs, and programmatic access.

Endpoints
---------
- ``POST /auth/login`` — Authenticate and receive a token
- ``GET /auth/status`` — Check if current request is authenticated
- ``POST /chat`` — Send a message and get a streaming response (SSE)
- ``POST /chat/sync`` — Send a message and wait for the full response
- ``POST /abort`` — Abort the current task
- ``GET /models`` — List available LLM models
- ``POST /models/switch`` — Switch to a different model
- ``GET /tools`` — List available tools
- ``GET /status`` — Agent status (running, idle, etc.)
- ``GET /memory/search`` — Semantic search over agent memory (RAG)
- ``WebSocket /ws/chat`` — Full-duplex chat via WebSocket

Security
--------
All endpoints (except /auth/login) require a valid bearer token via the
``Authorization: Bearer <token>`` header.  WebSocket connections validate
the token via the ``token`` query parameter during the handshake.

Example
-------
::

    # Authenticate
    curl -X POST http://localhost:8765/auth/login

    # Chat with token
    curl -X POST http://localhost:8765/chat \\
         -H "Content-Type: application/json" \\
         -H "Authorization: Bearer <token>" \\
         -d '{"message": "Hello, what can you do?"}'
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import secrets
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("server")

# Apply redacting filter to strip API keys from server logs (Task 8.2.4)
try:
    from logging_config import RedactingFilter
    logger.addFilter(RedactingFilter())
except ImportError:
    pass

# ══════════════════════════════════════════════════════════════════════════════
#  Lazy imports — FastAPI is optional
# ══════════════════════════════════════════════════════════════════════════════

_fastapi_available = False
try:
    from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, JSONResponse
    from pydantic import BaseModel, Field
    _fastapi_available = True
except ImportError:
    logger.debug("FastAPI not available — API server disabled")


def is_available() -> bool:
    """Check if FastAPI is installed and the server can run."""
    return _fastapi_available


# ══════════════════════════════════════════════════════════════════════════════
#  Authentication (Task 0.2.1)
# ══════════════════════════════════════════════════════════════════════════════

_AUTH_DIR = Path.home() / ".shadowagent"
_AUTH_TOKEN_FILE = _AUTH_DIR / "auth_token"

# In-memory set of currently valid tokens (populated at startup)
_active_tokens: set[str] = set()
_auth_lock = threading.Lock()


def _ensure_auth_dir() -> None:
    """Ensure the auth directory exists with secure permissions."""
    _AUTH_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(_AUTH_DIR), 0o700)
    except OSError:
        logger.warning("Could not set permissions on %s", _AUTH_DIR)


def _load_or_create_token() -> str:
    """Load the persistent auth token, or generate and persist a new one.

    The token is stored in ``~/.genericagent/auth_token``.  On first launch
    a cryptographically random token is generated with ``secrets.token_urlsafe``.
    """
    _ensure_auth_dir()

    if _AUTH_TOKEN_FILE.exists():
        try:
            token = _AUTH_TOKEN_FILE.read_text().strip()
            if token and len(token) >= 20:
                with _auth_lock:
                    _active_tokens.add(token)
                logger.info("Loaded existing auth token from %s", _AUTH_TOKEN_FILE)
                return token
        except OSError as exc:
            logger.warning("Could not read auth token file: %s", exc)

    # Generate new token
    token = secrets.token_urlsafe(32)
    try:
        _AUTH_TOKEN_FILE.write_text(token)
        os.chmod(str(_AUTH_TOKEN_FILE), 0o600)
        logger.info("Generated new auth token and saved to %s", _AUTH_TOKEN_FILE)
    except OSError as exc:
        logger.warning("Could not persist auth token: %s (token will not survive restart)", exc)

    with _auth_lock:
        _active_tokens.add(token)
    return token


def _verify_token_value(token: str) -> bool:
    """Check whether a token string is valid."""
    if not token:
        return False
    with _auth_lock:
        return token in _active_tokens


# ══════════════════════════════════════════════════════════════════════════════
#  Rate limiter (Task 0.2.3)
# ══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Simple in-memory sliding-window rate limiter.

    Parameters
    ----------
    max_requests : int
        Maximum number of requests allowed within *window_seconds*.
    window_seconds : int
        Time window in seconds.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Check if a request from *key* is allowed.

        Returns ``True`` if the request is within limits, ``False`` otherwise.
        """
        now = time.time()
        with self._lock:
            self._requests[key] = [t for t in self._requests[key] if now - t < self.window]
            if len(self._requests[key]) >= self.max_requests:
                return False
            self._requests[key].append(now)
            return True


# Pre-configured rate limiters
_chat_limiter = RateLimiter(max_requests=30, window_seconds=60)
_memory_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ══════════════════════════════════════════════════════════════════════════════
#  Request/Response models
# ══════════════════════════════════════════════════════════════════════════════

if _fastapi_available:

    class ChatRequest(BaseModel):
        """Chat message request."""
        message: str = Field(..., min_length=1, max_length=50000)
        stream: bool = True
        images: Optional[List[str]] = None
        source: str = "api"

    class SwitchModelRequest(BaseModel):
        """Model switch request."""
        index: int = Field(..., ge=0)

    class MemorySearchRequest(BaseModel):
        """Memory search request."""
        query: str = Field(..., min_length=1)
        top_k: int = Field(default=5, ge=1, le=20)
        category: Optional[str] = None

    class LoginRequest(BaseModel):
        """Login request — password is optional if no password is configured."""
        password: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  Server creation
# ══════════════════════════════════════════════════════════════════════════════


def create_app(agent: Any = None) -> Any:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    agent : GenericAgent | None
        The agent instance to serve.  If ``None``, a new one is created.

    Returns
    -------
    FastAPI
        The configured application.
    """
    if not _fastapi_available:
        raise RuntimeError("FastAPI is not installed. Run: pip install fastapi uvicorn")

    # ── Initialize auth ─────────────────────────────────────────────────────
    _primary_token = _load_or_create_token()
    # Optional password from environment variable GA_AUTH_PASSWORD
    _auth_password: Optional[str] = os.environ.get("GA_AUTH_PASSWORD", None)

    app = FastAPI(
        title="GenericAgent API",
        description="REST API for GenericAgent — an AI agent with tools, memory, and reasoning",
        version="0.6.0",
    )

    # ── CORS (Task 0.2.2) ──────────────────────────────────────────────────
    # Restrict origins to localhost by default; configurable via GA_CORS_ORIGINS
    _cors_env = os.environ.get("GA_CORS_ORIGINS", "")
    if _cors_env:
        allowed_origins = _validate_cors_origins(_cors_env)
    else:
        allowed_origins = ["http://localhost:*", "http://127.0.0.1:*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Security headers (Task 8.1.5) ─────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Any:
        """Add security-related headers to every HTTP response.

        These headers harden the API against common web vulnerabilities:
        - X-Content-Type-Options: prevents MIME-type sniffing
        - X-Frame-Options: prevents clickjacking via iframes
        - Content-Security-Policy: restricts resource loading to same-origin
        - Strict-Transport-Security: enforces HTTPS (1 year max-age)
        - X-XSS-Protection: enables browser XSS filter
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # ── Request size limit ──────────────────────────────────────────────
    _MAX_REQUEST_BODY = 10 * 1024 * 1024  # 10 MB

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next: Any) -> Any:
        """Reject requests with bodies exceeding the size limit."""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_REQUEST_BODY:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large (max {_MAX_REQUEST_BODY // (1024*1024)} MB)"},
                    )
            except (ValueError, TypeError):
                pass
        return await call_next(request)

    # ── Auth dependency (Task 0.2.1) ────────────────────────────────────────

    async def verify_token(request: Request) -> None:
        """FastAPI dependency that validates the Bearer token on every request."""
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.query_params.get("token", "")

        if not _verify_token_value(token):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: valid Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # ── WebSocket origin validation (Task 0.2.4) ───────────────────────────

    _cors_origins = set(allowed_origins)

    def _is_ws_origin_allowed(origin: str) -> bool:
        """Check if WebSocket origin is allowed."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(origin)
            if parsed.hostname == "localhost" and parsed.scheme in ("http", "https"):
                # Only allow specific localhost ports, not wildcard patterns
                port = parsed.port
                if port is not None and 1 <= port <= 65535:
                    return True
                # Allow no-port (default 80/443)
                if port is None:
                    return True
                return False
            if parsed.hostname == "127.0.0.1" and parsed.scheme in ("http", "https"):
                port = parsed.port
                if port is not None and 1 <= port <= 65535:
                    return True
                if port is None:
                    return True
                return False
            return origin in _cors_origins
        except Exception:
            return False

    # ── Agent lifecycle ───────────────────────────────────────────────────

    _agent = agent
    _agent_thread: Optional[threading.Thread] = None
    _rag_engine: Optional[Any] = None  # Shared RAGEngine instance

    @app.on_event("startup")
    async def startup() -> None:
        nonlocal _agent, _agent_thread
        if _agent is None:
            from agentmain import GenericAgent
            _agent = GenericAgent()
        if not _agent.is_running:
            _agent_thread = threading.Thread(target=_agent.run, daemon=True)
            _agent_thread.start()
        logger.info("GenericAgent API server started")
        if _primary_token:
            logger.info(
                "Auth token initialized. First-time token: %s...%s",
                _primary_token[:6], _primary_token[-4:],
            )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        if _agent is not None:
            _agent.abort()
        logger.info("GenericAgent API server stopped")

    # ════════════════════════════════════════════════════════════════════════
    #  Auth endpoints (Task 0.2.1)
    # ════════════════════════════════════════════════════════════════════════

    @app.post("/auth/login")
    async def auth_login(request: LoginRequest) -> Any:
        """Authenticate and receive a bearer token.

        If ``GA_AUTH_PASSWORD`` is set, the request must include the correct
        password.  Otherwise, a new session token is returned on any request.
        """
        if _auth_password:
            if request.password != _auth_password:
                raise HTTPException(status_code=401, detail="Invalid password")

        new_token = secrets.token_urlsafe(32)
        with _auth_lock:
            _active_tokens.add(new_token)
        return {"access_token": new_token, "token_type": "bearer"}

    @app.get("/auth/status")
    async def auth_status(request: Request, _auth: None = Depends(verify_token)) -> Any:
        """Check if the current request is authenticated."""
        return {"authenticated": True}

    # ════════════════════════════════════════════════════════════════════════
    #  Chat endpoint (SSE streaming) — protected (Task 0.2.1 + 0.2.3)
    # ════════════════════════════════════════════════════════════════════════

    @app.post("/chat")
    async def chat(request: ChatRequest, _auth: None = Depends(verify_token)) -> Any:
        """Send a message and receive a streaming response via SSE."""
        # Rate limiting (Task 0.2.3)
        client_ip = _get_client_ip(request)
        if not _chat_limiter.is_allowed(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded: max 30 requests/min for /chat")

        if _agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")

        display_queue = _agent.put_task(
            query=request.message,
            source=request.source,
            images=request.images,
        )

        if request.stream:
            return StreamingResponse(
                _stream_queue(_bridge_to_async(display_queue)),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # Synchronous — collect full response
            result = await _collect_response(_bridge_to_async(display_queue))
            return JSONResponse(content={"response": result})

    @app.post("/chat/sync")
    async def chat_sync(request: ChatRequest, _auth: None = Depends(verify_token)) -> Any:
        """Send a message and wait for the complete response."""
        # Rate limiting
        client_ip = _get_client_ip(request)
        if not _chat_limiter.is_allowed(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded: max 30 requests/min for /chat")

        if _agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")

        request.stream = False
        return await chat(request)

    # ── Abort — protected (Task 0.2.1) ────────────────────────────────────

    @app.post("/abort")
    async def abort(_auth: None = Depends(verify_token)) -> Any:
        """Abort the current task."""
        if _agent is not None:
            _agent.abort()
        return {"status": "aborted"}

    # ── Models — protected (Task 0.2.1) ───────────────────────────────────

    @app.get("/models")
    async def list_models(_auth: None = Depends(verify_token)) -> Any:
        """List available LLM models."""
        if _agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        models = _agent.list_llms()
        return {
            "models": [
                {"index": i, "name": name, "active": active}
                for i, name, active in models
            ]
        }

    @app.post("/models/switch")
    async def switch_model(request: SwitchModelRequest, _auth: None = Depends(verify_token)) -> Any:
        """Switch to a different LLM model."""
        if _agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        try:
            _agent.next_llm(request.index)
            name = _agent.get_llm_name(model=True)
            return {"status": "switched", "model": name}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # ── Tools — protected (Task 0.2.1) ────────────────────────────────────

    @app.get("/tools")
    async def list_tools(_auth: None = Depends(verify_token)) -> Any:
        """List available tools."""
        try:
            from tools import get_registry
            registry = get_registry()
            return {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "category": t.category,
                        "source": t.source,
                        "requires_confirmation": t.requires_confirmation,
                    }
                    for t in registry.list_tools()
                ]
            }
        except ImportError:
            return {"tools": []}

    # ── Status — protected (Task 0.2.1) ───────────────────────────────────

    @app.get("/status")
    async def status(_auth: None = Depends(verify_token)) -> Any:
        """Get agent status."""
        if _agent is None:
            return {"status": "not_initialized"}

        return {
            "status": "running" if _agent.is_running else "idle",
            "model": _agent.get_llm_name(model=True) if _agent.is_running else None,
        }

    # ── Memory search (RAG) — protected + rate limited (Task 0.2.1 + 0.2.3) ─

    @app.post("/memory/search")
    async def memory_search(request: MemorySearchRequest, _auth: None = Depends(verify_token)) -> Any:
        """Search agent memory using semantic similarity."""
        # Rate limiting (Task 0.2.3) — stricter for memory search
        client_ip = _get_client_ip(request)
        if not _memory_limiter.is_allowed(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded: max 10 requests/min for /memory/search")

        nonlocal _rag_engine
        try:
            from memory.vector import RAGEngine

            # Reuse shared RAGEngine instance instead of creating per-request
            if _rag_engine is None:
                store_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "memory",
                    "vector_store.json",
                )
                _rag_engine = RAGEngine(store_path=store_path)

            results = _rag_engine.search(
                request.query, top_k=request.top_k, category=request.category
            )

            return {
                "results": [
                    {
                        "text": doc.text[:500],
                        "score": round(score, 4),
                        "source": doc.metadata.get("source", ""),
                        "category": doc.metadata.get("category", ""),
                    }
                    for doc, score in results
                ]
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    # ── MCP status — protected (Task 0.2.1) ───────────────────────────────

    @app.get("/mcp/status")
    async def mcp_status(_auth: None = Depends(verify_token)) -> Any:
        """Get MCP server connection status."""
        if _agent is not None and hasattr(_agent, "_mcp_client"):
            try:
                return {"servers": _agent._mcp_client.get_status()}
            except Exception as exc:
                logger.warning("Failed to get MCP status: %s", exc)
        return {"servers": {}}

    # ════════════════════════════════════════════════════════════════════════
    #  WebSocket — secured (Task 0.2.4)
    # ════════════════════════════════════════════════════════════════════════

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket) -> None:
        """Full-duplex chat via WebSocket.

        Security (Task 0.2.4):
          - Token validation via ``token`` query parameter in the handshake.
          - Origin validation against allowed CORS origins.
          - Proper error logging and clean close instead of ``except: pass``.
        """
        # ── Token validation in handshake ──────────────────────────────────
        token = websocket.query_params.get("token", "")
        if not _verify_token_value(token):
            await websocket.close(code=4001, reason="Unauthorized: invalid or missing token")
            logger.warning("WebSocket connection rejected: invalid token from %s", websocket.client)
            return

        # ── Origin validation (Task 0.2.4) ────────────────────────────────
        origin = websocket.headers.get("origin", "")
        if origin and not _is_ws_origin_allowed(origin):
            await websocket.close(code=4003, reason="Forbidden: origin not allowed")
            logger.warning("WebSocket connection rejected: disallowed origin '%s'", origin)
            return

        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    message = msg.get("message", data)
                except json.JSONDecodeError:
                    message = data

                if _agent is None:
                    await websocket.send_json({"error": "Agent not initialized"})
                    continue

                display_queue = _agent.put_task(query=message, source="websocket")

                # Stream responses back via async bridge
                async_q = await _bridge_to_async(display_queue)
                while True:
                    try:
                        item = await asyncio.wait_for(async_q.get(), timeout=30.0)
                        if "done" in item:
                            await websocket.send_json(
                                {"type": "done", "content": item["done"]}
                            )
                            break
                        elif "next" in item:
                            await websocket.send_json(
                                {"type": "chunk", "content": item["next"]}
                            )
                    except asyncio.TimeoutError:
                        # Send keepalive to prevent timeout
                        await websocket.send_json({"type": "keepalive"})
        except Exception as exc:
            # Task 0.2.4: proper error logging and clean close instead of bare `except: pass`
            logger.error("WebSocket error: %s", exc, exc_info=True)
            try:
                await websocket.close(code=1011, reason="Internal server error")
            except Exception:
                logger.debug("WebSocket already closed during error handling")

    return app


# ══════════════════════════════════════════════════════════════════════════════
#  Utility helpers
# ══════════════════════════════════════════════════════════════════════════════


def _get_client_ip(request: Any) -> str:
    """Extract the client IP from a FastAPI Request for rate limiting."""
    if hasattr(request, "client") and request.client:
        return request.client.host
    return "unknown"


async def _bridge_to_async(sync_queue: queue.Queue) -> asyncio.Queue:
    """Bridge a synchronous queue.Queue to an asyncio.Queue.

    The agent's ``put_task`` returns a ``queue.Queue`` because the agent
    loop runs in a background thread.  This function creates an
    ``asyncio.Queue`` and spawns a background task that continuously
    reads from the sync queue and puts items into the async queue,
    allowing the async SSE/WebSocket handlers to consume data without
    blocking the event loop.

    The pump task is tracked so it can be cancelled when the SSE
    connection drops, preventing task leaks.

    Args:
        sync_queue: The synchronous ``queue.Queue`` returned by
            ``agent.put_task()``.

    Returns:
        An ``asyncio.Queue`` that will receive the same items.
        The queue has a ``_pump_task`` attribute for cancellation.
    """
    async_queue: asyncio.Queue = asyncio.Queue()

    async def _pump() -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, lambda: sync_queue.get(timeout=0.5))
                await async_queue.put(item)
                if "done" in item:
                    break
            except queue.Empty:
                # Check if the sync queue has been closed / task is done
                # by looking at the last item we put
                continue

    pump_task = asyncio.ensure_future(_pump())
    async_queue._pump_task = pump_task  # type: ignore[attr-defined]
    return async_queue


# ══════════════════════════════════════════════════════════════════════════════
#  Streaming helpers
# ══════════════════════════════════════════════════════════════════════════════


async def _stream_queue(display_queue: asyncio.Queue) -> Any:
    """Yield SSE events from an asyncio display queue.

    Uses :class:`asyncio.Queue` instead of :class:`queue.Queue` to avoid
    blocking the event loop with synchronous ``get(timeout=...)`` calls.
    A short ``asyncio.wait_for`` timeout produces keepalive frames when
    no data is available, maintaining the SSE connection.
    """
    pump_task = getattr(display_queue, "_pump_task", None)
    try:
        while True:
            try:
                item = await asyncio.wait_for(display_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if "done" in item:
                data = json.dumps({"type": "done", "content": item["done"]}, ensure_ascii=False)
                yield f"data: {data}\n\n"
                break
            elif "next" in item:
                data = json.dumps({"type": "chunk", "content": item["next"]}, ensure_ascii=False)
                yield f"data: {data}\n\n"
    finally:
        # Cancel the pump task when the SSE connection drops to prevent task leaks
        if pump_task is not None and not pump_task.done():
            pump_task.cancel()


async def _collect_response(display_queue: asyncio.Queue, timeout: int = 300) -> str:
    """Collect the full response from an asyncio display queue.

    Non-blocking — uses ``await`` instead of synchronous ``get()``.
    """
    full_response = ""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        remaining = deadline - loop.time()
        try:
            item = await asyncio.wait_for(display_queue.get(), timeout=min(remaining, 1.0))
        except asyncio.TimeoutError:
            continue

        if "done" in item:
            return item["done"]
        elif "next" in item:
            full_response += item["next"]

    return full_response + "\n[Timeout: response took too long]"


# ══════════════════════════════════════════════════════════════════════════════
#  Server runner
# ══════════════════════════════════════════════════════════════════════════════


def run_server(host: str = "127.0.0.1", port: int = 8765, agent: Any = None) -> None:
    """Start the API server.

    Parameters
    ----------
    host : str
        Bind address.
    port : int
        Port number.
    agent : GenericAgent | None
        The agent instance to serve.
    """
    if not _fastapi_available:
        print("Error: FastAPI is not installed. Run: pip install fastapi uvicorn")
        return

    import uvicorn

    app = create_app(agent)
    uvicorn.run(app, host=host, port=port, log_level="info")


def _validate_cors_origins(origins_str: str) -> list[str]:
    """Validate and parse CORS origins."""
    if origins_str.strip() == "*":
        logger.warning("GA_CORS_ORIGINS=* allows all origins - not recommended for production")
        return ["*"]
    origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    validated = []
    for o in origins:
        if o.startswith(("http://", "https://")):
            validated.append(o)
        else:
            logger.warning(f"Invalid CORS origin skipped: {o}")
    return validated


if __name__ == "__main__":
    run_server()

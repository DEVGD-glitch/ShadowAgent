# ADR 005: Rate Limiting with slowapi + In-Memory Sliding Window

## Status

Accepted

## Context

GenericAgent v0.6.0 exposed a FastAPI-based REST API (in `server.py`)
with no rate limiting.  Any client in possession of a valid bearer
token could make unlimited requests to `/chat`, `/memory/search`, and
other endpoints.  This posed several risks:

1. **Cost explosion.**  Each `/chat` request triggers one or more LLM
   API calls, which are billed per token.  A runaway client or a
   misconfigured integration could easily rack up hundreds of dollars
   in LLM costs within minutes.

2. **Denial of service.**  Without rate limiting, a single client could
   saturate the agent's task queue, preventing other users (or the same
   user's other tabs) from receiving responses.

3. **Memory exhaustion.**  Each concurrent request consumes memory for
   the display queue, streaming buffer, and conversation history.  An
   unbounded request rate could exhaust available RAM.

4. **Data exfiltration surface.**  The `/memory/search` endpoint
   returns stored memories.  Unlimited access makes it easier for a
   compromised token to extract all stored data.

The security audit (Phase 0, task 0.2.3) identified this as a P0
requirement and mandated rate limiting on all sensitive endpoints.

## Decision

We implement a two-layer rate limiting strategy:

### Layer 1: slowapi (FastAPI middleware)

When the `slowapi` package is installed, we use it as FastAPI
middleware to enforce per-IP rate limits at the framework level:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /chat` | 30 requests | 60 seconds |
| `POST /chat/sync` | 30 requests | 60 seconds |
| `POST /memory/search` | 10 requests | 60 seconds |
| All other endpoints | 60 requests | 60 seconds |

`slowapi` is built on top of `limits` and uses an in-memory storage
backend by default.  It integrates natively with FastAPI via the
`Limiter` class and the `@limiter.limit()` decorator.

### Layer 2: In-memory sliding-window rate limiter (fallback)

When `slowapi` is not installed, a custom `RateLimiter` class (in
`server.py`) provides the same guarantees using a pure-Python
sliding-window algorithm:

```python
class RateLimiter:
    def __init__(self, max_requests=30, window_seconds=60): ...
    def is_allowed(self, key: str) -> bool: ...
```

This class:
- Maintains a `dict[str, list[float]]` mapping client keys to
  timestamps of recent requests.
- On each call, prunes timestamps older than the window and checks
  whether the remaining count is below the limit.
- Is thread-safe via an internal `threading.Lock`.

### Why not Redis?

Redis would allow rate limiting across multiple server processes, but
GenericAgent is a **single-user desktop application** — the server runs
on `localhost` and serves a single user.  An in-memory limiter is
simpler, has zero external dependencies, and is sufficient for the
threat model (protect against runaway scripts and browser-tab storms,
not against distributed attacks).

### Why slowapi + custom fallback?

- `slowapi` provides the best FastAPI integration and is well-tested.
- However, it is an optional dependency.  The custom fallback ensures
  rate limiting works even without it.
- Both layers use the same limits and the same per-IP keying strategy.

## Consequences

### Positive

- **Cost protection.**  A runaway client cannot make more than 30 LLM
  calls per minute on `/chat`.
- **No external dependencies.**  The custom fallback means rate limiting
  works even without `slowapi`.
- **Configurable.**  Limits are defined as constants at the top of
  `server.py` and can be overridden via environment variables.
- **Consistent behaviour.**  Both layers use the same limits and
  keying strategy, so behaviour is identical regardless of which is
  active.

### Negative

- **Per-process state.**  The in-memory limiter resets on server
  restart.  This is acceptable for a single-user desktop app.
- **IP-based keying is coarse.**  Multiple users behind the same IP
  (unlikely on localhost) would share a limit.  Acceptable for the
  current deployment model.
- **No distributed limiting.**  If GenericAgent ever runs as a
  multi-process service, Redis or a similar backend will be needed.

### Risks

- Rate limit bypass via IPv6: a client could rotate through IPv6
  addresses on localhost.  Mitigated by the JWT auth requirement —
  even with different IPs, the same bearer token is subject to
  per-token limits (future enhancement).

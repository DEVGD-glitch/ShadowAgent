# ADR 003: EventBus for Decoupled Communication

## Status

Accepted

## Context

As GenericAgent grew from a simple chat loop into a multi-subsystem
platform (memory, guardrails, extensions, handoffs, voice, MCP), the
codebase accumulated a tangle of direct cross-module dependencies:

1. **Circular imports.**  `core.py` imported from `extensions.py`, which
   imported from `flow.py`, which imported back from `core.py`.  The
   import graph had cycles that required careful ordering and `lazy
   imports` to avoid `ImportError` at startup.

2. **Scattered callbacks.**  Each subsystem defined its own hook
   mechanism (`fire_hook`, `on_before_tool_call`, `on_after_response`,
   etc.).  Adding a new consumer meant modifying the producer's code to
   call the new callback — a violation of the Open/Closed Principle.

3. **Testing difficulty.**  To test whether a tool execution triggered
   the correct side-effect, tests had to mock the entire producer
   module, set up the callback chain, and verify the call.  This was
   brittle and coupled tests to implementation details.

4. **No global observability.**  There was no single place to see "what
   events are happening in the system right now."  Debugging required
   enabling DEBUG logging everywhere and sifting through thousands of
   lines.

## Decision

We introduce a central `EventBus` (in `agentmain/event_bus.py`) that
implements a **publish/subscribe** pattern:

```
Publisher ──publish(Event)──> EventBus ──notify──> Subscriber(s)
```

### Design

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Event types** | Enum `EventType` with well-known values | Discoverable, typed, IDE-friendly |
| **Event data** | `dataclass Event` with `type`, `data`, `source` | Structured, extensible |
| **Thread safety** | Internal `threading.Lock` | GenericAgent is multi-threaded |
| **Sync dispatch** | Handlers run in the publisher's thread | Simplicity; avoids async complexity |
| **Error isolation** | Handler exceptions are caught and logged | One bad subscriber cannot crash the bus |
| **Global singleton** | `get_event_bus()` function | Easy access; consistent instance |

### Well-known event types

| Event | When published | Example data |
|-------|---------------|--------------|
| `LLM_CALL_START` | Before an LLM request | `{"model": "claude-sonnet-4-6", "prompt_len": 1234}` |
| `LLM_CALL_END` | After a successful LLM response | `{"model": "claude-sonnet-4-6", "tokens": 567}` |
| `LLM_CALL_ERROR` | When an LLM call fails | `{"model": "claude-sonnet-4-6", "error": "timeout"}` |
| `TOOL_EXECUTED` | After a tool runs | `{"tool": "file_write", "success": True}` |
| `TOOL_ERROR` | When a tool fails | `{"tool": "web_scan", "error": "ConnectionError"}` |
| `ERROR_OCCURRED` | General error | `{"module": "core", "error": "..."}` |
| `THEME_CHANGED` | UI theme switch | `{"theme": "light"}` |
| `SESSION_SAVED` | Session persisted to disk | `{"path": "/home/user/.genericagent/..."}` |
| `SESSION_LOADED` | Session restored | `{"path": "..."}` |
| `AGENT_STARTED` | Agent loop begins | `{}` |
| `AGENT_STOPPED` | Agent loop ends | `{}` |
| `SHUTDOWN_REQUESTED` | Graceful shutdown | `{}` |
| `CONFIG_CHANGED` | Configuration reloaded | `{"keys": ["model", "temperature"]}` |
| `MEMORY_UPDATED` | Memory store changes | `{"collection": "general"}` |

### Relationship to extension hooks

The existing `fire_hook()` mechanism in `extensions.py` is being
gradually replaced by EventBus events.  During the transition, bridge
code translates hooks to events so that both old and new consumers work.

## Consequences

### Positive

- **Decoupling.**  Publishers no longer need to know about subscribers.
  New features can subscribe to existing events without modifying the
  producer.
- **No circular imports.**  Modules only need to import `EventType` and
  `get_event_bus` — lightweight dependencies that never cause cycles.
- **Testability.**  Tests can subscribe to events and assert on them
  without mocking internals.
- **Observability.**  A single debug subscriber can log all events,
  providing a timeline of system activity.

### Negative

- **Implicit coupling.**  The event bus makes data flow harder to trace
  statically — you cannot see from the publisher's code alone who will
  react to an event.  Mitigated by documenting all event types and their
  consumers in this ADR.
- **Synchronous dispatch.**  Handlers run in the publisher's thread, so
  a slow subscriber can block the publisher.  Mitigated by the rule
  "handlers must not be long-running."  If async dispatch is needed in
  the future, an `AsyncEventBus` variant can be added.
- **Event ordering.**  Subscribers are notified in subscription order,
  but cross-event ordering is not guaranteed.  If strict ordering is
  required, a dedicated sequencer must be built on top.
- **Memory leaks.**  If subscribers forget to unsubscribe, they remain
  referenced forever.  Mitigated by the `unsubscribe()` method and
  documentation.

### Risks

- Event explosion: as the system grows, the number of event types may
  balloon.  Mitigated by keeping the `EventType` enum focused on
  cross-cutting concerns; internal module state changes should use
  direct method calls, not events.

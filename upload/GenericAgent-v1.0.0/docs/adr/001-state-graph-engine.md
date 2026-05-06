# ADR 001: State Graph Engine for Agent Orchestration

## Status

Accepted

## Context

GenericAgent v0.6.0 needs a structured, extensible way to orchestrate the
agent loop.  Prior to this decision the agent ran a simple
`while not done` loop that alternated between "think" (LLM call) and "act"
(tool dispatch) steps.  This monolithic loop had several shortcomings:

1. **No support for cycles.**  Agents that need to self-correct (retry a
   failed tool call, refine a search query, or re-plan after a dead end)
   had to embed ad-hoc branching logic inside the loop body, making the
   code hard to follow and even harder to test.

2. **No checkpointing.**  If the process crashed mid-task, the entire
   conversation state was lost.  Long-running autonomous tasks had no way
   to resume from the last successful step.

3. **No conditional routing.**  Different task phases (research, coding,
   review, deployment) required different tool sets and prompt strategies,
   but the flat loop could not dynamically route to specialised handlers.

4. **No composition.**  Complex workflows that combined multiple
   sub-agents or nested pipelines were impossible to express cleanly.

LangGraph and similar frameworks demonstrated that a **directed state graph**
solves all of these problems by modelling each step as a node and the
flow of control as edges — including conditional edges and cycles.

## Decision

We implement a custom **State Graph engine** in
`engine/state_graph.py`, inspired by LangGraph's architecture but
tailored to GenericAgent's needs.

Key design choices:

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Node model** | Each node is a `Callable(state) -> dict` | Simple, composable, testable |
| **State schema** | TypedDict with per-key reducers | Type safety + controlled merge |
| **Cycles** | Supported via conditional edges | Enables retry / self-correction loops |
| **Checkpointing** | Pluggable `CheckpointProtocol` (memory + SQLite) | Fault tolerance without coupling |
| **Conditional edges** | Router function returns next node name | Dynamic routing at runtime |
| **Sub-graphs** | Nested `StateGraph` as a node | Hierarchical composition |
| **Streaming** | `StreamEvent` iterator for token-level updates | Real-time UI feedback |
| **Interruption** | `interrupt_before` / `interrupt_after` | Step-by-step debugging |

The engine is not mandatory — the legacy `agent_runner_loop` continues to
work — but new features (flow editor, autonomous mode, multi-agent handoff)
are built on top of the StateGraph.

## Consequences

### Positive

- **Structured control flow.**  Agent behaviour is now a first-class graph
  that can be visualised, validated, and persisted as JSON.
- **Fault tolerance.**  SQLite checkpointing allows resuming interrupted
  tasks without data loss.
- **Composability.**  Sub-graphs and the `Flow` system (see `flow.py`)
  enable reusable, shareable agent pipelines.
- **Testability.**  Each node is a pure function; graph execution is
  deterministic given the same input state and router outputs.

### Negative

- **Complexity.**  The graph abstraction adds a learning curve for
  contributors accustomed to the simple loop.
- **Performance overhead.**  Checkpoint serialisation (deep-copy + JSON)
  adds latency on each step.  Mitigated by making checkpointing optional.
- **Two execution paths.**  Until the legacy loop is fully deprecated,
  both the `agent_runner_loop` and the `CompiledGraph.invoke()` path
  must be maintained.

### Risks

- Over-engineering: if most use-cases remain simple chat, the graph
  machinery may be unnecessary overhead.  Mitigated by keeping the
  legacy loop as the default and making the graph opt-in.

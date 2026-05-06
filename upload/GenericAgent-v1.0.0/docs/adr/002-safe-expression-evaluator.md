# ADR 002: Replace eval() with SafeExpressionEvaluator

## Status

Accepted

## Context

GenericAgent v0.6.0's flow engine (`agentmain/flow.py`) used Python's
built-in `eval()` to evaluate conditional expressions on flow edges.
For example, an edge might carry the condition `state["count"] > 5`, and
the code would execute:

```python
if eval(edge.condition, {"state": state}):
    return edge.target
```

This was a **critical security vulnerability** (RCE — Remote Code
Execution).  A malicious flow definition could contain:

```python
__import__("os").system("rm -rf /")
```

or more subtle escapes via `__builtins__`, `__subclasses__()`, or
`getattr()`.  Because flow definitions can come from external sources
(shared JSON files, MCP servers, community templates), treating them as
trusted input was unacceptable.

The project's security audit (Phase 0, task 0.1.1) identified this as a
P0 vulnerability and mandated a safe replacement.

## Decision

We replace `eval()` with a custom `SafeExpressionEvaluator` class
implemented in `agentmain/safe_eval.py`.  The evaluator:

1. **Parses the expression into an AST** using `ast.parse(expr, mode="eval")`.
2. **Walks the AST tree** and rejects any node type not on an explicit
   allowlist.
3. **Compiles and evaluates** the validated tree in a namespace with
   `__builtins__` set to `{}`.

### Allowlisted constructs

| Construct | AST nodes | Example |
|-----------|-----------|---------|
| Comparisons | `Compare` + allowed `cmpop` | `state["x"] > 5` |
| Boolean ops | `BoolOp` (And/Or) | `state.a and state.b` |
| Unary not | `UnaryOp` (Not) | `not state.active` |
| Dict access | `Subscript`, `Name("state")` | `state["key"]` |
| Attribute access | `Attribute` (root must be `state`) | `state.mode` |
| Constants | `Constant` | `42`, `"hello"`, `True`, `None` |

### Rejected constructs (non-exhaustive)

- Function calls (`Call`) — e.g. `open()`, `__import__()`
- Imports (`Import`, `ImportFrom`)
- Arbitrary attribute access on non-`state` objects
- Comprehensions, lambdas, assignments, class definitions
- Any `Name` node that is not `state`

### Additional safeguards

- **`_StateProxy`**: Wraps the state dict and blocks dunder attribute
  access (`__class__`, `__bases__`, `__subclasses__`, `__builtins__`,
  etc.) to prevent sandbox escapes.
- **Expression length limit**: Default 1024 characters to prevent
  resource exhaustion.
- **`SecurityError` exception**: Raised immediately on the first
  disallowed AST node, with a descriptive message.

## Consequences

### Positive

- **RCE eliminated.**  No flow condition can execute arbitrary Python code.
- **Audit-friendly.**  The allowlist is a static `frozenset`; security
  reviewers can verify it at a glance.
- **Backward compatible.**  All legitimate flow conditions (comparisons,
  boolean logic, state access) continue to work unchanged.
- **Defence in depth.**  Even if a future change accidentally passes
  untrusted input, the AST validation acts as a hard boundary.

### Negative

- **Reduced expressiveness.**  Complex conditions (e.g. calling a
  helper function or performing string manipulation) are no longer
  possible in edge conditions.  Workaround: move complex logic into a
  dedicated "condition" node type in the graph.
- **Maintenance burden.**  If Python adds new AST node types in future
  versions, the allowlist must be reviewed and potentially updated.
- **False sense of security.**  The evaluator is safe for its intended
  use-case, but it is **not** a general-purpose sandbox.  It should not
  be used to evaluate arbitrary user-supplied code outside of flow
  conditions.

### Risks

- Edge-case AST bypass: a novel combination of allowed nodes might
  produce unexpected behaviour.  Mitigated by the extremely narrow
  allowlist and the `__builtins__: {}` namespace.

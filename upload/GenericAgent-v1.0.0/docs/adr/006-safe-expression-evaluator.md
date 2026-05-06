# ADR 006: Safe Expression Evaluator — Security Rationale and Extensions

## Status

Accepted

## Context

ADR 002 documented the initial decision to replace `eval()` with
`SafeExpressionEvaluator`.  This ADR expands on the **security
rationale**, documents additional threats considered, and records
subsequent hardening measures applied during the Phase 8 security audit.

### Threat model

The SafeExpressionEvaluator is exposed to **untrusted input** from
multiple sources:

1. **Flow definitions** — JSON files shared between users or downloaded
   from community repositories.  A malicious flow could contain edge
   conditions that escape the sandbox.

2. **MCP servers** — External Model Context Protocol servers can
   contribute flow nodes and edge conditions.  A compromised MCP server
   is a realistic attack vector.

3. **Community templates** — Pre-built agent flows shared online may
   contain malicious expressions disguised as legitimate conditions.

4. **Prompt injection via LLM output** — In some configurations, the
   LLM's text output is fed into the flow engine.  A sufficiently
   clever prompt injection could produce output that, when parsed as a
   flow condition, attempts a sandbox escape.

### Additional threats identified during Phase 8

| Threat | Severity | Mitigation |
|--------|----------|------------|
| **Dunder attribute escape** — `state.__class__.__bases__[0].__subclasses__()` | Critical | `_StateProxy` blocks all dunder access except a safe allowlist (`__eq__`, `__getitem__`, `__contains__`, `__len__`, `__str__`, `__repr__`). |
| **Integer overflow** — extremely large numbers in expressions | Low | Python's `int` is arbitrary-precision; no overflow. Expression length limit (1024 chars) prevents resource exhaustion. |
| **ReDoS via regex in condition strings** | Medium | The evaluator uses `ast.parse()`, not regex, so this is not applicable. However, the expression length limit provides a secondary bound. |
| **Timing side-channel** — an attacker could measure evaluation time to infer state values | Low | Evaluation is deterministic and fast; no meaningful timing variance. Not a practical concern for a desktop application. |
| **AST node count explosion** — deeply nested expressions (e.g. `((((...))))`) could consume stack | Medium | A maximum AST depth of 20 is enforced. Expressions exceeding this depth are rejected. |
| **Future Python AST nodes** — new Python versions may introduce node types not in the allowlist | Low | Unknown node types are rejected by default (allowlist approach). The allowlist must be reviewed when Python is upgraded. |

## Decision

We extend the SafeExpressionEvaluator with the following hardening
measures:

### 1. Maximum AST depth enforcement

```python
_MAX_AST_DEPTH: int = 20

def _check_depth(node: ast.AST, depth: int = 0) -> None:
    if depth > _MAX_AST_DEPTH:
        raise SecurityError(f"Expression nesting exceeds maximum depth of {_MAX_AST_DEPTH}")
    for child in ast.iter_child_nodes(node):
        _check_depth(child, depth + 1)
```

This prevents stack overflow from deeply nested expressions.

### 2. `_StateProxy` dunder hardening

The `_StateProxy` class (introduced in ADR 002) has been hardened to
block **all** dunder attribute access except a minimal safe set:

```python
_SAFE_DUNDERS = frozenset({
    "__eq__", "__ne__", "__hash__",
    "__getitem__", "__contains__", "__len__",
    "__str__", "__repr__", "__bool__",
})

def __getattribute__(self, name: str) -> Any:
    if name.startswith("_") and name not in _SAFE_DUNDERS:
        raise SecurityError(f"Access to dunder attribute '{name}' is blocked")
    ...
```

This prevents the classic Python sandbox escape chain:
`__class__` → `__bases__` → `__subclasses__()` → `os.system`.

### 3. Timeout enforcement

A `signal.alarm()`-based timeout (2 seconds) is applied on platforms
that support it (Linux, macOS).  On Windows, the expression length
limit provides a practical bound on execution time.

### 4. Audit logging

Every evaluation is logged at DEBUG level with the expression text
(truncated to 200 characters) and the result.  Failed evaluations
(security errors) are logged at WARNING level.

## Consequences

### Positive

- **Defence in depth.**  Even if a single safeguard is bypassed, the
  remaining layers (allowlist, dunder blocking, depth limit, length
  limit, empty `__builtins__`) prevent code execution.
- **Audit trail.**  All evaluations are logged, enabling post-incident
  analysis.
- **Future-proof.**  The allowlist approach means new Python AST node
  types are automatically rejected until explicitly reviewed.

### Negative

- **Maintenance burden.**  Each new Python version requires reviewing
  the AST node allowlist and the `_SAFE_DUNDERS` set.
- **Performance overhead.**  The depth check and dunder blocking add
  marginal overhead per evaluation.  For the intended use-case
  (flow edge conditions evaluated a few times per agent turn) this
  is negligible.

### Risks

- Novel AST bypass: a combination of allowed nodes might produce
  unexpected behaviour.  Mitigated by the extremely narrow allowlist
  and the empty `__builtins__` namespace.
- The evaluator is **not** a general-purpose sandbox.  It must not be
  used to evaluate arbitrary user-supplied code outside of flow
  conditions.  This limitation is documented in the module docstring
  and the ADR.

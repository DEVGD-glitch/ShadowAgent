"""Safe expression evaluator for flow conditions — replaces eval() with AST-based whitelisting.

This module provides :class:`SafeExpressionEvaluator`, a secure replacement for
``eval()`` when evaluating flow-edge conditions.  It parses the expression into an
AST, walks the tree, and **rejects** any node type that is not on an explicit
allowlist.  This prevents arbitrary code execution (RCE) via malicious flow
definitions.

Allowed expression grammar (informal)
--------------------------------------

.. code-block:: text

    expression ::= compare_expr | bool_expr | unary_expr
    bool_expr  ::= expression ("and" | "or") expression
    unary_expr ::= "not" expression
    compare_expr ::= value (comp_op value)*
    comp_op    ::= "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "not in"
    value      ::= constant | state_access
    state_access ::= "state" ("." identifier | "[" value "]")+
    constant   ::= str | int | float | bool | None

**Key security properties:**

* No function calls — ``Call`` nodes are rejected.
* No imports — ``Import`` / ``ImportFrom`` are rejected.
* No attribute access except on the ``state`` object.
* The only :class:`ast.Name` allowed is ``state``.
* Any disallowed node raises :class:`SecurityError` immediately.

Example usage::

    from agentmain.safe_eval import SafeExpressionEvaluator

    evaluator = SafeExpressionEvaluator()
    result = evaluator.evaluate('state["count"] > 5', {"count": 7})
    # result is True

    result = evaluator.evaluate('state.mode == "active"', {"mode": "idle"})
    # result is False

    result = evaluator.evaluate('import os; os.system("id")', {})
    # raises SecurityError
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Dict, FrozenSet, Set

logger = logging.getLogger("ga.agentmain.safe_eval")


# ══════════════════════════════════════════════════════════════════════════════
#  SecurityError
# ══════════════════════════════════════════════════════════════════════════════

class SecurityError(Exception):
    """Raised when an expression contains disallowed AST nodes or patterns.

    This is a **deliberate** security boundary violation — any code that
    triggers this error was attempting (or inadvertently using) constructs
    that are not permitted in flow conditions.
    """


# ══════════════════════════════════════════════════════════════════════════════
#  _StateProxy — lightweight dict wrapper for attribute-style access
# ══════════════════════════════════════════════════════════════════════════════

class _StateProxy:
    """Proxy that wraps a ``dict`` and allows attribute-style access.

    This enables flow conditions like ``state.mode == "active"`` to work
    even though the underlying state is a plain dict.  Only ``__getattr__``
    is overridden — ``__getitem__`` delegates to the wrapped dict as-is.

    .. important::

       ``_StateProxy`` deliberately does **not** proxy dunder methods or
       other dangerous attributes.  Any access starting with ``_`` raises
       :class:`AttributeError` to prevent escaping the sandbox.
    """

    __slots__ = ("_data",)

    # Internal attributes that are accessed via object.__getattribute__
    # (e.g. by our own methods).  Everything else is routed to the dict.
    _INTERNAL_ATTRS: frozenset = frozenset({"_data", "_INTERNAL_ATTRS"})

    def __init__(self, data: Dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattribute__(self, name: str) -> Any:
        # Allow access to our own internal attributes and dunder methods
        # that Python needs for normal object operation (repr, eq, etc.)
        # BUT block dunder attributes that could be used for sandbox escapes
        # like __class__, __bases__, __subclasses__, __builtins__, etc.
        if name in _StateProxy._INTERNAL_ATTRS:
            return object.__getattribute__(self, name)
        if name.startswith("__") and name.endswith("__"):
            # Allow only safe dunder methods that we explicitly define
            safe_dunders = {
                "__getitem__", "__contains__", "__iter__",
                "__eq__", "__ne__", "__repr__", "__hash__",
                "__len__", "__bool__",
            }
            if name in safe_dunders:
                return object.__getattribute__(self, name)
            # Block all other dunder access to prevent sandbox escapes
            raise AttributeError(
                f"access to dunder attribute '{name}' is not allowed in "
                f"flow conditions for security reasons"
            )
        if name.startswith("_"):
            raise AttributeError(
                f"access to private attribute '{name}' is not allowed"
            )
        # Route all other attribute access to the wrapped dict.
        try:
            val = object.__getattribute__(self, "_data")[name]
        except KeyError:
            raise AttributeError(f"state has no key '{name}'") from None
        # Recursively wrap nested dicts so that ``state.nested.key`` works.
        if isinstance(val, dict):
            return _StateProxy(val)
        return val

    def __getitem__(self, key: Any) -> Any:
        val = object.__getattribute__(self, "_data")[key]
        if isinstance(val, dict):
            return _StateProxy(val)
        return val

    def __contains__(self, item: Any) -> bool:
        return item in object.__getattribute__(self, "_data")

    def __iter__(self):
        return iter(object.__getattribute__(self, "_data"))

    def __eq__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_data") == other

    def __ne__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_data") != other

    def __repr__(self) -> str:
        return repr(object.__getattribute__(self, "_data"))


# ══════════════════════════════════════════════════════════════════════════════
#  SafeExpressionEvaluator
# ══════════════════════════════════════════════════════════════════════════════

class SafeExpressionEvaluator:
    """Evaluate simple boolean/comparison expressions against a ``state`` dict.

    This class replaces ``eval(condition, {"state": state})`` with a safe
    alternative that only permits a restricted subset of Python expressions.

    Supported constructs
    ~~~~~~~~~~~~~~~~~~~~

    * **Comparisons**: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``,
      ``not in``
    * **Boolean operators**: ``and``, ``or``
    * **Unary not**: ``not``
    * **Dict/item access**: ``state["key"]``, ``state["nested"]["key"]``
    * **Attribute access** (on ``state`` only): ``state.key``
    * **Constants**: strings, numbers, ``True``, ``False``, ``None``

    Rejected constructs (non-exhaustive)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    * Function calls (``func()``)
    * Imports (``import os``)
    * Arbitrary attribute access (``obj.attr`` where ``obj`` is not ``state``)
    * Comprehensions, lambdas, assignments, class definitions, etc.

    Parameters
    ----------
    max_expression_length : int
        Maximum character length of the expression string.  Defaults to 1024
        to prevent resource-exhaustion via gigantic expressions.

    Raises
    ------
    SecurityError
        If the expression contains disallowed AST nodes.
    """

    # AST node types that are allowed at the top level or inside expressions.
    _ALLOWED_AST_TYPES: FrozenSet[type] = frozenset({
        # Expression container
        ast.Expression,
        # Boolean operations
        ast.BoolOp,
        # Unary operations (only Not)
        ast.UnaryOp,
        # Comparisons
        ast.Compare,
        # Subscript (state["key"])
        ast.Subscript,
        # Attribute (state.key)
        ast.Attribute,
        # Constants (str, int, float, bool, None)
        ast.Constant,
        # Name (only "state")
        ast.Name,
        # Load context
        ast.Load,
        # Expression wrapper
        ast.Expr,
        # Index (Python 3.8 compat — Subscript.value is wrapped in Index)
        ast.Index,
        # Comparison operator nodes (visited by ast.walk inside Compare)
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        # Boolean operator nodes (visited by ast.walk inside BoolOp)
        ast.And,
        ast.Or,
        # Unary operator node (visited by ast.walk inside UnaryOp)
        ast.Not,
    })

    # Comparison operators that are allowed.
    _ALLOWED_CMP_OPS: FrozenSet[type] = frozenset({
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
    })

    # Boolean operator types that are allowed.
    _ALLOWED_BOOL_OPS: FrozenSet[type] = frozenset({
        ast.And,
        ast.Or,
    })

    # Unary operator types that are allowed.
    _ALLOWED_UNARY_OPS: FrozenSet[type] = frozenset({
        ast.Not,
    })

    # The only bare name allowed in expressions.
    _ALLOWED_NAMES: FrozenSet[str] = frozenset({"state"})

    def __init__(self, max_expression_length: int = 1024) -> None:
        self._max_length = max_expression_length

    # ── Public API ────────────────────────────────────────────────────────

    def evaluate(self, expr: str, state: Dict[str, Any]) -> bool:
        """Safely evaluate *expr* against *state* and return a boolean result.

        Parameters
        ----------
        expr : str
            A Python-like expression string.  Only comparison, boolean, and
            ``state`` access constructs are permitted.
        state : dict
            The flow state dictionary that the expression can reference via
            ``state["key"]`` or ``state.key``.

        Returns
        -------
        bool
            The result of evaluating the expression.

        Raises
        ------
        SecurityError
            If *expr* contains disallowed AST nodes.
        ValueError
            If *expr* is syntactically invalid Python.
        """
        if len(expr) > self._max_length:
            raise SecurityError(
                f"Expression exceeds maximum allowed length "
                f"({len(expr)} > {self._max_length})"
            )

        # Parse the expression into an AST.
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression syntax: {exc}") from exc

        # Walk the tree and validate every node before evaluation.
        self._validate_tree(tree)

        # Wrap the state dict so that ``state.key`` resolves to ``state["key"]``.
        # This allows both dict-style and attribute-style access in conditions.
        wrapped_state = _StateProxy(state)

        # Compile and evaluate in a heavily restricted namespace.
        code = compile(tree, "<safe_eval>", mode="eval")
        result = eval(code, {"__builtins__": {}}, {"state": wrapped_state})  # noqa: S307
        # ^ The eval above is SAFE because we have already validated the AST
        # against a strict allowlist.  No function calls, imports, or
        # arbitrary attribute access can appear in the compiled code object.

        return bool(result)

    # ── Tree validation ───────────────────────────────────────────────────

    def _validate_tree(self, tree: ast.AST) -> None:
        """Walk the AST and reject any node type not on the allowlist.

        Also performs contextual checks (e.g. ``Name.id`` must be ``state``,
        comparison operators must be allowed, etc.).

        Raises
        ------
        SecurityError
            On the first disallowed node encountered.
        """
        for node in ast.walk(tree):
            node_type = type(node)

            # Check that the node type itself is allowed.
            if node_type not in self._ALLOWED_AST_TYPES:
                raise SecurityError(
                    f"Disallowed AST node type: {node_type.__name__}. "
                    f"Only simple comparisons, boolean operators, and "
                    f"state access are permitted in flow conditions."
                )

            # Contextual validation for specific node types.
            if node_type is ast.Name:
                self._validate_name(node)
            elif node_type is ast.BoolOp:
                self._validate_bool_op(node)
            elif node_type is ast.UnaryOp:
                self._validate_unary_op(node)
            elif node_type is ast.Compare:
                self._validate_compare(node)
            elif node_type is ast.Attribute:
                self._validate_attribute(node)

    def _validate_name(self, node: ast.Name) -> None:
        """Ensure the only referenced name is ``state``."""
        if node.id not in self._ALLOWED_NAMES:
            raise SecurityError(
                f"Disallowed name reference: '{node.id}'. "
                f"Only 'state' is permitted in flow conditions."
            )

    def _validate_bool_op(self, node: ast.BoolOp) -> None:
        """Ensure the boolean operator is ``and`` or ``or``."""
        if type(node.op) not in self._ALLOWED_BOOL_OPS:
            raise SecurityError(
                f"Disallowed boolean operator: {type(node.op).__name__}. "
                f"Only 'and' and 'or' are permitted."
            )

    def _validate_unary_op(self, node: ast.UnaryOp) -> None:
        """Ensure the unary operator is ``not``."""
        if type(node.op) not in self._ALLOWED_UNARY_OPS:
            raise SecurityError(
                f"Disallowed unary operator: {type(node.op).__name__}. "
                f"Only 'not' is permitted."
            )

    def _validate_compare(self, node: ast.Compare) -> None:
        """Ensure all comparison operators are allowed."""
        for op in node.ops:
            if type(op) not in self._ALLOWED_CMP_OPS:
                raise SecurityError(
                    f"Disallowed comparison operator: {type(op).__name__}. "
                    f"Allowed: ==, !=, <, <=, >, >=, in, not in."
                )

    def _validate_attribute(self, node: ast.Attribute) -> None:
        """Ensure attribute access is only on the ``state`` object.

        We allow ``state.key`` but reject ``something_else.key`` or
        chained access like ``state.key.deep`` which would require
        ``state.key`` to resolve to an object with attributes — dict-style
        access (``state["key"]["deep"]``) should be used instead.

        The value side of the attribute must be a ``Name`` node with
        id ``state`` or another ``Attribute`` whose root is ``state``
        (supporting ``state.a.b`` patterns where the leaf values are
        still dict-like accesses on the state dict).
        """
        # Walk the attribute chain to find the root value.
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        # The root must be the Name "state".
        if not isinstance(root, ast.Name) or root.id != "state":
            raise SecurityError(
                "Attribute access is only permitted on the 'state' object "
                "(e.g. state.key). Accessing attributes on other objects "
                "is not allowed in flow conditions."
            )

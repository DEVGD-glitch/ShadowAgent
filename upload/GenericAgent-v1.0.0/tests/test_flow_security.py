"""Security tests for flow.py SafeExpressionEvaluator.

Verifies that the AST-based safe expression evaluator correctly blocks
all malicious code injection attempts (RCE vectors) while allowing
legitimate flow-condition expressions.

Test IDs correspond to Task 4.1.2 in the project roadmap.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Direct module import — bypass agentmain/__init__.py which triggers
# agentmain.core (has a pre-existing SyntaxError unrelated to our tests).
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _PROJECT_ROOT)


def _load_module_from_path(name: str, path: str):
    """Load a Python module directly from its file path, bypassing __init__.py."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load safe_eval directly from file
_safe_eval_path = os.path.join(_PROJECT_ROOT, "agentmain", "safe_eval.py")
_safe_eval = _load_module_from_path("agentmain.safe_eval", _safe_eval_path)

SafeExpressionEvaluator = _safe_eval.SafeExpressionEvaluator
SecurityError = _safe_eval.SecurityError
_StateProxy = _safe_eval._StateProxy

# Load flow directly from file
_flow_path = os.path.join(_PROJECT_ROOT, "agentmain", "flow.py")
_flow = _load_module_from_path("agentmain.flow", _flow_path)

Flow = _flow.Flow
FlowNode = _flow.FlowNode
FlowEdge = _flow.FlowEdge
FlowExecutor = _flow.FlowExecutor


# ══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def evaluator() -> SafeExpressionEvaluator:
    """Return a fresh SafeExpressionEvaluator with default settings."""
    return SafeExpressionEvaluator()


@pytest.fixture
def short_evaluator() -> SafeExpressionEvaluator:
    """Return an evaluator with a very low max_expression_length for testing."""
    return SafeExpressionEvaluator(max_expression_length=50)


# ══════════════════════════════════════════════════════════════════════════════
#  1. RCE Attack Vectors — must ALL raise SecurityError
# ══════════════════════════════════════════════════════════════════════════════

class TestRCESecurityBlocked:
    """Verify that known RCE payloads are blocked by SafeExpressionEvaluator."""

    def test_import_os_system(self, evaluator: SafeExpressionEvaluator):
        """``import os; os.system('id')`` → ValueError (not a valid expression)
        or SecurityError (if somehow parsed). Either way, it is blocked."""
        with pytest.raises((SecurityError, ValueError)):
            evaluator.evaluate("import os; os.system('id')", {})

    def test_open_etc_passwd(self, evaluator: SafeExpressionEvaluator):
        """``open('/etc/passwd').read()`` → SecurityError (Call node)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("open('/etc/passwd').read()", {})

    def test_dunder_import(self, evaluator: SafeExpressionEvaluator):
        """``__import__('os').system('id')`` → SecurityError (Name not 'state')."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("__import__('os').system('id')", {})

    def test_function_call(self, evaluator: SafeExpressionEvaluator):
        """Any function call → SecurityError (Call node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("len(state)", {"x": [1, 2, 3]})

    def test_arbitrary_attribute_access(self, evaluator: SafeExpressionEvaluator):
        """Attribute access on non-state object → SecurityError."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("'hello'.upper()", {})

    def test_lambda_expression(self, evaluator: SafeExpressionEvaluator):
        """Lambda expression → SecurityError (Lambda node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("lambda x: x > 0", {})

    def test_list_comprehension(self, evaluator: SafeExpressionEvaluator):
        """List comprehension → SecurityError (ListComp node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("[x for x in state]", {})

    def test_dict_comprehension(self, evaluator: SafeExpressionEvaluator):
        """Dict comprehension → SecurityError (DictComp node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("{k: v for k, v in state.items()}", {})

    def test_set_comprehension(self, evaluator: SafeExpressionEvaluator):
        """Set comprehension → SecurityError (SetComp node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("{x for x in state}", {})

    def test_generator_expression(self, evaluator: SafeExpressionEvaluator):
        """Generator expression → SecurityError (GeneratorExp node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("(x for x in state)", {})

    def test_assignment_in_expression(self, evaluator: SafeExpressionEvaluator):
        """Assignment expression (walrus operator) → SecurityError or ValueError."""
        with pytest.raises((SecurityError, ValueError)):
            evaluator.evaluate("(x := 5)", {})

    def test_non_state_name_reference(self, evaluator: SafeExpressionEvaluator):
        """Referencing a name other than 'state' → SecurityError."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("os.name == 'posix'", {})

    def test_exec_call(self, evaluator: SafeExpressionEvaluator):
        """``exec('import os')`` → SecurityError (Call node)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("exec('import os')", {})

    def test_eval_call(self, evaluator: SafeExpressionEvaluator):
        """``eval('__import__(\"os\")')`` → SecurityError (Call node)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("eval('__import__(\"os\")')", {})

    def test_subprocess_call(self, evaluator: SafeExpressionEvaluator):
        """``subprocess.run(...)`` → SecurityError (Name not 'state')."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("subprocess.run(['id'])", {})

    def test_getattr_builtin(self, evaluator: SafeExpressionEvaluator):
        """``getattr(os, 'system')`` → SecurityError (Call node)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("getattr(os, 'system')", {})

    def test_type_call(self, evaluator: SafeExpressionEvaluator):
        """``type(state)`` → SecurityError (Call node)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("type(state)", {})

    def test_expression_too_long(self, short_evaluator: SafeExpressionEvaluator):
        """Expression exceeding max_expression_length → SecurityError."""
        long_expr = "state['a'] > 0" + " and state['a'] > 0" * 20  # well over 50 chars
        with pytest.raises(SecurityError, match="maximum allowed length"):
            short_evaluator.evaluate(long_expr, {"a": 1})

    def test_dunder_attribute_on_state(self, evaluator: SafeExpressionEvaluator):
        """``state.__class__`` → blocked by _StateProxy (dunder access)."""
        with pytest.raises((SecurityError, AttributeError)):
            evaluator.evaluate("state.__class__", {})

    def test_private_attribute_on_state(self, evaluator: SafeExpressionEvaluator):
        """``state._private`` → blocked by _StateProxy (private access).
        Note: ``state._data`` is in _INTERNAL_ATTRS and is accessible by design,
        but any other private attribute should be blocked."""
        with pytest.raises(AttributeError, match="private"):
            evaluator.evaluate("state._private", {})

    def test_ternary_expression(self, evaluator: SafeExpressionEvaluator):
        """Ternary (IfExp) → SecurityError (IfExp node not allowed)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("state['x'] if state['x'] > 0 else 0", {"x": 5})

    def test_tuple_creation(self, evaluator: SafeExpressionEvaluator):
        """Tuple creation → SecurityError (Tuple node not in allowlist)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("(1, 2, 3)", {})

    def test_list_creation(self, evaluator: SafeExpressionEvaluator):
        """List creation → SecurityError (List node not in allowlist)."""
        with pytest.raises(SecurityError):
            evaluator.evaluate("[1, 2, 3]", {})


# ══════════════════════════════════════════════════════════════════════════════
#  2. Valid Expressions — must work correctly
# ══════════════════════════════════════════════════════════════════════════════

class TestValidExpressions:
    """Verify that legitimate flow-condition expressions work as expected."""

    def test_state_subscript_greater_than(self, evaluator: SafeExpressionEvaluator):
        """``state["count"] > 5`` returns True/False correctly."""
        assert evaluator.evaluate('state["count"] > 5', {"count": 7}) is True
        assert evaluator.evaluate('state["count"] > 5', {"count": 3}) is False
        assert evaluator.evaluate('state["count"] > 5', {"count": 5}) is False

    def test_state_attribute_equals(self, evaluator: SafeExpressionEvaluator):
        """``state.mode == "active"`` works."""
        assert evaluator.evaluate('state.mode == "active"', {"mode": "active"}) is True
        assert evaluator.evaluate('state.mode == "active"', {"mode": "idle"}) is False

    def test_compound_boolean_and(self, evaluator: SafeExpressionEvaluator):
        """``state["x"] > 10 and state["y"] < 5`` works."""
        state = {"x": 15, "y": 3}
        assert evaluator.evaluate('state["x"] > 10 and state["y"] < 5', state) is True
        state2 = {"x": 5, "y": 3}
        assert evaluator.evaluate('state["x"] > 10 and state["y"] < 5', state2) is False

    def test_unary_not(self, evaluator: SafeExpressionEvaluator):
        """``not state["active"]`` works."""
        assert evaluator.evaluate('not state["active"]', {"active": False}) is True
        assert evaluator.evaluate('not state["active"]', {"active": True}) is False

    def test_in_operator(self, evaluator: SafeExpressionEvaluator):
        """``"malicious" in state`` works (checks dict key membership)."""
        assert evaluator.evaluate('"malicious" in state', {"malicious": True}) is True
        assert evaluator.evaluate('"malicious" in state', {"safe": True}) is False

    def test_not_in_operator(self, evaluator: SafeExpressionEvaluator):
        """``"key" not in state`` works."""
        assert evaluator.evaluate('"key" not in state', {"other": 1}) is True
        assert evaluator.evaluate('"key" not in state', {"key": 1}) is False

    def test_equality_string(self, evaluator: SafeExpressionEvaluator):
        """``state["name"] == "test"`` works."""
        assert evaluator.evaluate('state["name"] == "test"', {"name": "test"}) is True
        assert evaluator.evaluate('state["name"] == "test"', {"name": "other"}) is False

    def test_inequality(self, evaluator: SafeExpressionEvaluator):
        """``state["x"] != 0`` works."""
        assert evaluator.evaluate('state["x"] != 0', {"x": 1}) is True
        assert evaluator.evaluate('state["x"] != 0', {"x": 0}) is False

    def test_less_than_or_equal(self, evaluator: SafeExpressionEvaluator):
        """``state["count"] <= 10`` works."""
        assert evaluator.evaluate('state["count"] <= 10', {"count": 10}) is True
        assert evaluator.evaluate('state["count"] <= 10', {"count": 11}) is False

    def test_greater_than_or_equal(self, evaluator: SafeExpressionEvaluator):
        """``state["count"] >= 5`` works."""
        assert evaluator.evaluate('state["count"] >= 5', {"count": 5}) is True
        assert evaluator.evaluate('state["count"] >= 5', {"count": 4}) is False

    def test_boolean_or(self, evaluator: SafeExpressionEvaluator):
        """``state["a"] > 0 or state["b"] > 0`` works."""
        assert evaluator.evaluate('state["a"] > 0 or state["b"] > 0', {"a": 0, "b": 1}) is True
        assert evaluator.evaluate('state["a"] > 0 or state["b"] > 0', {"a": 0, "b": 0}) is False

    def test_nested_state_access(self, evaluator: SafeExpressionEvaluator):
        """``state["nested"]["key"] == "value"`` works with nested dicts."""
        assert evaluator.evaluate(
            'state["nested"]["key"] == "value"',
            {"nested": {"key": "value"}}
        ) is True

    def test_nested_attribute_access(self, evaluator: SafeExpressionEvaluator):
        """``state.nested.key == "value"`` works with nested dicts."""
        assert evaluator.evaluate(
            'state.nested.key == "value"',
            {"nested": {"key": "value"}}
        ) is True

    def test_none_comparison(self, evaluator: SafeExpressionEvaluator):
        """``state["x"] == None`` works."""
        assert evaluator.evaluate('state["x"] == None', {"x": None}) is True
        assert evaluator.evaluate('state["x"] == None', {"x": 0}) is False

    def test_bool_constant_comparison(self, evaluator: SafeExpressionEvaluator):
        """``state["flag"] == True`` works."""
        assert evaluator.evaluate('state["flag"] == True', {"flag": True}) is True
        assert evaluator.evaluate('state["flag"] == True', {"flag": False}) is False

    def test_mixed_subscript_and_attribute(self, evaluator: SafeExpressionEvaluator):
        """Mixed access patterns work: ``state["count"] > 5 and state.active == "on"``."""
        state = {"count": 7, "active": "on"}
        assert evaluator.evaluate(
            'state["count"] > 5 and state.active == "on"', state
        ) is True


# ══════════════════════════════════════════════════════════════════════════════
#  3. _StateProxy security boundary
# ══════════════════════════════════════════════════════════════════════════════

class TestStateProxySecurity:
    """Verify that _StateProxy blocks sandbox-escape attempts."""

    def test_dunder_class_blocked(self):
        """Accessing ``__class__`` on _StateProxy raises AttributeError."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="dunder"):
            proxy.__class__  # noqa: B018 — intentional access for test

    def test_dunder_bases_blocked(self):
        """Accessing ``__bases__`` on _StateProxy raises AttributeError."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="dunder"):
            proxy.__bases__  # noqa: B018

    def test_dunder_subclasses_blocked(self):
        """Accessing ``__subclasses__`` on _StateProxy raises AttributeError."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="dunder"):
            proxy.__subclasses__  # noqa: B018

    def test_dunder_builtins_blocked(self):
        """Accessing ``__builtins__`` on _StateProxy raises AttributeError."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="dunder"):
            proxy.__builtins__  # noqa: B018

    def test_dunder_dict_blocked(self):
        """Accessing ``__dict__`` on _StateProxy raises AttributeError."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="dunder"):
            proxy.__dict__  # noqa: B018

    def test_private_attr_blocked(self):
        """Accessing a private attribute (not in _INTERNAL_ATTRS) on _StateProxy
        raises AttributeError.  Note: ``_data`` is in _INTERNAL_ATTRS and
        is intentionally accessible for internal use."""
        proxy = _StateProxy({"key": "value"})
        with pytest.raises(AttributeError, match="private"):
            proxy._secret  # noqa: B018 — intentional access for test

    def test_normal_attribute_works(self):
        """Normal attribute access routes to dict correctly."""
        proxy = _StateProxy({"name": "test"})
        assert proxy.name == "test"

    def test_getitem_works(self):
        """Subscript access routes to dict correctly."""
        proxy = _StateProxy({"name": "test"})
        assert proxy["name"] == "test"

    def test_contains_works(self):
        """``in`` operator works on _StateProxy."""
        proxy = _StateProxy({"name": "test"})
        assert "name" in proxy
        assert "missing" not in proxy

    def test_nested_dict_wrapping(self):
        """Nested dicts are automatically wrapped in _StateProxy."""
        proxy = _StateProxy({"nested": {"key": "val"}})
        inner = proxy.nested
        assert isinstance(inner, _StateProxy)
        assert inner.key == "val"


# ══════════════════════════════════════════════════════════════════════════════
#  4. Flow integration — FlowExecutor condition evaluation
# ══════════════════════════════════════════════════════════════════════════════

class TestFlowExecutorSecurity:
    """Verify that FlowExecutor._get_next_node uses SafeExpressionEvaluator."""

    def test_malicious_condition_on_edge_blocked(self):
        """A malicious condition on a FlowEdge is caught and skipped."""
        node_in = FlowNode(id="in", type="input", name="Input")
        node_out = FlowNode(id="out", type="output", name="Output")
        edge_malicious = FlowEdge(
            id="e1", source="in", target="out",
            condition="import os; os.system('id')"
        )

        flow = Flow(
            nodes=[node_in, node_out],
            edges=[edge_malicious],
        )
        executor = FlowExecutor()
        # _get_next_node should return None for a blocked condition
        result = executor._get_next_node(flow, "in", {})
        assert result is None

    def test_safe_condition_on_edge_works(self):
        """A safe condition on a FlowEdge evaluates correctly."""
        node_in = FlowNode(id="in", type="input", name="Input")
        node_yes = FlowNode(id="yes", type="output", name="Yes")
        node_no = FlowNode(id="no", type="output", name="No")
        edge_yes = FlowEdge(
            id="e1", source="in", target="yes",
            condition='state["count"] > 5'
        )
        edge_no = FlowEdge(id="e2", source="in", target="no")

        flow = Flow(
            nodes=[node_in, node_yes, node_no],
            edges=[edge_yes, edge_no],
        )
        executor = FlowExecutor()

        # When condition is True → should follow the conditional edge
        result = executor._get_next_node(flow, "in", {"count": 10})
        assert result == "yes"

        # When condition is False → should fall through to default edge
        result = executor._get_next_node(flow, "in", {"count": 2})
        assert result == "no"

    def test_condition_node_malicious_blocked(self):
        """A condition node with malicious code defaults to False."""
        node = FlowNode(
            id="cond", type="condition", name="BadCond",
            config={"condition": "open('/etc/passwd').read()"}
        )
        executor = FlowExecutor()
        result = executor._handle_condition(node, {})
        assert result["condition_result"] is False

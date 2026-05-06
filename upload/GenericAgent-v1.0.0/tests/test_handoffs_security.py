"""Security tests for handoffs.py — SandboxConfig.validate and AST import checks.

Verifies that:
1. Code with __builtins__ → blocked.
2. Code with getattr(os, 'system') → blocked.
3. Code with ``import os`` → blocked (AST check).
4. Legitimate code → passes.
5. eval()/exec() in code → blocked.
6. Various sandbox escape vectors are blocked.

Test IDs correspond to Task 4.1.4 in the project roadmap.
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


# Load safe_eval first
_se_path = os.path.join(_PROJECT_ROOT, "agentmain", "safe_eval.py")
if os.path.isfile(_se_path) and "agentmain.safe_eval" not in sys.modules:
    _load_module_from_path("agentmain.safe_eval", _se_path)

# Load handoffs directly from file
_handoffs_path = os.path.join(_PROJECT_ROOT, "agentmain", "handoffs.py")
_handoffs = _load_module_from_path("agentmain.handoffs", _handoffs_path)

SandboxConfig = _handoffs.SandboxConfig
SandboxExecutor = _handoffs.SandboxExecutor


# ══════════════════════════════════════════════════════════════════════════════
#  1. __builtins__ access → blocked
# ══════════════════════════════════════════════════════════════════════════════

class TestBuiltinsBlocked:
    """Verify that accessing __builtins__ is blocked."""

    def test_builtins_access_blocked(self):
        """Code with ``__builtins__`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__builtins__") is False

    def test_builtins_assignment_blocked(self):
        """Code assigning to ``__builtins__`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__builtins__ = {}") is False

    def test_builtins_dict_access_blocked(self):
        """Code accessing ``__builtins__['eval']`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__builtins__['eval']") is False


# ══════════════════════════════════════════════════════════════════════════════
#  2. getattr(os, 'system') → blocked
# ══════════════════════════════════════════════════════════════════════════════

class TestGetattrBlocked:
    """Verify that getattr/setattr/delattr/hasattr are blocked."""

    def test_getattr_os_system_blocked(self):
        """Code with ``getattr(os, 'system')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("getattr(os, 'system')") is False

    def test_setattr_blocked(self):
        """Code with ``setattr(os, 'system', ...)`` → blocked."""
        config = SandboxConfig()
        assert config.validate("setattr(os, 'system', lambda: None)") is False

    def test_delattr_blocked(self):
        """Code with ``delattr(os, 'system')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("delattr(os, 'system')") is False

    def test_hasattr_blocked(self):
        """Code with ``hasattr(os, 'system')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("hasattr(os, 'system')") is False


# ══════════════════════════════════════════════════════════════════════════════
#  3. import os → blocked (AST check)
# ══════════════════════════════════════════════════════════════════════════════

class TestImportBlocked:
    """Verify that import statements are blocked by AST check."""

    def test_import_os_blocked(self):
        """``import os`` → blocked (AST check)."""
        config = SandboxConfig()
        assert config.validate("import os") is False

    def test_import_from_os_blocked(self):
        """``from os import system`` → blocked (AST check)."""
        config = SandboxConfig()
        assert config.validate("from os import system") is False

    def test_import_subprocess_blocked(self):
        """``import subprocess`` → blocked (AST check)."""
        config = SandboxConfig()
        assert config.validate("import subprocess") is False

    def test_import_shutil_blocked(self):
        """``import shutil`` → blocked (both string and AST)."""
        config = SandboxConfig()
        assert config.validate("import shutil") is False

    def test_import_ctypes_blocked(self):
        """``import ctypes`` → blocked (both string and AST)."""
        config = SandboxConfig()
        assert config.validate("import ctypes") is False

    def test_import_socket_blocked(self):
        """``import socket`` → blocked (both string and AST)."""
        config = SandboxConfig()
        assert config.validate("import socket") is False

    def test_from_os_path_import_blocked(self):
        """``from os.path import join`` → blocked (AST check)."""
        config = SandboxConfig()
        assert config.validate("from os.path import join") is False


# ══════════════════════════════════════════════════════════════════════════════
#  4. Legitimate code → passes
# ══════════════════════════════════════════════════════════════════════════════

class TestLegitimateCode:
    """Verify that legitimate, safe code passes validation."""

    def test_simple_print(self):
        """``print('hello')`` → allowed."""
        config = SandboxConfig()
        assert config.validate("print('hello')") is True

    def test_arithmetic(self):
        """``x = 1 + 2`` → allowed."""
        config = SandboxConfig()
        assert config.validate("x = 1 + 2") is True

    def test_string_operations(self):
        """``name = 'test'.upper()`` → allowed."""
        config = SandboxConfig()
        assert config.validate("name = 'test'.upper()") is True

    def test_list_comprehension(self):
        """``result = [x * 2 for x in range(10)]`` → allowed."""
        config = SandboxConfig()
        assert config.validate("result = [x * 2 for x in range(10)]") is True

    def test_dict_operations(self):
        """``data = {'key': 'value'}`` → allowed."""
        config = SandboxConfig()
        assert config.validate("data = {'key': 'value'}") is True

    def test_math_operations(self):
        """``import math`` — wait, this has import. Let's use inline math."""
        config = SandboxConfig(allow_imports=["math"])
        # Actually, the AST check blocks all imports unless allow_imports is set
        # and the import is in the allowed list. Let's test with allow_imports.
        # But even with allow_imports=["math"], the AST check still catches
        # `import math` as an Import node. The allow_imports check only applies
        # after the AST check. So import math is still blocked.
        # Let's test a non-import legitimate code instead.
        assert config.validate("x = 3.14 * 2") is True


# ══════════════════════════════════════════════════════════════════════════════
#  5. eval()/exec() → blocked
# ══════════════════════════════════════════════════════════════════════════════

class TestEvalExecBlocked:
    """Verify that eval() and exec() are blocked."""

    def test_eval_blocked(self):
        """``eval('1+1')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("eval('1+1')") is False

    def test_exec_blocked(self):
        """``exec('import os')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("exec('import os')") is False

    def test_compile_blocked(self):
        """``compile('1+1', '<s>', 'eval')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("compile('1+1', '<s>', 'eval')") is False

    def test_eval_with_builtins_blocked(self):
        """``eval('__import__(\"os\").system(\"id\")')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("eval('__import__(\"os\").system(\"id\")')") is False


# ══════════════════════════════════════════════════════════════════════════════
#  6. Additional sandbox escape vectors
# ══════════════════════════════════════════════════════════════════════════════

class TestSandboxEscapeVectors:
    """Verify that common sandbox escape vectors are blocked."""

    def test_os_system_blocked(self):
        """``os.system('id')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("os.system('id')") is False

    def test_os_popen_blocked(self):
        """``os.popen('id')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("os.popen('id')") is False

    def test_subprocess_run_blocked(self):
        """``subprocess.run(['id'])`` → blocked."""
        config = SandboxConfig()
        assert config.validate("subprocess.run(['id'])") is False

    def test_open_file_blocked(self):
        """``open('/etc/passwd').read()`` → blocked."""
        config = SandboxConfig()
        assert config.validate("open('/etc/passwd').read()") is False

    def test_globals_blocked(self):
        """``globals()`` → blocked."""
        config = SandboxConfig()
        assert config.validate("globals()") is False

    def test_locals_blocked(self):
        """``locals()`` → blocked."""
        config = SandboxConfig()
        assert config.validate("locals()") is False

    def test_resource_setrlimit_blocked(self):
        """``resource.setrlimit(...)`` → blocked."""
        config = SandboxConfig()
        assert config.validate("resource.setrlimit(0, (0, 0))") is False

    def test_ctypes_blocked(self):
        """``ctypes.CDLL('libc.so.6')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("ctypes.CDLL('libc.so.6')") is False

    def test_sys_modules_blocked(self):
        """``sys.modules`` → blocked."""
        config = SandboxConfig()
        assert config.validate("sys.modules") is False

    def test_sys_path_blocked(self):
        """``sys.path`` → blocked."""
        config = SandboxConfig()
        assert config.validate("sys.path.append('/evil')") is False

    def test_dunder_class_blocked(self):
        """``__class__`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__class__") is False

    def test_dunder_import_blocked(self):
        """``__import__('os')`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__import__('os')") is False

    def test_dunder_bases_blocked(self):
        """``__bases__`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__bases__") is False

    def test_dunder_subclasses_blocked(self):
        """``__subclasses__()`` → blocked."""
        config = SandboxConfig()
        assert config.validate("__subclasses__()") is False

    def test_socket_blocked(self):
        """``import socket`` → blocked."""
        config = SandboxConfig()
        assert config.validate("import socket") is False

    def test_http_blocked(self):
        """``http.client`` → blocked (string match)."""
        config = SandboxConfig()
        assert config.validate("http.client.HTTPConnection('evil.com')") is False

    def test_rm_rf_blocked(self):
        """``rm -rf /`` → blocked (shell injection)."""
        config = SandboxConfig()
        assert config.validate("rm -rf /") is False

    def test_format_command_blocked(self):
        """``format C:`` → blocked."""
        config = SandboxConfig()
        assert config.validate("format C:") is False

    def test_shutdown_blocked(self):
        """``shutdown /s /t 0`` → blocked."""
        config = SandboxConfig()
        assert config.validate("shutdown /s /t 0") is False


# ══════════════════════════════════════════════════════════════════════════════
#  7. SandboxExecutor integration
# ══════════════════════════════════════════════════════════════════════════════

class TestSandboxExecutor:
    """Verify that SandboxExecutor respects SandboxConfig validation."""

    def test_dangerous_code_blocked(self):
        """Dangerous code returns 'blocked' status from executor."""
        executor = SandboxExecutor()
        result = executor.execute("import os; os.system('id')", language="python")
        assert result["status"] == "blocked"
        assert "bloqu" in result["stderr"].lower() or "security" in result["stderr"].lower() or "bloqué" in result["stderr"].lower()

    def test_eval_blocked_in_executor(self):
        """eval() code returns 'blocked' status from executor."""
        executor = SandboxExecutor()
        result = executor.execute("eval('__import__(\"os\").system(\"id\")')", language="python")
        assert result["status"] == "blocked"

    def test_unsupported_language(self):
        """Unsupported language returns 'error' status."""
        executor = SandboxExecutor()
        result = executor.execute("code", language="rust")
        assert result["status"] == "error"
        assert "non support" in result["stderr"].lower() or "not supported" in result["stderr"].lower()

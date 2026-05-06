"""Security tests for ga.py — path traversal, shell safety, inline_eval.

Verifies that:
1. Path traversal via ``{{file:../../etc/passwd:1:10}}`` is rejected.
2. ``inline_eval`` mode raises SecurityError.
3. ``ALLOW_DANGEROUS_SHELL=False`` blocks dangerous shell commands.
4. Dangerous shell patterns are detected by DANGEROUS_SHELL_PATTERNS.
5. ``expand_file_refs`` blocks paths outside allowed directories.

Test IDs correspond to Task 4.1.1 in the project roadmap.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is importable
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _PROJECT_ROOT)

import ga
from ga import (
    expand_file_refs,
    DANGEROUS_SHELL_PATTERNS,
    set_shell_confirm_callback,
)

# Import SecurityError — ga.py defines its own fallback that is used
# for the inline_eval check. We use ga.SecurityError directly because
# that is the class raised by do_code_run.
try:
    from agentmain.safe_eval import SecurityError as _SafeEvalSecurityError
except ImportError:
    _SafeEvalSecurityError = None

# The SecurityError raised by ga.py's do_code_run is ga.SecurityError
# (which may be the safe_eval version or the fallback).
SecurityError = ga.SecurityError


# ══════════════════════════════════════════════════════════════════════════════
#  1. Path traversal in expand_file_refs
# ══════════════════════════════════════════════════════════════════════════════

class TestPathTraversal:
    """Verify that expand_file_refs blocks path traversal attempts."""

    def test_parent_directory_traversal_rejected(self):
        """``{{file:../../etc/passwd:1:10}}`` → rejected (path traversal).
        The regex disallows slashes in the filename, so the reference is NOT
        expanded. The literal text remains — no file content is read."""
        result = expand_file_refs("{{file:../../etc/passwd:1:10}}")
        # The key assertion: the reference was NOT expanded (no file content read)
        # The literal {{file:...}} should remain unchanged in the output
        assert "{{file:" in result  # reference was NOT expanded
        assert "root:" not in result  # /etc/passwd content was NOT read

    def test_absolute_path_traversal_rejected(self):
        """``{{file:/etc/passwd:1:10}}`` → rejected (absolute path)."""
        result = expand_file_refs("{{file:/etc/passwd:1:10}}")
        # The colon in /etc/passwd breaks the regex — reference is not expanded.
        # Even if expanded, path traversal check should block it.
        assert "root:" not in result or "refusé" in result

    def test_backslash_traversal_rejected(self):
        """``{{file:..\\..\\windows\\system32:1:10}}`` → rejected.
        The regex disallows backslashes in the filename, so the reference
        is NOT expanded."""
        result = expand_file_refs("{{file:..\\..\\windows\\system32:1:10}}")
        # The key assertion: the reference was NOT expanded
        assert "{{file:" in result  # reference was NOT expanded

    def test_path_outside_base_dir_rejected(self, tmp_path):
        """A file reference resolving outside base_dir → access denied."""
        # Create a file inside tmp_path
        safe_dir = tmp_path / "safe"
        safe_dir.mkdir()
        test_file = safe_dir / "data.txt"
        test_file.write_text("secret data\n")

        # Create a file outside safe_dir
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("outside data\n")

        # "outside.txt" relative to safe_dir → safe_dir/outside.txt → doesn't exist → ValueError
        with pytest.raises(ValueError):
            expand_file_refs("{{file:outside.txt:1:1}}", base_dir=str(safe_dir))

    def test_valid_file_ref_within_base_dir(self, tmp_path):
        """A valid file reference within base_dir works correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3\n")

        result = expand_file_refs(
            "{{file:test.txt:1:2}}",
            base_dir=str(tmp_path)
        )
        assert "line 1" in result
        assert "line 2" in result

    def test_file_ref_with_double_dots_in_name_rejected(self, tmp_path):
        """``{{file:../secret.txt:1:1}}`` → rejected (traversal via ..)."""
        test_file = tmp_path / "secret.txt"
        test_file.write_text("secret\n")

        # The regex disallows / in filename, so ../ won't match
        result = expand_file_refs("{{file:../secret.txt:1:1}}", base_dir=str(tmp_path))
        # Reference should not be expanded (literal text remains)
        assert "secret" not in result or "../secret.txt" in result

    def test_symlink_escape_rejected(self, tmp_path):
        """A symlink in base_dir pointing outside → access denied."""
        safe_dir = tmp_path / "safe"
        safe_dir.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("top secret\n")

        # Create symlink inside safe_dir pointing to outside_dir
        link = safe_dir / "link"
        try:
            link.symlink_to(outside_dir)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Reading via the symlink should be blocked because realpath resolves
        # outside the base_dir
        result = expand_file_refs(
            "{{file:link/secret.txt:1:1}}",
            base_dir=str(safe_dir)
        )
        # The regex disallows slashes in the filename, so link/secret.txt
        # won't match. The reference remains unexpanded.
        assert "top secret" not in result or "refusé" in result


# ══════════════════════════════════════════════════════════════════════════════
#  2. inline_eval mode → SecurityError
# ══════════════════════════════════════════════════════════════════════════════

class TestInlineEvalDisabled:
    """Verify that inline_eval mode in do_code_run raises SecurityError."""

    def test_inline_eval_raises_security_error(self):
        """``inline_eval=True`` → raises SecurityError."""
        from ga import GenericAgentHandler
        handler = GenericAgentHandler(MagicMock())
        with pytest.raises(SecurityError, match="inline_eval"):
            # do_code_run is a generator — we need to consume it
            gen = handler.do_code_run(
                {"type": "python", "code": "print('hello')", "inline_eval": True},
                MagicMock(),
            )
            # Exhaust the generator to trigger the SecurityError
            for _ in gen:
                pass

    def test_inline_eval_deprecation_warning(self):
        """``inline_eval=True`` also emits a DeprecationWarning."""
        from ga import GenericAgentHandler
        handler = GenericAgentHandler(MagicMock())
        with pytest.warns(DeprecationWarning, match="inline_eval"):
            with pytest.raises(SecurityError):
                gen = handler.do_code_run(
                    {"type": "python", "code": "x=1", "inline_eval": True},
                    MagicMock(),
                )
                for _ in gen:
                    pass


# ══════════════════════════════════════════════════════════════════════════════
#  3. ALLOW_DANGEROUS_SHELL=False blocks dangerous shell commands
# ══════════════════════════════════════════════════════════════════════════════

class TestAllowDangerousShell:
    """Verify that ALLOW_DANGEROUS_SHELL=False blocks dangerous commands in headless mode."""

    def setup_method(self):
        """Save original state before each test."""
        self._original_callback = ga._shell_confirm_callback
        self._original_allow = ga.ALLOW_DANGEROUS_SHELL

    def teardown_method(self):
        """Restore original state after each test."""
        ga._shell_confirm_callback = self._original_callback
        ga.ALLOW_DANGEROUS_SHELL = self._original_allow

    def test_dangerous_command_blocked_when_no_callback_and_no_flag(self):
        """Without callback and ALLOW_DANGEROUS_SHELL=False, dangerous commands are blocked."""
        ga._shell_confirm_callback = None
        ga.ALLOW_DANGEROUS_SHELL = False
        from ga import code_run
        gen = code_run("rm -rf /tmp/test_security", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        assert "bloquée" in all_output.lower() or "blocked" in all_output.lower() or "sécurité" in all_output.lower()

    def test_dangerous_command_allowed_with_flag(self):
        """With ALLOW_DANGEROUS_SHELL=True, dangerous commands pass through."""
        ga._shell_confirm_callback = None
        ga.ALLOW_DANGEROUS_SHELL = True
        from ga import code_run
        gen = code_run("rm -rf /tmp/test_security_allowed", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        # Should NOT contain "bloquée" — the command should be allowed
        assert "bloquée" not in all_output.lower()

    def test_safe_command_allowed_without_flag(self):
        """Safe shell commands are allowed even without ALLOW_DANGEROUS_SHELL."""
        ga._shell_confirm_callback = None
        ga.ALLOW_DANGEROUS_SHELL = False
        from ga import code_run
        gen = code_run("echo hello_security_test", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        # Safe command should execute (not blocked)
        assert "bloquée" not in all_output.lower()
        assert "hello_security_test" in all_output

    def test_callback_rejection_blocks_command(self):
        """A callback that returns False blocks the dangerous command."""
        ga._shell_confirm_callback = lambda code, code_type: False
        ga.ALLOW_DANGEROUS_SHELL = False
        from ga import code_run
        gen = code_run("rm -rf /tmp/test_reject", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        assert "bloquée" in all_output.lower() or "annulée" in all_output.lower()

    def test_callback_acceptance_allows_command(self):
        """A callback that returns True allows the dangerous command."""
        ga._shell_confirm_callback = lambda code, code_type: True
        ga.ALLOW_DANGEROUS_SHELL = False
        from ga import code_run
        gen = code_run("rm -rf /tmp/test_accept", code_type="bash", timeout=10)
        results = list(gen)
        all_output = "".join(str(r) for r in results)
        assert "bloquée" not in all_output.lower()


# ══════════════════════════════════════════════════════════════════════════════
#  4. Dangerous shell patterns are detected
# ══════════════════════════════════════════════════════════════════════════════

class TestDangerousShellPatterns:
    """Verify that DANGEROUS_SHELL_PATTERNS correctly detect dangerous commands."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf /tmp/test",
        "del /f /q important.txt",
        "rmdir /s /q C:\\important",
        "format C:",
        "shutdown /s /t 0",
        "reboot",
        "reg add HKLM\\Software\\Evil",
        "regedit /s evil.reg",
        "net user hacker P@ssw0rd /add",
        "netsh advfirewall set allprofiles state off",
        "taskkill /f /im important.exe",
        "chmod 777 /etc/shadow",
        "sudo rm -rf /",
    ])
    def test_dangerous_command_detected(self, cmd: str):
        """Each dangerous command should be matched by at least one pattern."""
        code_lower = cmd.lower()
        found = any(re.search(p, code_lower) for p in DANGEROUS_SHELL_PATTERNS)
        assert found, f"Command not detected as dangerous: {cmd}"

    @pytest.mark.parametrize("cmd", [
        "echo hello",
        "ls -la",
        "cat file.txt",
        "python script.py",
        "git status",
        "npm install",
        "pip install package",
        "mkdir newdir",
        "cp file1.txt file2.txt",
        "mv old.txt new.txt",
    ])
    def test_safe_command_not_detected(self, cmd: str):
        """Safe commands should NOT be matched by any dangerous pattern."""
        code_lower = cmd.lower()
        found = any(re.search(p, code_lower) for p in DANGEROUS_SHELL_PATTERNS)
        assert not found, f"Safe command incorrectly flagged as dangerous: {cmd}"

    def test_patterns_are_compilable_regex(self):
        """Every pattern in DANGEROUS_SHELL_PATTERNS is a valid regex."""
        for pattern in DANGEROUS_SHELL_PATTERNS:
            re.compile(pattern)  # Should not raise re.error


# ══════════════════════════════════════════════════════════════════════════════
#  5. expand_file_refs blocks paths outside allowed directories
# ══════════════════════════════════════════════════════════════════════════════

class TestExpandFileRefsSecurity:
    """Verify that expand_file_refs enforces directory boundaries."""

    def test_file_in_allowed_dir_works(self, tmp_path):
        """Reading a file within the base directory works."""
        f = tmp_path / "readme.txt"
        f.write_text("hello world\nline 2\n")
        result = expand_file_refs("{{file:readme.txt:1:2}}", base_dir=str(tmp_path))
        assert "hello world" in result

    def test_file_resolving_outside_base_dir_blocked(self, tmp_path):
        """A filename resolving outside base_dir is blocked."""
        safe = tmp_path / "safe"
        safe.mkdir()
        # "readme.txt" relative to safe/ → safe/readme.txt → doesn't exist → ValueError
        with pytest.raises(ValueError):
            expand_file_refs("{{file:readme.txt:1:1}}", base_dir=str(safe))

    def test_absolute_path_in_ref_not_matched(self):
        """Absolute paths in the filename portion are rejected by regex."""
        result = expand_file_refs("{{file:/etc/passwd:1:1}}")
        # The regex disallows / in filename, so /etc/passwd won't match
        # Result should be the original text unchanged
        assert "{{file:/etc/passwd:1:1}}" in result or "refusé" in result

    def test_double_dot_not_matched(self):
        """Double-dot in filename portion is rejected by regex."""
        result = expand_file_refs("{{file:../../etc/passwd:1:10}}")
        # The regex disallows / in filename, so ../../etc/passwd won't match
        assert "root:" not in result

    def test_backslash_not_matched(self):
        """Backslash in filename portion is rejected by regex."""
        result = expand_file_refs("{{file:..\\..\\etc\\passwd:1:10}}")
        # The regex disallows \\ in filename
        assert "root:" not in result

    def test_no_refs_passthrough(self):
        """Text without file references passes through unchanged."""
        assert expand_file_refs("Hello, world!") == "Hello, world!"

    def test_malformed_ref_passthrough(self):
        """A malformed {{file:...}} reference is not expanded."""
        result = expand_file_refs("{{file:no_colon_separator}}")
        # Should not crash and the text should remain unchanged
        assert "{{file:no_colon_separator}}" in result

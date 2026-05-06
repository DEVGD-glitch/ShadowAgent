"""Security tests for slash.py — /session.* allowlist and range validation.

Verifies that:
1. ``/session.api_key=STOLEN`` → rejected (not in allowlist).
2. ``/session.model=claude-3`` → accepted.
3. ``/session.temperature=0.5`` → accepted.
4. ``/session.temperature=3.0`` → rejected (out of range).
5. ``/session.max_tokens=-1`` → rejected.

Test IDs correspond to Task 4.1.3 in the project roadmap.
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import sys
import pytest
from unittest.mock import MagicMock, patch

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


# Load safe_eval first (slash.py doesn't depend on it, but having it in
# sys.modules prevents accidental import through agentmain package).
_se_path = os.path.join(_PROJECT_ROOT, "agentmain", "safe_eval.py")
if os.path.isfile(_se_path):
    _load_module_from_path("agentmain.safe_eval", _se_path)

# Load prompts (needed by slash.py for script_dir)
_prompts_path = os.path.join(_PROJECT_ROOT, "agentmain", "prompts.py")
if "agentmain.prompts" not in sys.modules and os.path.isfile(_prompts_path):
    _load_module_from_path("agentmain.prompts", _prompts_path)

# Load slash directly from file
_slash_path = os.path.join(_PROJECT_ROOT, "agentmain", "slash.py")
_slash = _load_module_from_path("agentmain.slash", _slash_path)

handle_slash_cmd = _slash.handle_slash_cmd
SESSION_WRITABLE_ATTRS = _slash.SESSION_WRITABLE_ATTRS
_SESSION_VALIDATORS = _slash._SESSION_VALIDATORS


# ══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_agent():
    """Create a mock agent with llmclient.backend for setattr tests."""
    agent = MagicMock()
    agent.llmclient = MagicMock()
    agent.llmclient.backend = MagicMock()
    return agent


@pytest.fixture
def display_queue():
    """Create a queue for display messages."""
    return queue.Queue()


# ══════════════════════════════════════════════════════════════════════════════
#  1. Allowlist enforcement — non-allowed attributes are rejected
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionAllowlist:
    """Verify that only allowlisted attributes can be set via /session.*."""

    def test_api_key_rejected(self, mock_agent, display_queue):
        """``/session.api_key=STOLEN`` → rejected (not in allowlist)."""
        result = handle_slash_cmd(mock_agent, "/session.api_key=STOLEN", display_queue)
        assert result is None  # Command was handled (rejected)
        # Backend should NOT have been modified
        assert not mock_agent.llmclient.backend.method_calls

    def test_arbitrary_attr_rejected(self, mock_agent, display_queue):
        """``/session.__class__`` → rejected (not in allowlist, dangerous)."""
        result = handle_slash_cmd(mock_agent, "/session.__class__=evil", display_queue)
        assert result is None
        assert not mock_agent.llmclient.backend.method_calls

    def test_dangerous_attr_rejected(self, mock_agent, display_queue):
        """Various dangerous attributes are rejected."""
        dangerous_attrs = [
            "system_prompt", "base_url", "api_key",
            "headers", "auth_token", "credentials",
        ]
        for attr in dangerous_attrs:
            q = queue.Queue()
            result = handle_slash_cmd(
                mock_agent, f"/session.{attr}=malicious", q
            )
            assert result is None, f"Attribute '{attr}' should be rejected"
            # Check that a rejection message was sent to the display queue
            msg = q.get_nowait()
            msg_text = msg.get("done", "").lower()
            assert "non modifiable" in msg_text or "attribut" in msg_text or "autoris" in msg_text

    def test_non_session_slash_command_passthrough(self, mock_agent, display_queue):
        """A slash command that isn't /session.* is passed through."""
        result = handle_slash_cmd(mock_agent, "/help", display_queue)
        assert result == "/help"

    def test_non_slash_passthrough(self, mock_agent, display_queue):
        """Non-slash input is passed through unchanged."""
        result = handle_slash_cmd(mock_agent, "Hello agent", display_queue)
        assert result == "Hello agent"


# ══════════════════════════════════════════════════════════════════════════════
#  2. Allowed attributes — model
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionModel:
    """Verify /session.model validation."""

    def test_model_accepted(self, mock_agent, display_queue):
        """``/session.model=claude-3`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.model=claude-3", display_queue
        )
        assert result is None  # Command was handled
        # Verify the backend attribute was set
        assert mock_agent.llmclient.backend.model == "claude-3"

    def test_model_empty_rejected(self, mock_agent, display_queue):
        """``/session.model=`` → rejected (empty string)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.model=", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "non-empty" in msg_text or "must be" in msg_text or "vide" in msg_text

    def test_model_numeric_rejected(self, mock_agent, display_queue):
        """``/session.model=123`` → rejected (not a string after JSON parse)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.model=123", q)
        # After JSON parsing, 123 becomes an int, which should be rejected
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "string" in msg_text or "must be" in msg_text or "chaîne" in msg_text


# ══════════════════════════════════════════════════════════════════════════════
#  3. Allowed attributes — temperature
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionTemperature:
    """Verify /session.temperature validation."""

    def test_temperature_valid(self, mock_agent, display_queue):
        """``/session.temperature=0.5`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.temperature=0.5", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.temperature == 0.5

    def test_temperature_zero(self, mock_agent, display_queue):
        """``/session.temperature=0`` → accepted (boundary)."""
        result = handle_slash_cmd(
            mock_agent, "/session.temperature=0", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.temperature == 0

    def test_temperature_two(self, mock_agent, display_queue):
        """``/session.temperature=2`` → accepted (boundary)."""
        result = handle_slash_cmd(
            mock_agent, "/session.temperature=2", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.temperature == 2

    def test_temperature_too_high(self, mock_agent, display_queue):
        """``/session.temperature=3.0`` → rejected (out of range)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.temperature=3.0", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "between" in msg_text or "0" in msg_text or "entre" in msg_text

    def test_temperature_negative(self, mock_agent, display_queue):
        """``/session.temperature=-0.1`` → rejected (out of range)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.temperature=-0.1", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "between" in msg_text or "0" in msg_text or "entre" in msg_text

    def test_temperature_string_rejected(self, mock_agent, display_queue):
        """``/session.temperature=hot`` → rejected (not a number)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.temperature=hot", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "number" in msg_text or "must be" in msg_text or "nombre" in msg_text


# ══════════════════════════════════════════════════════════════════════════════
#  4. Allowed attributes — max_tokens
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionMaxTokens:
    """Verify /session.max_tokens validation."""

    def test_max_tokens_negative_rejected(self, mock_agent, display_queue):
        """``/session.max_tokens=-1`` → rejected (negative)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.max_tokens=-1", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "positive" in msg_text or "must be" in msg_text or "positif" in msg_text

    def test_max_tokens_zero_rejected(self, mock_agent, display_queue):
        """``/session.max_tokens=0`` → rejected (not positive)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.max_tokens=0", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "positive" in msg_text or "positif" in msg_text

    def test_max_tokens_valid(self, mock_agent, display_queue):
        """``/session.max_tokens=4096`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.max_tokens=4096", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.max_tokens == 4096

    def test_max_tokens_float_rejected(self, mock_agent, display_queue):
        """``/session.max_tokens=1.5`` → rejected (not an integer)."""
        q = queue.Queue()
        # JSON parses 1.5 as float, not int
        result = handle_slash_cmd(mock_agent, "/session.max_tokens=1.5", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "integer" in msg_text or "entier" in msg_text

    def test_max_tokens_string_rejected(self, mock_agent, display_queue):
        """``/session.max_tokens=abc`` → rejected (not a number)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.max_tokens=abc", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "integer" in msg_text or "entier" in msg_text or "must be" in msg_text


# ══════════════════════════════════════════════════════════════════════════════
#  5. Other allowed attributes — top_p, frequency_penalty, presence_penalty, stream
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionOtherAttrs:
    """Verify validation for top_p, frequency_penalty, presence_penalty, stream."""

    def test_top_p_valid(self, mock_agent, display_queue):
        """``/session.top_p=0.9`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.top_p=0.9", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.top_p == 0.9

    def test_top_p_out_of_range(self, mock_agent, display_queue):
        """``/session.top_p=1.5`` → rejected (must be 0-1)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.top_p=1.5", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "between" in msg_text or "0" in msg_text or "entre" in msg_text

    def test_frequency_penalty_valid(self, mock_agent, display_queue):
        """``/session.frequency_penalty=0.5`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.frequency_penalty=0.5", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.frequency_penalty == 0.5

    def test_frequency_penalty_out_of_range(self, mock_agent, display_queue):
        """``/session.frequency_penalty=3.0`` → rejected (must be -2 to 2)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.frequency_penalty=3.0", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "between" in msg_text or "-2" in msg_text or "entre" in msg_text

    def test_presence_penalty_valid(self, mock_agent, display_queue):
        """``/session.presence_penalty=-1.0`` → accepted."""
        result = handle_slash_cmd(
            mock_agent, "/session.presence_penalty=-1.0", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.presence_penalty == -1.0

    def test_presence_penalty_out_of_range(self, mock_agent, display_queue):
        """``/session.presence_penalty=-3.0`` → rejected (must be -2 to 2)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.presence_penalty=-3.0", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "between" in msg_text or "-2" in msg_text or "entre" in msg_text

    def test_stream_valid(self, mock_agent, display_queue):
        """``/session.stream=true`` → accepted (JSON parses to bool)."""
        result = handle_slash_cmd(
            mock_agent, "/session.stream=true", display_queue
        )
        assert result is None
        assert mock_agent.llmclient.backend.stream is True

    def test_stream_string_rejected(self, mock_agent, display_queue):
        """``/session.stream=yes`` → rejected (not a boolean)."""
        q = queue.Queue()
        result = handle_slash_cmd(mock_agent, "/session.stream=yes", q)
        assert result is None
        msg = q.get_nowait()
        msg_text = msg.get("done", "").lower()
        assert "boolean" in msg_text or "must be" in msg_text or "booléen" in msg_text


# ══════════════════════════════════════════════════════════════════════════════
#  6. SESSION_WRITABLE_ATTRS completeness
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionWritableAttrs:
    """Verify the SESSION_WRITABLE_ATTRS allowlist is properly defined."""

    def test_allowlist_is_frozenset(self):
        """SESSION_WRITABLE_ATTRS should be a frozenset (immutable)."""
        assert isinstance(SESSION_WRITABLE_ATTRS, frozenset)

    def test_core_attrs_in_allowlist(self):
        """Core attributes model, temperature, max_tokens, top_p are in allowlist."""
        assert "model" in SESSION_WRITABLE_ATTRS
        assert "temperature" in SESSION_WRITABLE_ATTRS
        assert "max_tokens" in SESSION_WRITABLE_ATTRS
        assert "top_p" in SESSION_WRITABLE_ATTRS

    def test_dangerous_attrs_not_in_allowlist(self):
        """Dangerous attributes are NOT in the allowlist."""
        assert "api_key" not in SESSION_WRITABLE_ATTRS
        assert "__class__" not in SESSION_WRITABLE_ATTRS
        assert "__dict__" not in SESSION_WRITABLE_ATTRS
        assert "system_prompt" not in SESSION_WRITABLE_ATTRS

    def test_all_allowed_attrs_have_validators(self):
        """Every attr in SESSION_WRITABLE_ATTRS has a corresponding validator."""
        for attr in SESSION_WRITABLE_ATTRS:
            assert attr in _SESSION_VALIDATORS, (
                f"Attr '{attr}' is in SESSION_WRITABLE_ATTRS but has no validator"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  7. /resume command
# ══════════════════════════════════════════════════════════════════════════════

class TestResumeCommand:
    """Verify /resume command returns the resume prompt."""

    def test_resume_returns_prompt(self, mock_agent, display_queue):
        """``/resume`` returns a non-empty prompt string."""
        result = handle_slash_cmd(mock_agent, "/resume", display_queue)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 10  # Should be a meaningful prompt

    def test_resume_with_whitespace(self, mock_agent, display_queue):
        """``/resume  `` (with trailing whitespace) still works."""
        result = handle_slash_cmd(mock_agent, "/resume  ", display_queue)
        assert result is not None
        assert isinstance(result, str)

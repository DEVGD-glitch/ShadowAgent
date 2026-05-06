"""
Custom exception hierarchy for the GenericAgent project.

This module defines a structured set of exceptions organized by domain:
- LLM Errors: Connection, rate-limiting, auth, response parsing, and streaming issues
- Tool Errors: Execution, timeout, security, and code-run failures
- File Errors: Not-found, patching, reading, and writing problems
- Web Errors: Browser availability and JavaScript evaluation issues
- Session Errors: Configuration, history, and missing API keys
- Agent Errors: Turn limits, interrupts, and plan-mode conflicts

All exceptions inherit from :class:`GenericAgentError` so that callers can
catch the entire family with a single ``except GenericAgentError`` handler.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class GenericAgentError(Exception):
    """Base exception for all custom errors in the GenericAgent project.

    Parameters
    ----------
    message : str
        A human-readable description of the error.
    details : dict[str, Any] | None
        Optional structured metadata providing additional context (e.g. the
        HTTP status code that triggered the error, a tool name, a file path).

    Attributes
    ----------
    message : str
        The error message.
    details : dict[str, Any]
        Structured metadata (empty dict when not provided).
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message: str = message
        self.details: dict[str, Any] = details if details is not None else {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


# ---------------------------------------------------------------------------
# LLM Errors
# ---------------------------------------------------------------------------

class LLMError(GenericAgentError):
    """Base exception for errors related to LLM interactions.

    Covers any failure that occurs while communicating with a large-language-
    model provider (connection issues, rate limits, authentication, bad
    responses, interrupted streams, etc.).
    """


class LLMConnectionError(LLMError):
    """Raised when a network-level connection to the LLM provider cannot be
    established or is unexpectedly dropped.

    Typical causes include DNS failures, refused connections, and socket
    timeouts that occur *before* an HTTP response is received.
    """


class LLMRateLimitError(LLMError):
    """Raised when the LLM provider responds with a rate-limit / too-many-
    requests error.

    The ``details`` dict typically contains ``retry_after`` (seconds) and
    ``status_code`` (e.g. 429).
    """


class LLMAuthError(LLMError):
    """Raised when authentication with the LLM provider fails.

    This usually indicates an invalid, expired, or missing API key / token.
    """


class LLMResponseError(LLMError):
    """Raised when the LLM provider returns an unexpected or malformed
    response that cannot be parsed into the expected schema.

    The raw response text may be attached via ``details["raw_response"]``.
    """


class LLMStreamInterruptedError(LLMError):
    """Raised when an ongoing streaming response from the LLM is interrupted
    before completion.

    This can happen due to network instability, server-side timeouts, or the
    provider terminating the stream.  Partial content collected so far may be
    available in ``details["partial_content"]``.
    """


# ---------------------------------------------------------------------------
# Tool Errors
# ---------------------------------------------------------------------------

class ToolError(GenericAgentError):
    """Base exception for errors related to agent tool execution.

    Covers failures that occur while preparing, running, or processing the
    output of a tool (shell commands, code execution, etc.).
    """


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution.

    The ``details`` dict often includes ``tool_name``, ``exit_code``, and
    ``stderr`` to aid debugging.
    """


class ToolTimeoutError(ToolError):
    """Raised when a tool exceeds its allowed execution time.

    The ``details`` dict may include ``timeout_seconds`` and ``tool_name``.
    """


class ShellSecurityError(ToolError):
    """Raised when a shell command violates the project's security policy.

    This includes attempts to run blocked commands, access forbidden paths, or
    perform privileged operations outside the sandbox.
    """


class CodeExecutionError(ToolError):
    """Raised when inline code execution (e.g. Python sandbox) fails.

    The ``details`` dict may include ``traceback_str``, ``exit_code``, and
    ``language``.
    """


# ---------------------------------------------------------------------------
# File Errors
# ---------------------------------------------------------------------------

class FileOperationError(GenericAgentError):
    """Base exception for errors related to file operations.

    Covers read, write, patch, and file-not-found failures encountered while
    the agent manipulates the filesystem.
    """


class FileNotFoundError_(FileOperationError):
    """Raised when a required file does not exist.

    The trailing underscore avoids shadowing the built-in
    :class:`FileNotFoundError`.

    The ``details`` dict typically contains ``path``.
    """


class FilePatchError(FileOperationError):
    """Raised when a patch (diff-based edit) cannot be applied to a file.

    This may be due to a mismatch between the expected context lines and the
    actual file contents.  ``details`` may include ``path`` and ``hunk``.
    """


class FileWriteError(FileOperationError):
    """Raised when writing to a file fails.

    Common causes include permission errors, disk-full conditions, and path
    traversal violations.  ``details`` typically contains ``path``.
    """


class FileReadError(FileOperationError):
    """Raised when reading from a file fails.

    Common causes include permission errors and encoding issues.
    ``details`` typically contains ``path``.
    """


# ---------------------------------------------------------------------------
# Web Errors
# ---------------------------------------------------------------------------

class WebError(GenericAgentError):
    """Base exception for errors related to web browsing / automation.

    Covers browser availability, JavaScript evaluation, and page interaction
    failures.
    """


class BrowserNotAvailableError(WebError):
    """Raised when the required browser runtime (e.g. Playwright, TMWebDriver)
    is not installed or cannot be launched.

    ``details`` may include ``browser`` (the name of the requested browser)
    and ``install_hint``.
    """


class WebJSError(WebError):
    """Raised when JavaScript evaluation in a browser context fails.

    ``details`` may include ``expression``, ``exception_message``, and
    ``url``.
    """


# ---------------------------------------------------------------------------
# Session Errors
# ---------------------------------------------------------------------------

class SessionError(GenericAgentError):
    """Base exception for errors related to session management.

    Covers configuration mistakes, history corruption, and missing credentials.
    """


class SessionConfigError(SessionError):
    """Raised when a session is misconfigured.

    This includes invalid parameter values, missing required fields, or
    conflicting settings.
    """


class SessionHistoryError(SessionError):
    """Raised when there is a problem loading, saving, or validating session
    history (e.g. corrupted JSON, schema mismatches).
    """


class APIKeyMissingError(SessionConfigError):
    """Raised when a required API key is not provided for the session.

    ``details`` typically contains ``provider`` (the name of the LLM provider
    that requires the key) and ``env_var`` (the expected environment variable).
    """


# ---------------------------------------------------------------------------
# Agent Errors
# ---------------------------------------------------------------------------

class AgentError(GenericAgentError):
    """Base exception for errors related to the agent loop itself.

    Covers turn limits, user interrupts, and plan-mode conflicts.
    """


class MaxTurnsExceededError(AgentError):
    """Raised when the agent loop exceeds its configured maximum number of
    turns without reaching a conclusion.

    ``details`` typically contains ``max_turns`` and ``actual_turns``.
    """


class AgentInterruptError(AgentError):
    """Raised when the agent loop is interrupted by the user or an external
    signal.

    ``details`` may include ``reason`` and ``last_turn_index``.
    """


class PlanModeError(AgentError):
    """Raised when a plan-mode operation encounters a conflict or failure,
    such as attempting to execute a tool while in planning-only mode or when
    the plan cannot be generated.

    ``details`` may include ``plan_step`` and ``conflict_reason``.
    """


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Base
    "GenericAgentError",
    # LLM
    "LLMError",
    "LLMConnectionError",
    "LLMRateLimitError",
    "LLMAuthError",
    "LLMResponseError",
    "LLMStreamInterruptedError",
    # Tool
    "ToolError",
    "ToolExecutionError",
    "ToolTimeoutError",
    "ShellSecurityError",
    "CodeExecutionError",
    # File
    "FileOperationError",
    "FileNotFoundError_",
    "FilePatchError",
    "FileWriteError",
    "FileReadError",
    # Web
    "WebError",
    "BrowserNotAvailableError",
    "WebJSError",
    # Session
    "SessionError",
    "SessionConfigError",
    "SessionHistoryError",
    "APIKeyMissingError",
    # Agent
    "AgentError",
    "MaxTurnsExceededError",
    "AgentInterruptError",
    "PlanModeError",
]

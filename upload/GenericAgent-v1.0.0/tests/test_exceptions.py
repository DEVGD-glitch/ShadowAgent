"""Tests for the exceptions module.

Covers all exception classes, their hierarchy, __str__ format, details dict,
and GenericAgentError as the base for all custom exceptions.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from exceptions import (
    GenericAgentError,
    # LLM errors
    LLMError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMAuthError,
    LLMResponseError,
    LLMStreamInterruptedError,
    # Tool errors
    ToolError,
    ToolExecutionError,
    ToolTimeoutError,
    ShellSecurityError,
    CodeExecutionError,
    # File errors
    FileOperationError,
    FileNotFoundError_,
    FilePatchError,
    FileWriteError,
    FileReadError,
    # Web errors
    WebError,
    BrowserNotAvailableError,
    WebJSError,
    # Session errors
    SessionError,
    SessionConfigError,
    SessionHistoryError,
    APIKeyMissingError,
    # Agent errors
    AgentError,
    MaxTurnsExceededError,
    AgentInterruptError,
    PlanModeError,
)


# ══════════════════════════════════════════════════════════════════════
# GenericAgentError — base
# ══════════════════════════════════════════════════════════════════════

class TestGenericAgentError:
    """Tests for the base GenericAgentError."""

    def test_creation_with_message(self):
        """GenericAgentError can be created with just a message."""
        err = GenericAgentError("something went wrong")
        assert err.message == "something went wrong"

    def test_creation_with_details(self):
        """GenericAgentError stores details dict."""
        err = GenericAgentError("error", details={"code": 500})
        assert err.details == {"code": 500}

    def test_details_default_empty(self):
        """GenericAgentError details defaults to empty dict."""
        err = GenericAgentError("error")
        assert err.details == {}

    def test_details_none_becomes_empty(self):
        """GenericAgentError with details=None gets empty dict."""
        err = GenericAgentError("error", details=None)
        assert err.details == {}

    def test_str_format(self):
        """GenericAgentError __str__ includes class name and message."""
        err = GenericAgentError("test error")
        assert str(err) == "GenericAgentError: test error"

    def test_is_exception(self):
        """GenericAgentError is a subclass of Exception."""
        assert issubclass(GenericAgentError, Exception)

    def test_can_be_raised_and_caught(self):
        """GenericAgentError can be raised and caught normally."""
        with pytest.raises(GenericAgentError) as exc_info:
            raise GenericAgentError("caught!")
        assert exc_info.value.message == "caught!"

    def test_details_not_shared_between_instances(self):
        """Each instance has its own details dict."""
        err1 = GenericAgentError("e1")
        err2 = GenericAgentError("e2")
        err1.details["key"] = "val"
        assert "key" not in err2.details


# ══════════════════════════════════════════════════════════════════════
# Hierarchy — all exceptions inherit from GenericAgentError
# ══════════════════════════════════════════════════════════════════════

class TestExceptionHierarchy:
    """Tests for the exception class hierarchy."""

    # -- LLM errors ----------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        LLMError, LLMConnectionError, LLMRateLimitError,
        LLMAuthError, LLMResponseError, LLMStreamInterruptedError,
    ])
    def test_llm_errors_are_generic_agent_errors(self, cls):
        """All LLM error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [
        LLMConnectionError, LLMRateLimitError, LLMAuthError,
        LLMResponseError, LLMStreamInterruptedError,
    ])
    def test_llm_subclasses_inherit_from_llm_error(self, cls):
        """LLM-specific errors inherit from LLMError."""
        assert issubclass(cls, LLMError)

    # -- Tool errors ---------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        ToolError, ToolExecutionError, ToolTimeoutError,
        ShellSecurityError, CodeExecutionError,
    ])
    def test_tool_errors_are_generic_agent_errors(self, cls):
        """All Tool error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [
        ToolExecutionError, ToolTimeoutError, ShellSecurityError,
        CodeExecutionError,
    ])
    def test_tool_subclasses_inherit_from_tool_error(self, cls):
        """Tool-specific errors inherit from ToolError."""
        assert issubclass(cls, ToolError)

    # -- File errors ---------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        FileOperationError, FileNotFoundError_, FilePatchError,
        FileWriteError, FileReadError,
    ])
    def test_file_errors_are_generic_agent_errors(self, cls):
        """All File error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [
        FileNotFoundError_, FilePatchError, FileWriteError, FileReadError,
    ])
    def test_file_subclasses_inherit_from_file_operation_error(self, cls):
        """File-specific errors inherit from FileOperationError."""
        assert issubclass(cls, FileOperationError)

    # -- Web errors ----------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        WebError, BrowserNotAvailableError, WebJSError,
    ])
    def test_web_errors_are_generic_agent_errors(self, cls):
        """All Web error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [BrowserNotAvailableError, WebJSError])
    def test_web_subclasses_inherit_from_web_error(self, cls):
        """Web-specific errors inherit from WebError."""
        assert issubclass(cls, WebError)

    # -- Session errors ------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        SessionError, SessionConfigError, SessionHistoryError,
        APIKeyMissingError,
    ])
    def test_session_errors_are_generic_agent_errors(self, cls):
        """All Session error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [SessionConfigError, SessionHistoryError, APIKeyMissingError])
    def test_session_subclasses_inherit_from_session_error(self, cls):
        """Session-specific errors inherit from SessionError."""
        assert issubclass(cls, SessionError)

    def test_api_key_missing_inherits_from_session_config_error(self):
        """APIKeyMissingError inherits from SessionConfigError."""
        assert issubclass(APIKeyMissingError, SessionConfigError)

    # -- Agent errors --------------------------------------------------------

    @pytest.mark.parametrize("cls", [
        AgentError, MaxTurnsExceededError, AgentInterruptError,
        PlanModeError,
    ])
    def test_agent_errors_are_generic_agent_errors(self, cls):
        """All Agent error classes inherit from GenericAgentError."""
        assert issubclass(cls, GenericAgentError)

    @pytest.mark.parametrize("cls", [MaxTurnsExceededError, AgentInterruptError, PlanModeError])
    def test_agent_subclasses_inherit_from_agent_error(self, cls):
        """Agent-specific errors inherit from AgentError."""
        assert issubclass(cls, AgentError)


# ══════════════════════════════════════════════════════════════════════
# Creation and __str__ for every exception class
# ══════════════════════════════════════════════════════════════════════

class TestAllExceptionCreation:
    """Test that every exception class can be created and has proper __str__."""

    ALL_EXCEPTION_CLASSES = [
        GenericAgentError,
        LLMError, LLMConnectionError, LLMRateLimitError,
        LLMAuthError, LLMResponseError, LLMStreamInterruptedError,
        ToolError, ToolExecutionError, ToolTimeoutError,
        ShellSecurityError, CodeExecutionError,
        FileOperationError, FileNotFoundError_, FilePatchError,
        FileWriteError, FileReadError,
        WebError, BrowserNotAvailableError, WebJSError,
        SessionError, SessionConfigError, SessionHistoryError,
        APIKeyMissingError,
        AgentError, MaxTurnsExceededError, AgentInterruptError,
        PlanModeError,
    ]

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_can_create_with_message(self, cls):
        """Every exception class can be created with a message."""
        err = cls("test message")
        assert err.message == "test message"

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_str_includes_class_name(self, cls):
        """Every exception __str__ includes the class name."""
        err = cls("test")
        assert cls.__name__ in str(err)

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_str_includes_message(self, cls):
        """Every exception __str__ includes the message."""
        err = cls("unique_message_123")
        assert "unique_message_123" in str(err)

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_str_format(self, cls):
        """Every exception __str__ follows 'ClassName: message' format."""
        err = cls("test")
        assert str(err) == f"{cls.__name__}: test"

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_details_dict(self, cls):
        """Every exception can store details dict."""
        err = cls("msg", details={"key": "value"})
        assert err.details == {"key": "value"}

    @pytest.mark.parametrize("cls", ALL_EXCEPTION_CLASSES)
    def test_catch_as_generic_agent_error(self, cls):
        """Every exception can be caught as GenericAgentError."""
        with pytest.raises(GenericAgentError):
            raise cls("caught")


# ══════════════════════════════════════════════════════════════════════
# Specific exception semantics
# ══════════════════════════════════════════════════════════════════════

class TestSpecificExceptionSemantics:
    """Tests for specific exception behaviours."""

    def test_max_turns_exceeded_details(self):
        """MaxTurnsExceededError stores turn info in details."""
        err = MaxTurnsExceededError(
            "exceeded",
            details={"max_turns": 40, "actual_turns": 41},
        )
        assert err.details["max_turns"] == 40
        assert err.details["actual_turns"] == 41

    def test_llm_rate_limit_details(self):
        """LLMRateLimitError stores retry info in details."""
        err = LLMRateLimitError(
            "rate limited",
            details={"retry_after": 30, "status_code": 429},
        )
        assert err.details["retry_after"] == 30
        assert err.details["status_code"] == 429

    def test_llm_auth_error_catch_as_llm_error(self):
        """LLMAuthError can be caught as LLMError."""
        with pytest.raises(LLMError):
            raise LLMAuthError("bad key")

    def test_tool_execution_error_catch_as_tool_error(self):
        """ToolExecutionError can be caught as ToolError."""
        with pytest.raises(ToolError):
            raise ToolExecutionError("tool failed")

    def test_file_not_found_error_not_shadow_builtin(self):
        """FileNotFoundError_ does not shadow the built-in FileNotFoundError."""
        assert FileNotFoundError_ is not FileNotFoundError
        assert issubclass(FileNotFoundError_, FileOperationError)
        # The built-in should still be accessible
        with pytest.raises(FileNotFoundError):
            raise FileNotFoundError("builtin")

    def test_api_key_missing_catch_as_session_config_error(self):
        """APIKeyMissingError can be caught as SessionConfigError."""
        with pytest.raises(SessionConfigError):
            raise APIKeyMissingError("no key")

    def test_api_key_missing_catch_as_session_error(self):
        """APIKeyMissingError can be caught as SessionError."""
        with pytest.raises(SessionError):
            raise APIKeyMissingError("no key")

    def test_agent_interrupt_details(self):
        """AgentInterruptError stores reason in details."""
        err = AgentInterruptError(
            "interrupted",
            details={"reason": "user_cancel", "last_turn_index": 5},
        )
        assert err.details["reason"] == "user_cancel"

    def test_shell_security_error_is_tool_error(self):
        """ShellSecurityError can be caught as ToolError."""
        with pytest.raises(ToolError):
            raise ShellSecurityError("dangerous command")

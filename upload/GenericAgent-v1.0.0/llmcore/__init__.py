"""Core LLM session management, SSE parsing, and retry logic.

This package provides session classes for communicating with LLM providers
(Anthropic Claude, OpenAI-compatible APIs, Google AI Studio), SSE stream
parsing, message conversion between Claude and OpenAI formats, and
exponential-backoff retry with jitter.

Public API
----------
reload_mykeys, compress_history_tags, trim_messages_history, auto_make_url,
BaseSession, ClaudeSession, LLMSession, NativeClaudeSession, NativeOAISession,
ToolClient, MixinSession, NativeToolClient, tryparse, safeprint,
openai_tools_to_claude, GoogleAISession, GoogleAIConfig,
tools_to_google_format, parse_google_response, google_function_call_to_tool_call
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Re-export all public symbols from submodules
# ---------------------------------------------------------------------------

# config
from .config import _load_mykeys, reload_mykeys

# utils
from .utils import (
    _RESP_CACHE_KEY,
    _oldprint,
    _record_usage,
    _write_llm_log,
    auto_make_url,
    safeprint,
    THINKING_PROMPT_EN,
    THINKING_PROMPT_FR,
    THINKING_PROMPT_ZH,
    logger,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMStreamInterruptedError,
)

# parsers
from .parsers import (
    _parse_claude_json,
    _parse_claude_sse,
    _parse_openai_json,
    _parse_openai_sse,
    _try_parse_tool_args,
    tryparse,
)

# messages
from .messages import (
    _fix_messages,
    _msgs_claude2oai,
    _sanitize_leading_user_msg,
    _stamp_oai_cache_markers,
    compress_history_tags,
    trim_messages_history,
)

# retry
from .retry import _stream_with_retry

# convert
from .convert import (
    _prepare_oai_tools,
    _to_responses_input,
    openai_tools_to_claude,
)

# sessions
from .sessions import (
    BaseSession,
    ClaudeSession,
    LLMSession,
    MixinSession,
    _openai_stream,
    _keep_claude_block,
    _drop_unsigned_thinking,
    _ensure_thinking_blocks,
)

# clients
from .clients import (
    MockFunction,
    MockResponse,
    MockToolCall,
    NativeClaudeSession,
    NativeOAISession,
    NativeToolClient,
    ToolClient,
    _parse_text_tool_calls,
)

# google_provider
from .google_provider import (
    GoogleAIConfig,
    GoogleAISession,
    google_function_call_to_tool_call,
    parse_google_response,
    tools_to_google_format,
)

# ---------------------------------------------------------------------------
# Public symbols (same __all__ as the original monolith)
# ---------------------------------------------------------------------------
__all__ = [
    "reload_mykeys",
    "compress_history_tags",
    "trim_messages_history",
    "auto_make_url",
    "_parse_claude_json",
    "_parse_claude_sse",
    "_parse_openai_sse",
    "_parse_openai_json",
    "_stamp_oai_cache_markers",
    "_stream_with_retry",
    "_openai_stream",
    "_prepare_oai_tools",
    "_to_responses_input",
    "_msgs_claude2oai",
    "BaseSession",
    "ClaudeSession",
    "LLMSession",
    "NativeClaudeSession",
    "_fix_messages",
    "_sanitize_leading_user_msg",
    "_try_parse_tool_args",
    "tryparse",
    "safeprint",
    "ToolClient",
    "MixinSession",
    "NativeToolClient",
    "NativeOAISession",
    "openai_tools_to_claude",
    # Google AI Studio
    "GoogleAISession",
    "GoogleAIConfig",
    "tools_to_google_format",
    "parse_google_response",
    "google_function_call_to_tool_call",
]

# ---------------------------------------------------------------------------
# PEP 562 lazy module attribute (mykeys)
# ---------------------------------------------------------------------------

def __getattr__(name: str) -> Any:
    """Lazy attribute access for module-level state like ``mykeys``."""
    if name == 'mykeys':
        from .config import reload_mykeys
        return reload_mykeys()[0]
    raise AttributeError(f"module 'llmcore' has no attribute {name}")

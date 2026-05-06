"""Session classes for LLM communication.

Provides :class:`BaseSession`, :class:`ClaudeSession`, :class:`LLMSession`,
and :class:`MixinSession`.  Also includes the :func:`_openai_stream` helper
and thinking-block utilities.
"""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from typing import Any, Generator

from .convert import _prepare_oai_tools, _to_responses_input, openai_tools_to_claude
from .messages import (
    _drop_unsigned_thinking,
    _ensure_thinking_blocks,
    _fix_messages,
    _keep_claude_block,
    _msgs_claude2oai,
    _sanitize_leading_user_msg,
    _stamp_oai_cache_markers,
    compress_history_tags,
    trim_messages_history,
)
from .parsers import _parse_claude_json, _parse_claude_sse, _parse_openai_json, _parse_openai_sse
from .retry import _stream_with_retry
from .utils import (
    _RESP_CACHE_KEY,
    LLMError,
    logger,
    auto_make_url,
)


# ---------------------------------------------------------------------------
# OpenAI stream construction
# ---------------------------------------------------------------------------

def _openai_stream(sess: BaseSession, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
    """Build and send an OpenAI-compatible request, streaming the response."""
    model, api_mode = sess.model, sess.api_mode
    ml = model.lower()
    temperature = sess.temperature
    if 'kimi' in ml or 'moonshot' in ml:
        temperature = 1
    elif 'minimax' in ml:
        temperature = max(0.01, min(temperature, 1.0))  # MiniMax requires temp in (0, 1]
    headers = {"Authorization": f"Bearer {sess.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_mode == "responses":
        url = auto_make_url(sess.api_base, "responses")
        payload: dict[str, Any] = {"model": model, "input": _to_responses_input(messages), "stream": sess.stream,
                                   "prompt_cache_key": _RESP_CACHE_KEY, "instructions": sess.system or "You are an Omnipotent Executor."}
        if sess.reasoning_effort:
            payload["reasoning"] = {"effort": sess.reasoning_effort}
        if sess.max_tokens:
            payload["max_output_tokens"] = sess.max_tokens
    else:
        url = auto_make_url(sess.api_base, "chat/completions")
        if sess.system:
            messages = [{"role": "system", "content": sess.system}] + messages
        _stamp_oai_cache_markers(messages, model)
        payload = {"model": model, "messages": messages, "stream": sess.stream}
        if sess.stream:
            payload["stream_options"] = {"include_usage": True}
        if temperature != 1:
            payload["temperature"] = temperature
        if sess.max_tokens:
            payload["max_completion_tokens" if ml.startswith(("gpt-5", "o1", "o2", "o3", "o4")) else "max_tokens"] = sess.max_tokens
        if sess.reasoning_effort:
            payload["reasoning_effort"] = sess.reasoning_effort
    tools = getattr(sess, 'tools', None)
    if tools:
        payload["tools"] = _prepare_oai_tools(tools, api_mode)
    if sess.service_tier:
        payload["service_tier"] = sess.service_tier
    parse_fn = (lambda r: _parse_openai_sse(r.iter_lines(), api_mode)) if sess.stream else (lambda r: _parse_openai_json(r.json(), api_mode))
    return (yield from _stream_with_retry(sess, url, headers, payload, parse_fn))


# ---------------------------------------------------------------------------
# Base session class
# ---------------------------------------------------------------------------

class BaseSession:
    """Base class for LLM session management.

    Handles configuration, retry logic, history trimming, and the public
    ``ask()`` interface.  Subclasses must implement ``raw_ask()`` and
    ``make_messages()``.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.api_key: str = cfg['apikey']
        self.api_base: str = cfg['apibase'].rstrip('/')
        self.model: str = cfg.get('model', '')
        self.context_win: int = cfg.get('context_win', 28000)
        self.history: list[dict[str, Any]] = []
        self.lock: threading.Lock = threading.Lock()
        self.system: str = ""
        self.name: str = cfg.get('name', self.model)
        proxy = cfg.get('proxy')
        self.proxies: dict[str, str] | None = {"http": proxy, "https": proxy} if proxy else None
        self.max_retries: int = max(0, int(cfg.get('max_retries', 4)))
        self.verify: bool = cfg.get('verify', True)
        self.stream: bool = cfg.get('stream', True)
        default_ct, default_rt = (5, 30) if self.stream else (10, 240)
        self.connect_timeout: int = max(1, int(cfg.get('timeout', default_ct)))
        self.read_timeout: int = max(5, int(cfg.get('read_timeout', default_rt)))

        def _enum(key: str, valid: set[str]) -> str | None:
            v = cfg.get(key)
            v = None if v is None else str(v).strip().lower()
            if v and v not in valid:
                logger.warning("Invalid %s %r, ignored.", key, v)
                return None
            return v

        self.reasoning_effort: str | None = _enum('reasoning_effort', {'none', 'minimal', 'low', 'medium', 'high', 'xhigh'})
        self.service_tier: str | None = _enum('service_tier', {'auto', 'default', 'priority', 'flex'})
        self.thinking_type: str | None = _enum('thinking_type', {'adaptive', 'enabled', 'disabled'})
        self.thinking_budget_tokens: int | None = cfg.get('thinking_budget_tokens')
        mode = str(cfg.get('api_mode', 'chat_completions')).strip().lower().replace('-', '_')
        self.api_mode: str = 'responses' if mode in ('responses', 'response') else 'chat_completions'
        self.temperature: float = cfg.get('temperature', 1)
        self.max_tokens: int | None = cfg.get('max_tokens')

    def _apply_claude_thinking(self, payload: dict[str, Any]) -> None:
        """Apply thinking/reasoning configuration to a Claude API payload."""
        if self.thinking_type:
            thinking: dict[str, Any] = {"type": self.thinking_type}
            if self.thinking_type == 'enabled':
                if self.thinking_budget_tokens is None:
                    logger.warning("thinking_type='enabled' requires thinking_budget_tokens, ignored.")
                else:
                    thinking["budget_tokens"] = self.thinking_budget_tokens
                    payload["thinking"] = thinking
            else:
                payload["thinking"] = thinking
        if self.reasoning_effort:
            effort = {'low': 'low', 'medium': 'medium', 'high': 'high', 'xhigh': 'max'}.get(self.reasoning_effort)
            if effort:
                payload["output_config"] = {"effort": effort}
            else:
                logger.warning("reasoning_effort %r is unsupported for Claude output_config.effort, ignored.", self.reasoning_effort)

    def ask(self, prompt: str) -> str | Generator[str, None, None]:
        """Send a prompt and return the response.

        If ``self.stream`` is True, returns a generator that yields text
        chunks.  Otherwise, returns the full response as a string.
        """
        def _ask_gen() -> Generator[str, None, None]:
            with self.lock:
                self.history.append({"role": "user", "content": [{"type": "text", "text": prompt}]})
                trim_messages_history(self.history, self.context_win)
                messages = self.make_messages(self.history)
            content_blocks: list[dict[str, Any]] | None = None
            content = ''
            gen = self.raw_ask(messages)
            try:
                while True:
                    chunk = next(gen); content += chunk; yield chunk
            except StopIteration as e:
                content_blocks = e.value or []
            finally:
                # Always append the response, even if generator is not fully consumed
                if content and not content.startswith("!!!Error:"):
                    # Check if assistant response was already appended
                    last = self.history[-1] if self.history else None
                    if not (last and last.get("role") == "assistant" and
                            last.get("content") == [{"type": "text", "text": content}]):
                        self.history.append({"role": "assistant", "content": [{"type": "text", "text": content}]})
            if len(content_blocks) > 1:
                logger.debug("BaseSession.ask content_blocks: %s", content_blocks)
            for block in (content_blocks or []):
                if block.get('type', '') == 'tool_use':
                    tu = {'name': block.get('name', ''), 'arguments': block.get('input', {})}
                    yield f'<tool_use>{json.dumps(tu, ensure_ascii=False)}</tool_use>'
        return _ask_gen() if self.stream else ''.join(list(_ask_gen()))

    # Subclasses must implement these
    def raw_ask(self, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
        """Send messages to the LLM and yield text chunks.  Must be overridden."""
        raise NotImplementedError

    def make_messages(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal history to the format expected by the API.  Must be overridden."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Claude native session
# ---------------------------------------------------------------------------

class ClaudeSession(BaseSession):
    """Session for the Anthropic Claude Messages API (native SSE)."""

    def raw_ask(self, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
        if self.max_tokens is None:
            self.max_tokens = 8192
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01", "anthropic-beta": "prompt-caching-2024-07-31"}
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": self.max_tokens, "stream": self.stream}
        if self.temperature != 1:
            payload["temperature"] = self.temperature
        self._apply_claude_thinking(payload)
        if self.system:
            payload["system"] = [{"type": "text", "text": self.system, "cache_control": {"type": "persistent"}}]
        url = auto_make_url(self.api_base, "messages")
        parse_fn = (lambda r: _parse_claude_sse(r.iter_lines())) if self.stream else (lambda r: _parse_claude_json(r.json()))
        return (yield from _stream_with_retry(self, url, headers, payload, parse_fn))

    def make_messages(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        msgs = _drop_unsigned_thinking([{"role": m['role'], "content": list(m['content'])} for m in raw_list])
        user_idxs = [i for i, m in enumerate(msgs) if m['role'] == 'user']
        for idx in user_idxs[-2:]:
            msgs[idx]["content"][-1] = dict(msgs[idx]["content"][-1], cache_control={"type": "ephemeral"})
        return msgs


# ---------------------------------------------------------------------------
# OpenAI-compatible session
# ---------------------------------------------------------------------------

class LLMSession(BaseSession):
    """Session for OpenAI-compatible chat-completions and responses APIs."""

    def raw_ask(self, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
        return (yield from _openai_stream(self, messages))

    def make_messages(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _msgs_claude2oai(raw_list)


# ---------------------------------------------------------------------------
# MixinSession -- multi-session fallback with spring-back
# ---------------------------------------------------------------------------

class MixinSession:
    """Multi-session fallback with spring-back to primary.

    Distributes requests across multiple backend sessions.  On failure,
    retries with the next session.  After a configurable period
    (``spring_back``), automatically switches back to the primary session.

    All sessions must be of the same type (Native or non-Native).
    """

    _BROADCAST_ATTRS = frozenset({'system', 'tools', 'temperature', 'max_tokens', 'reasoning_effort', 'history'})

    def __init__(self, all_sessions: list[Any], cfg: dict[str, Any]) -> None:
        self._retries: int = cfg.get('max_retries', 3)
        self._base_delay: float = cfg.get('base_delay', 1.5)
        self._spring_sec: float = cfg.get('spring_back', 300)
        self._sessions = []
        for i in cfg.get('llm_nos', []):
            if isinstance(i, int):
                self._sessions.append(all_sessions[i].backend)
            else:
                session = next((s.backend for s in all_sessions if type(s) is not dict and s.backend.name == i), None)
                if session is None:
                    logger.warning(f"No session found for backend '{i}', skipping")
                    continue
                self._sessions.append(session)
        def _is_native(s: Any) -> bool:
            return 'Native' in s.__class__.__name__
        groups = {_is_native(s) for s in self._sessions}
        if len(groups) != 1:
            raise ValueError(f"MixinSession: sessions must be in same group (Native or non-Native), got {[type(s).__name__ for s in self._sessions]}")
        self.name: str = '|'.join(s.name for s in self._sessions)
        self._sessions = [copy.copy(s) for s in self._sessions]
        for s in self._sessions:
            s.max_retries = 0
        self._orig_raw_asks = [s.raw_ask for s in self._sessions]
        self._sessions[0].raw_ask = self._raw_ask  # type: ignore[assignment]
        self.model: str | None = getattr(self._sessions[0], 'model', None)
        self._cur_idx: int = 0
        self._switched_at: float = 0.0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sessions[0], name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._BROADCAST_ATTRS:
            for s in self._sessions:
                # Lazy import to avoid circular dependency with clients module
                if name == 'tools':
                    from .clients import NativeClaudeSession as _NCS
                    v = openai_tools_to_claude(value) if type(s) is _NCS else value
                else:
                    v = value
                setattr(s, name, v)
        else:
            object.__setattr__(self, name, value)

    @property
    def primary(self) -> Any:
        """Return the primary (first) session."""
        return self._sessions[0]

    def _pick(self) -> int:
        """Return the current session index, springing back to primary if enough time has elapsed."""
        if self._cur_idx and time.time() - self._switched_at > self._spring_sec:
            self._cur_idx = 0
        return self._cur_idx

    def _raw_ask(self, *args: Any, **kwargs: Any) -> Generator[str, None, list[dict[str, Any]]]:
        base, n = self._pick(), len(self._sessions)
        test_error = lambda x: isinstance(x, str) and x.lstrip().startswith(('!!!Error:', '[Error:'))
        for attempt in range(self._retries + 1):
            idx = (base + attempt) % n
            gen = self._orig_raw_asks[idx](*args, **kwargs)
            logger.info("[MixinSession] Using session (%s)", self._sessions[idx].name)
            last_chunk: Any = None
            return_val: list[dict[str, Any]] = []
            yielded = False
            try:
                while True:
                    chunk = next(gen); last_chunk = chunk
                    if not yielded and test_error(chunk):
                        continue
                    yield chunk; yielded = True
            except StopIteration as e:
                return_val = e.value or []
            is_err = test_error(last_chunk)
            if not is_err:
                if attempt > 0:
                    self._cur_idx = idx; self._switched_at = time.time()
                elif isinstance(last_chunk, str) and ('stream abnormally interrupted' in last_chunk.lower() or '流异常中断' in last_chunk or 'flux interrompu anormalement' in last_chunk.lower()) and n > 1:
                    self._cur_idx = (idx + 1) % n; self._switched_at = time.time()
                    logger.info("[MixinSession] Partial failure, next call -> s%d (%s)", self._cur_idx, self._sessions[self._cur_idx].name)
                return return_val
            if attempt >= self._retries:
                yield last_chunk; return return_val
            nxt = (base + attempt + 1) % n
            if nxt == base:  # full round failed, delay before next
                rnd = (attempt + 1) // n
                delay = min(30, self._base_delay * (1.5 ** rnd))
                logger.warning("[MixinSession] %s, round %d exhausted, retry in %.1fs", last_chunk[:80], rnd, delay)
                time.sleep(delay)
            else:
                logger.info("[MixinSession] %s, retry %d/%d (s%d->s%d)", last_chunk[:80], attempt + 1, self._retries, idx, nxt)

"""Tool clients and native session classes.

Provides :class:`ToolClient` (text-protocol tool client), :class:`NativeToolClient`
(structured tool-use client), :class:`NativeClaudeSession`, and
:class:`NativeOAISession`.  Also includes mock objects and text tool-call
extraction.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Generator

from .convert import openai_tools_to_claude
from .messages import (
    _drop_unsigned_thinking,
    _ensure_thinking_blocks,
    _fix_messages,
    _msgs_claude2oai,
    trim_messages_history,
)
from .parsers import _parse_claude_json, _parse_claude_sse, _parse_openai_json, _parse_openai_sse, tryparse
from .retry import _stream_with_retry
from .sessions import BaseSession, _openai_stream
from .utils import (
    THINKING_PROMPT_EN,
    THINKING_PROMPT_FR,
    THINKING_PROMPT_ZH,
    _write_llm_log,
    auto_make_url,
    logger,
)


# ---------------------------------------------------------------------------
# Mock objects (for ToolClient / NativeClaudeSession)
# ---------------------------------------------------------------------------

class MockFunction:
    """Lightweight stand-in for an OpenAI function call object."""

    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments

class MockToolCall:
    """Lightweight stand-in for an OpenAI tool-call object."""

    def __init__(self, name: str, args: Any, id: str = '') -> None:
        arg_str = json.dumps(args, ensure_ascii=False) if isinstance(args, (dict, list)) else (args or '{}')
        self.function = MockFunction(name, arg_str)
        self.id = id

class MockResponse:
    """Lightweight stand-in for an LLM response with thinking, content, and tool calls."""

    def __init__(
        self,
        thinking: str,
        content: str,
        tool_calls: list[MockToolCall],
        raw: str,
        stop_reason: str = 'end_turn',
    ) -> None:
        self.thinking = thinking
        self.content = content
        self.tool_calls = tool_calls
        self.raw = raw
        self.stop_reason = 'tool_use' if tool_calls else stop_reason

    def __repr__(self) -> str:
        return f"<MockResponse thinking={bool(self.thinking)}, content='{self.content}', tools={bool(self.tool_calls)}>"


# ---------------------------------------------------------------------------
# Text tool-call extraction
# ---------------------------------------------------------------------------

def _parse_text_tool_calls(content: str) -> tuple[list[MockToolCall], str]:
    """Fallback: extract tool calls from text when the model doesn't use native tool_use blocks.

    Tries JSON array format first, then XML ``<tool_use>`` / ``<tool_call`` tags.

    Returns
    -------
    tuple[list[MockToolCall], str]
        The extracted tool calls and the remaining content with tool calls removed.
    """
    tcs: list[MockToolCall] = []
    # try JSON array: [{"type":"tool_use", "name":..., "input":...}]
    _jp = next((p for p in ['[{"type":"tool_use"', '[{"type": "tool_use"'] if p in content), None)
    if _jp and content.endswith('}]'):
        try:
            idx = content.index(_jp); raw = json.loads(content[idx:])
            tcs = [MockToolCall(b["name"], b.get("input", {}), id=b.get("id", "")) for b in raw if b.get("type") == "tool_use"]
            return tcs, content[:idx].strip()
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("Failed to parse JSON array tool calls: %s", e)
    # try XML tags:  {"name":..., "arguments":...}
    _xp = r"<(?:tool_use|tool_call)>((?:(?!<(?:tool_use|tool_call)>).)+?)</(?:tool_use|tool_call)>"
    for s in re.findall(_xp, content, re.DOTALL):
        try:
            d = tryparse(s.strip()); name = d.get('name')
            args = d.get('arguments') or d.get('args') or d.get('input') or {}
            if name:
                tcs.append(MockToolCall(name, args))
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("Failed to parse XML tool call: %s", e)
    if tcs:
        content = re.sub(_xp, "", content, flags=re.DOTALL).strip()
    return tcs, content


# ---------------------------------------------------------------------------
# Native Claude Code session
# ---------------------------------------------------------------------------

class NativeClaudeSession(BaseSession):
    """Session that uses Claude's native API protocol.

    Supports beta features like interleaved thinking, context-1m, and
    prompt caching scope.  Sends appropriate headers and metadata.

    .. note::
        Previous versions impersonated Claude Code CLI by sending spoofed
        headers (``anthropic-dangerous-direct-browser-access``, ``claude-code-*``
        beta flags, and the ``"You are Claude Code"`` system prompt). This was
        a **security risk** — it violated Anthropic's Terms of Service, could
        trigger account suspension, and misrepresented the software's identity
        to users. All impersonation has been removed.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        super().__init__(cfg)
        self.fake_cc_system_prompt: bool = False  # Disabled: Claude Code impersonation removed (security risk)
        self.user_agent: str = cfg.get("user_agent", "GenericAgent/0.6.0")
        self._session_id: str = str(uuid.uuid4())
        self._account_uuid: str = str(uuid.uuid4())
        self._device_id: str = uuid.uuid4().hex + uuid.uuid4().hex[:32]
        self.tools: list[dict[str, Any]] | None = None

    def raw_ask(self, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
        messages = _ensure_thinking_blocks(_drop_unsigned_thinking(_fix_messages(messages)), self.model)
        if self.max_tokens is None:
            self.max_tokens = 8192
        model = self.model
        # NOTE: "claude-code-20250219" was removed — it impersonated Claude Code CLI (security risk)
        beta_parts = ["interleaved-thinking-2025-05-14", "redact-thinking-2026-02-12", "prompt-caching-scope-2026-01-05"]
        if "[1m]" in model.lower():
            beta_parts.insert(1, "context-1m-2025-08-07")
            model = model.replace("[1m]", "").replace("[1M]", "")
        headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01",
            "anthropic-beta": ",".join(beta_parts),
            "user-agent": self.user_agent, "x-app": "genericagent"}
        if self.api_key.startswith("sk-ant-"):
            headers["x-api-key"] = self.api_key
        else:
            headers["authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": self.max_tokens, "stream": self.stream}
        if self.temperature != 1:
            payload["temperature"] = self.temperature
        self._apply_claude_thinking(payload)
        payload["metadata"] = {"user_id": json.dumps({"device_id": self._device_id, "account_uuid": self._account_uuid, "session_id": self._session_id}, separators=(',', ':'))}
        if self.tools:
            claude_tools = openai_tools_to_claude(self.tools)
            tools = [dict(t) for t in claude_tools]
            tools[-1]["cache_control"] = {"type": "ephemeral"}
            payload["tools"] = tools
        else:
            logger.error("No tools provided for this session.")
        payload['system'] = [{"type": "text", "text": f"You are GenericAgent, an AI desktop assistant powered by {model}.", "cache_control": {"type": "ephemeral"}}]
        if self.system:
            if self.fake_cc_system_prompt:
                messages[0]["content"].insert(0, {"type": "text", "text": self.system})
            else:
                payload["system"] = [{"type": "text", "text": self.system}]
        user_idxs = [i for i, m in enumerate(messages) if m['role'] == 'user']
        for idx in user_idxs[-2:]:
            messages[idx] = {**messages[idx], "content": list(messages[idx]["content"])}
            messages[idx]["content"][-1] = dict(messages[idx]["content"][-1], cache_control={"type": "ephemeral"})
        url = auto_make_url(self.api_base, "messages") + '?beta=true'
        parse_fn = (lambda r: _parse_claude_sse(r.iter_lines())) if self.stream else (lambda r: _parse_claude_json(r.json()))
        return (yield from _stream_with_retry(self, url, headers, payload, parse_fn))

    def ask(self, msg: dict[str, Any]) -> Generator[str, None, MockResponse]:
        """Send a message dict and yield text chunks, returning a MockResponse."""
        if type(msg) is not dict:
            raise TypeError(f"ask() expected a dict message, got {type(msg).__name__}")
        with self.lock:
            self.history.append(msg)
            trim_messages_history(self.history, self.context_win)
            messages = [{"role": m["role"], "content": list(m["content"])} for m in self.history]
        content_blocks: list[dict[str, Any]] | None = None
        gen = self.raw_ask(messages)
        try:
            while True:
                yield next(gen)
        except StopIteration as e:
            content_blocks = e.value or []
        if content_blocks and not (len(content_blocks) == 1 and content_blocks[0].get("text", "").startswith("!!!Error:")):
            self.history.append({"role": "assistant", "content": content_blocks})
        text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        content = "\n".join(text_parts).strip()
        tool_calls = [MockToolCall(b["name"], b.get("input", {}), id=b.get("id", "")) for b in content_blocks if b.get("type") == "tool_use"]
        if not tool_calls:
            tool_calls, content = _parse_text_tool_calls(content)
        thinking_parts = [b["thinking"] for b in content_blocks if b.get("type") == "thinking"]
        thinking = "\n".join(thinking_parts).strip()
        if not thinking:
            think_pattern = r"<think(?:ing)?>(.*?)</think(?:ing)?>"
            think_match = re.search(think_pattern, content, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                content = re.sub(think_pattern, "", content, flags=re.DOTALL)
        return MockResponse(thinking, content, tool_calls, str(content_blocks))


# ---------------------------------------------------------------------------
# Native OAI session
# ---------------------------------------------------------------------------

class NativeOAISession(NativeClaudeSession):
    """Native session that uses OpenAI-compatible API format instead of Claude's native protocol."""

    def raw_ask(self, messages: list[dict[str, Any]]) -> Generator[str, None, list[dict[str, Any]]]:
        messages = _fix_messages(messages)
        messages = _ensure_thinking_blocks(messages, self.model)
        return (yield from _openai_stream(self, _msgs_claude2oai(messages)))


# ---------------------------------------------------------------------------
# ToolClient -- text-based tool protocol
# ---------------------------------------------------------------------------

class ToolClient:
    """Text-protocol tool client that wraps a BaseSession.

    Injects a tool-use protocol prompt and parses ``<tool_use>`` XML blocks
    from the model's text output.
    """

    # Token-cost threshold beyond which tool descriptions are force-refreshed
    # to prevent context bloat from degrading model performance.
    _TOKEN_COST_REFRESH_THRESHOLD: int = 9000

    def __init__(self, backend: BaseSession, auto_save_tokens: bool = True) -> None:
        self.backend = backend
        self.auto_save_tokens = auto_save_tokens
        self.last_tools: str = ''
        self.name: str = self.backend.name
        self.total_cd_tokens: int = 0

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Generator[str, None, MockResponse]:
        """Send messages with optional tools and yield text chunks, returning a MockResponse."""
        full_prompt = self._build_protocol_prompt(messages, tools)
        logger.debug("Full prompt length: %d chars", len(full_prompt))
        gen = self.backend.ask(full_prompt)
        _write_llm_log('Prompt', full_prompt)
        raw_text = ''
        for chunk in gen:
            raw_text += chunk; yield chunk
        _write_llm_log('Response', raw_text)
        return self._parse_mixed_response(raw_text)

    def _prepare_tool_instruction(self, tools: list[dict[str, Any]] | None) -> str:
        """Build the tool instruction prompt section based on language and tools."""
        tool_instruction = ""
        if not tools:
            return tool_instruction
        tools_json = json.dumps(tools, ensure_ascii=False, separators=(',', ':'))
        _en = os.environ.get('GA_LANG') == 'en'
        if _en:
            tool_instruction = f"""
### Interaction Protocol (must follow strictly, always in effect)
Follow these steps to think and act:
1. **Think**: Analyze the current situation and strategy inside `<thinking>` tags.
2. **Summarize**: Output a minimal one-line (<30 words) physical snapshot in `<summary>`: new info from last tool result + current tool call intent. This goes into long-term working memory. Must contain real information, no filler.
3. **Act**: If you need to call tools, output one or more **<tool_use> blocks** after your reply, then stop.
"""
        elif os.environ.get('GA_LANG') == 'zh':
            tool_instruction = f"""
### 交互协议 (必须严格遵守，持续有效)
请按照以下步骤思考并行动：
1. **思考**: 在 `<thinking>` 标签中先进行思考，分析现状和策略。
2. **总结**: 在 `<summary>` 中输出*极为简短*的高度概括的单行（<30字）物理快照，包括上次工具调用结果产生的新信息+本次工具调用意图。此内容将进入长期工作记忆，记录关键信息，严禁输出无实际信息增量的描述。
3. **行动**: 如需调用工具，请在回复正文之后输出一个（或多个）**<tool_use>块**，然后结束。
"""
        else:
            tool_instruction = f"""
### Protocole d'interaction (obligatoire, toujours en vigueur)
Suivez ces étapes pour réfléchir et agir :
1. **Réflexion** : Analysez la situation et la stratégie dans les balises `<thinking>`.
2. **Résumé** : Produisez un instantané minimaliste en une ligne (<30 mots) dans `<summary>` : nouvelles infos du dernier résultat + intention de l'appel d'outil. Ce contenu entre dans la mémoire de travail à long terme. Interdiction de produire du remplissage sans information réelle.
3. **Action** : Si vous devez appeler un outil, produisez un ou plusieurs **blocs <tool_use>** après votre réponse, puis arrêtez.
"""
        tool_instruction += f'\nFormat: ```<tool_use>{{"name": "tool_name", "arguments": {{...}}}}</tool_use>```\n\n### Tools (mounted, always in effect):\n{tools_json}\n'
        if self.auto_save_tokens and self.last_tools == tools_json:
            tool_instruction = "\n### Tools: still active, **ready to call**. Protocol unchanged.\n" if _en else "\n### Outils toujours actifs, **prêts à l'emploi**. Protocole inchangé.\n"
        else:
            self.total_cd_tokens = 0
        self.last_tools = tools_json
        return tool_instruction

    def _build_protocol_prompt(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
        """Build the full prompt string from messages and tool instructions."""
        system_content = next((m['content'] for m in messages if m['role'].lower() == 'system'), "")
        history_msgs = [m for m in messages if m['role'].lower() != 'system']
        tool_instruction = self._prepare_tool_instruction(tools)
        system = ""; user = ""
        if system_content:
            system += f"{system_content}\n"
        system += f"{tool_instruction}"
        for m in history_msgs:
            role = "USER" if m['role'] == 'user' else "ASSISTANT"
            user += f"=== {role} ===\n"
            for tr in m.get('tool_results', []):
                user += f'<tool_result>{tr["content"]}</tool_result>\n'
            user += str(m['content']) + "\n"
            self.total_cd_tokens += len(user) // 3
        if self.total_cd_tokens > self._TOKEN_COST_REFRESH_THRESHOLD:
            self.last_tools = ''
        user += "=== ASSISTANT ===\n"
        return system + user

    def _parse_mixed_response(self, text: str) -> MockResponse:
        """Parse a mixed text response that may contain thinking, tool calls, and content."""
        remaining_text = text; thinking = ''
        think_match = re.search(r"<think(?:ing)?>(.*?)</think(?:ing)?>", text, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            remaining_text = re.sub(r"<think(?:ing)?>(.*?)</think(?:ing)?>", "", remaining_text, flags=re.DOTALL)
        tool_calls, remaining_text = _parse_text_tool_calls(remaining_text)
        if not tool_calls:
            json_strs: list[str] = []
            errors: list[str] = []
            if '<tool_use>' in remaining_text:
                weaktoolstr = remaining_text.split('<tool_use>')[-1].strip().strip('><')
                json_str = weaktoolstr if weaktoolstr.endswith('}') else ''
                if json_str == '' and '```' in weaktoolstr and weaktoolstr.split('```')[0].strip().endswith('}'):
                    json_str = weaktoolstr.split('```')[0].strip()
                if json_str:
                    json_strs.append(json_str)
                remaining_text = remaining_text.replace('<tool_use>' + weaktoolstr, "")
            elif '"name":' in remaining_text and '"arguments":' in remaining_text:
                # Robust JSON extraction: handle nested objects by
                # tracking brace depth instead of using a regex that
                # can't match nested structures.
                i = 0
                while i < len(remaining_text):
                    start = remaining_text.find('{', i)
                    if start == -1:
                        break
                    # Try to parse a JSON object from this position
                    depth = 0
                    j = start
                    found = False
                    while j < len(remaining_text):
                        if remaining_text[j] == '{':
                            depth += 1
                        elif remaining_text[j] == '}':
                            depth -= 1
                            if depth == 0:
                                try:
                                    obj = json.loads(remaining_text[start:j+1])
                                    if isinstance(obj, dict) and ('name' in obj or 'arguments' in obj):
                                        json_strs.append(remaining_text[start:j+1].strip())
                                        remaining_text = remaining_text[:start] + remaining_text[j+1:]
                                        found = True
                                except (json.JSONDecodeError, ValueError):
                                    pass
                                break
                        j += 1
                    if found:
                        # Don't advance i, since remaining_text was modified
                        continue
                    i = start + 1
            for json_str in json_strs:
                try:
                    data = tryparse(json_str)
                    func_name = data.get('name') or data.get('function') or data.get('tool')
                    args = data.get('arguments') or data.get('args') or data.get('params') or data.get('parameters')
                    if args is None:
                        args = data
                    if func_name:
                        tool_calls.append(MockToolCall(func_name, args))
                except json.JSONDecodeError:
                    errors.append(f'Failed to parse tool_use JSON: {json_str[:200]}')
                    self.last_tools = ''
                except Exception as e:
                    logger.debug("Unexpected error parsing tool call: %s", e)
            if not tool_calls:
                for e in errors:
                    logger.warning("%s", e)
                    tool_calls.append(MockToolCall('bad_json', {'msg': e}))
        return MockResponse(thinking, remaining_text.strip(), tool_calls, text)


# ---------------------------------------------------------------------------
# NativeToolClient
# ---------------------------------------------------------------------------

class NativeToolClient:
    """Tool client for native Claude / OAI sessions using structured tool-use blocks.

    Manages system prompts, pending tool IDs, and message assembly for
    sessions that support native tool calling (``NativeClaudeSession``,
    ``NativeOAISession``).
    """

    @staticmethod
    def _thinking_prompt() -> str:
        """Return the thinking prompt in the configured language."""
        _lang = os.environ.get('GA_LANG', '').strip().lower()
        if _lang == 'en':
            return THINKING_PROMPT_EN
        if _lang == 'zh':
            return THINKING_PROMPT_ZH
        return THINKING_PROMPT_FR  # Francais par defaut

    def __init__(self, backend: NativeClaudeSession) -> None:
        self.backend = backend
        self.backend.system = self._thinking_prompt()
        self.name: str = self.backend.name
        self._pending_tool_ids: list[str] = []

    def set_system(self, extra_system: str) -> None:
        """Set or extend the system prompt, preserving the thinking protocol."""
        combined = f"{extra_system}\n\n{self._thinking_prompt()}" if extra_system else self._thinking_prompt()
        if combined != self.backend.system:
            logger.debug("Updated system prompt, length %d chars.", len(combined))
        self.backend.system = combined

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Generator[str, None, MockResponse | None]:
        """Send messages with optional tools, yielding text chunks and returning a MockResponse."""
        if tools:
            self.backend.tools = tools
        combined_content: list[dict[str, Any]] = []
        resp: MockResponse | None = None
        tool_results: list[dict[str, Any]] = []
        for msg in messages:
            c = msg.get('content', '')
            if msg['role'] == 'system':
                self.set_system(c); continue
            if isinstance(c, str):
                combined_content.append({"type": "text", "text": c})
            elif isinstance(c, list):
                combined_content.extend(c)
            if msg['role'] == 'user' and msg.get('tool_results'):
                tool_results.extend(msg['tool_results'])
        tr_id_set: set[str] = set()
        tool_result_blocks: list[dict[str, Any]] = []
        for tr in tool_results:
            tool_use_id, content = tr.get("tool_use_id", ""), tr.get("content", "")
            tr_id_set.add(tool_use_id)
            if tool_use_id:
                tool_result_blocks.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": tr.get("content", "")})
            else:
                combined_content = [{"type": "text", "text": f'<tool_result>{content}</tool_result>'}] + combined_content
        for tid in self._pending_tool_ids:
            if tid not in tr_id_set:
                tool_result_blocks.append({"type": "tool_result", "tool_use_id": tid, "content": ""})
        self._pending_tool_ids = []
        merged: dict[str, Any] = {"role": "user", "content": tool_result_blocks + combined_content}
        _write_llm_log('Prompt', json.dumps(merged, ensure_ascii=False, indent=2))
        gen = self.backend.ask(merged)
        try:
            while True:
                chunk = next(gen); yield chunk
        except StopIteration as e:
            resp = e.value
        if resp:
            _write_llm_log('Response', resp.raw)
        if resp and hasattr(resp, 'tool_calls') and resp.tool_calls:
            self._pending_tool_ids = [tc.id for tc in resp.tool_calls]
        return resp

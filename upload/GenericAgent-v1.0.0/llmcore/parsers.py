"""SSE/JSON stream parsing for Claude and OpenAI APIs.

Provides generator-based parsers that yield text chunks and return
content blocks in a unified format.
"""

from __future__ import annotations

import json
import re
from typing import Any, Generator

from .utils import _record_usage, logger


# ---------------------------------------------------------------------------
# Claude SSE / JSON parsing
# ---------------------------------------------------------------------------

def _parse_claude_json(data: dict[str, Any]) -> Generator[str, None, list[dict[str, Any]]]:
    """Parse a non-streaming Claude Messages API response.

    Yields text chunks and returns the list of content blocks.
    """
    content_blocks: list[dict[str, Any]] = data.get("content", [])
    _record_usage(data.get("usage", {}), "messages")
    for b in content_blocks:
        if b.get("type") == "text":
            yield b.get("text", "")
        elif b.get("type") == "thinking":
            yield ""
    return content_blocks

def _parse_claude_sse(resp_lines: Any) -> Generator[str, None, list[dict[str, Any]]]:
    """Parse an Anthropic SSE stream.

    Yields text chunks and returns the list of content blocks.
    Content blocks follow the Claude content-block schema:
    ``{type:'text', text:str}``, ``{type:'thinking', thinking:str, signature:str}``,
    or ``{type:'tool_use', id:str, name:str, input:dict}``.
    """
    content_blocks: list[dict[str, Any]] = []
    current_block: dict[str, Any] | None = None
    tool_json_buf = ""
    stop_reason: str | None = None
    got_message_stop = False
    warn: str | None = None

    for line in resp_lines:
        if not line:
            continue
        line = line.decode('utf-8') if isinstance(line, bytes) else line
        if not line.startswith("data:"):
            continue
        data_str = line[5:].lstrip()
        if data_str == "[DONE]":
            break
        try:
            evt = json.loads(data_str)
        except Exception as e:
            logger.warning("[SSE] JSON parse error: %s, line: %s", e, data_str[:200])
            continue
        evt_type = evt.get("type", "")
        if evt_type == "message_start":
            usage = evt.get("message", {}).get("usage", {})
            _record_usage(usage, "messages")
        elif evt_type == "content_block_start":
            block = evt.get("content_block", {})
            if block.get("type") == "text":
                current_block = {"type": "text", "text": ""}
            elif block.get("type") == "thinking":
                current_block = {"type": "thinking", "thinking": "", "signature": ""}
            elif block.get("type") == "tool_use":
                current_block = {"type": "tool_use", "id": block.get("id", ""), "name": block.get("name", ""), "input": {}}
                tool_json_buf = ""
        elif evt_type == "content_block_delta":
            delta = evt.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if current_block and current_block.get("type") == "text":
                    current_block["text"] += text
                if text:
                    yield text
            elif delta.get("type") == "thinking_delta":
                if current_block and current_block.get("type") == "thinking":
                    current_block["thinking"] += delta.get("thinking", "")
            elif delta.get("type") == "signature_delta":
                if current_block and current_block.get("type") == "thinking":
                    current_block["signature"] = current_block.get("signature", "") + delta.get("signature", "")
            elif delta.get("type") == "input_json_delta":
                tool_json_buf += delta.get("partial_json", "")
        elif evt_type == "content_block_stop":
            if current_block:
                if current_block["type"] == "tool_use":
                    try:
                        current_block["input"] = json.loads(tool_json_buf) if tool_json_buf else {}
                    except (json.JSONDecodeError, ValueError):
                        current_block["input"] = {"_raw": tool_json_buf}
                content_blocks.append(current_block)
                current_block = None
        elif evt_type == "message_delta":
            delta = evt.get("delta", {})
            stop_reason = delta.get("stop_reason", stop_reason)
            out_usage = evt.get("usage", {})
            out_tokens = out_usage.get("output_tokens", 0)
            if out_tokens:
                logger.debug("[Output] tokens=%d stop_reason=%s", out_tokens, stop_reason)
        elif evt_type == "message_stop":
            got_message_stop = True
        elif evt_type == "error":
            err = evt.get("error", {})
            emsg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            warn = f"\n\n!!!Error: SSE {emsg}"
            break
    if not warn:
        if not got_message_stop and not stop_reason:
            warn = "\n\n[!!! Stream abnormally interrupted, complete response not received !!!]"
        elif stop_reason == "max_tokens":
            warn = "\n\n[!!! Response truncated: max_tokens !!!]"
    # Flush any unfinished block
    if current_block:
        if current_block["type"] == "tool_use":
            try:
                current_block["input"] = json.loads(tool_json_buf) if tool_json_buf else {}
            except (json.JSONDecodeError, ValueError):
                current_block["input"] = {"_raw": tool_json_buf}
        content_blocks.append(current_block)
        current_block = None
    if warn:
        logger.warning("%s", warn.strip())
        content_blocks.append({"type": "text", "text": warn})
        yield warn
    return content_blocks

# ---------------------------------------------------------------------------
# Tool-arg parsing helpers
# ---------------------------------------------------------------------------

def _try_parse_tool_args(raw: str | None) -> list[dict[str, Any]]:
    """Parse tool args string; split concatenated JSON objects like ``{..}{..}`` if needed.

    Returns a list of parsed dicts.  If parsing fails entirely, returns
    ``[{"_raw": raw}]`` so that callers can still inspect the raw string.
    """
    if not raw:
        return [{}]
    try:
        return [json.loads(raw)]
    except (json.JSONDecodeError, ValueError):
        pass
    parts = re.split(r'(?<=\})(?=\{)', raw)
    if len(parts) > 1:
        parsed: list[dict[str, Any]] = []
        for p in parts:
            try:
                parsed.append(json.loads(p))
            except (json.JSONDecodeError, ValueError):
                return [{"_raw": raw}]
        return parsed
    return [{"_raw": raw}]

# ---------------------------------------------------------------------------
# OpenAI SSE / JSON parsing
# ---------------------------------------------------------------------------

def _parse_openai_sse(
    resp_lines: Any,
    api_mode: str = "chat_completions",
) -> Generator[str, None, list[dict[str, Any]]]:
    """Parse an OpenAI SSE stream (chat_completions or responses API).

    Yields text chunks and returns a list of content blocks in the same
    format as ``_parse_claude_sse``:
    ``{type:'text', text:str}``, ``{type:'thinking', thinking:str}``,
    or ``{type:'tool_use', id:str, name:str, input:dict}``.
    """
    content_text = ""
    if api_mode == "responses":
        seen_delta = False
        fc_buf: dict[int, dict[str, Any]] = {}
        current_fc_idx: int | None = None
        for line in resp_lines:
            if not line:
                continue
            line = line.decode('utf-8', errors='replace') if isinstance(line, bytes) else line
            if not line.startswith("data:"):
                continue
            data_str = line[5:].lstrip()
            if data_str == "[DONE]":
                break
            try:
                evt = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                continue
            etype = evt.get("type", "")
            if etype == "response.output_text.delta":
                delta = evt.get("delta", "")
                if delta:
                    seen_delta = True; content_text += delta; yield delta
            elif etype == "response.output_text.done" and not seen_delta:
                text = evt.get("text", "")
                if text:
                    content_text += text; yield text
            elif etype == "response.output_item.added":
                item = evt.get("item", {})
                if item.get("type") == "function_call":
                    idx = evt.get("output_index", 0)
                    fc_buf[idx] = {"id": item.get("call_id", item.get("id", "")), "name": item.get("name", ""), "args": ""}
                    current_fc_idx = idx
            elif etype == "response.function_call_arguments.delta":
                idx = evt.get("output_index", current_fc_idx or 0)
                if idx in fc_buf:
                    fc_buf[idx]["args"] += evt.get("delta", "")
            elif etype == "response.function_call_arguments.done":
                idx = evt.get("output_index", current_fc_idx or 0)
                if idx in fc_buf:
                    fc_buf[idx]["args"] = evt.get("arguments", fc_buf[idx]["args"])
            elif etype == "error":
                err = evt.get("error", {})
                emsg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                if emsg:
                    content_text += f"!!!Error: {emsg}"; yield f"!!!Error: {emsg}"
                break
            elif etype == "response.completed":
                usage = evt.get("response", {}).get("usage", {})
                _record_usage(usage, api_mode)
                break
        blocks: list[dict[str, Any]] = []
        if content_text:
            blocks.append({"type": "text", "text": content_text})
        for idx in sorted(fc_buf):
            fc = fc_buf[idx]
            inps = _try_parse_tool_args(fc["args"])
            for i, inp in enumerate(inps):
                bid = fc["id"] or ''
                if len(inps) > 1:
                    bid = f"{bid}_{i}" if bid else f"split_{i}"
                blocks.append({"type": "tool_use", "id": bid, "name": fc["name"], "input": inp})
        return blocks
    else:
        # chat_completions mode
        tc_buf: dict[int, dict[str, Any]] = {}  # index -> {id, name, args}
        reasoning_text = ""
        for line in resp_lines:
            if not line:
                continue
            line = line.decode('utf-8', errors='replace') if isinstance(line, bytes) else line
            if not line.startswith("data:"):
                continue
            data_str = line[5:].lstrip()
            if data_str == "[DONE]":
                break
            try:
                evt = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                continue
            ch = (evt.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if delta.get("reasoning_content"):
                reasoning_text += delta["reasoning_content"]
            if delta.get("content"):
                text = delta["content"]; content_text += text; yield text
            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                has_name = bool(tc.get("function", {}).get("name"))
                if idx not in tc_buf:
                    if has_name or not tc_buf:
                        tc_buf[idx] = {"id": tc.get("id") or '', "name": "", "args": ""}
                    else:
                        idx = max(tc_buf)  # type: ignore[assignment]
                if has_name:
                    tc_buf[idx]["name"] = tc["function"]["name"]
                if tc.get("function", {}).get("arguments"):
                    tc_buf[idx]["args"] += tc["function"]["arguments"]
                if tc.get("id") and not tc_buf[idx]["id"]:
                    tc_buf[idx]["id"] = tc["id"]
            usage = evt.get("usage")
            if usage:
                _record_usage(usage, api_mode)
        blocks = []
        if reasoning_text:
            blocks.append({"type": "thinking", "thinking": reasoning_text})
        if content_text:
            blocks.append({"type": "text", "text": content_text})
        for idx in sorted(tc_buf):
            tc = tc_buf[idx]
            inps = _try_parse_tool_args(tc["args"])
            for i, inp in enumerate(inps):
                bid = tc["id"] or ''
                if len(inps) > 1:
                    bid = f"{bid}_{i}" if bid else f"split_{i}"
                blocks.append({"type": "tool_use", "id": bid, "name": tc["name"], "input": inp})
        return blocks

def _parse_openai_json(
    data: dict[str, Any],
    api_mode: str = "chat_completions",
) -> Generator[str, None, list[dict[str, Any]]]:
    """Parse a non-streaming OpenAI API response.

    Yields text chunks and returns the list of content blocks.
    """
    blocks: list[dict[str, Any]] = []
    if api_mode == "responses":
        _record_usage(data.get("usage") or {}, api_mode)
        for item in (data.get("output") or []):
            if item.get("type") == "message":
                for p in (item.get("content") or []):
                    if p.get("type") in ("output_text", "text") and p.get("text"):
                        blocks.append({"type": "text", "text": p["text"]}); yield p["text"]
            elif item.get("type") == "function_call":
                try:
                    args = json.loads(item.get("arguments", "")) if item.get("arguments") else {}
                except (json.JSONDecodeError, ValueError):
                    args = {"_raw": item.get("arguments", "")}
                blocks.append({"type": "tool_use", "id": item.get("call_id", item.get("id", "")),
                               "name": item.get("name", ""), "input": args})
    else:
        _record_usage(data.get("usage") or {}, api_mode)
        msg = (data.get("choices") or [{}])[0].get("message", {})
        reasoning = msg.get("reasoning_content", "")
        if reasoning:
            blocks.append({"type": "thinking", "thinking": reasoning})
        content = msg.get("content", "")
        if content:
            blocks.append({"type": "text", "text": content}); yield content
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "")) if fn.get("arguments") else {}
            except (json.JSONDecodeError, ValueError):
                args = {"_raw": fn.get("arguments", "")}
            blocks.append({"type": "tool_use", "id": tc.get("id", ""), "name": fn.get("name", ""), "input": args})
    return blocks

# ---------------------------------------------------------------------------
# JSON parsing utility
# ---------------------------------------------------------------------------

def tryparse(json_str: str) -> Any:
    """Attempt to parse a JSON string with multiple fallback strategies.

    Tries, in order:
    1. Direct ``json.loads``
    2. Strip markdown fences and leading ``json``
    3. Remove the last character (trailing comma, etc.)
    4. Truncate to the last closing brace
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass
    json_str = json_str.strip().strip('`').replace('json\n', '', 1).strip()
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return json.loads(json_str[:-1])
    except (json.JSONDecodeError, ValueError):
        pass
    if '}' in json_str:
        json_str = json_str[:json_str.rfind('}') + 1]
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        # All strategies failed — return a best-effort wrapper
        return {"_raw": json_str}

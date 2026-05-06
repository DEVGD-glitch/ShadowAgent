"""Message conversion helpers: OpenAI Responses API input, tool preparation.

Provides :func:`_to_responses_input` for converting to the OpenAI Responses
API format, :func:`_prepare_oai_tools` for tool format conversion, and
:func:`openai_tools_to_claude` for OpenAI-to-Claude tool conversion.
"""

from __future__ import annotations

import uuid
from typing import Any


def _prepare_oai_tools(tools: list[dict[str, Any]], api_mode: str = "chat_completions") -> list[dict[str, Any]]:
    """Convert tools to the format expected by the given API mode.

    For the ``responses`` API, each ``{type:'function', function:{...}}`` is
    flattened to ``{type:'function', name, description, parameters}``.
    For ``chat_completions``, tools are passed through unchanged.
    """
    if api_mode == "responses":
        resp_tools: list[dict[str, Any]] = []
        for t in tools:
            if t.get("type") == "function" and "function" in t:
                rt: dict[str, Any] = {"type": "function"}; rt.update(t["function"])
                resp_tools.append(rt)
            else:
                resp_tools.append(t)
        return resp_tools
    return tools


def _to_responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert chat-completions messages to OpenAI Responses API input format.

    Handles role mapping (``system`` -> ``developer``), tool messages, and
    content-block restructuring.
    """
    result: list[dict[str, Any]] = []
    pending: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).lower()
        if role == "tool":
            cid = msg.get("tool_call_id") or (pending.pop(0) if pending else f"call_{uuid.uuid4().hex[:8]}")
            result.append({"type": "function_call_output", "call_id": cid, "output": msg.get("content", "")})
            continue
        if role not in ["user", "assistant", "system", "developer"]:
            role = "user"
        if role == "system":
            role = "developer"  # Responses API uses 'developer' instead of 'system'
        content = msg.get("content", "")
        text_type = "output_text" if role == "assistant" else "input_text"
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            if content:
                parts.append({"type": text_type, "text": content})
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text", "")
                    if text:
                        parts.append({"type": text_type, "text": text})
                elif ptype == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url and role != "assistant":
                        parts.append({"type": "input_image", "image_url": url})
        if len(parts) == 0:
            parts = [{"type": text_type, "text": str(content) if not isinstance(content, list) else '[empty]'}]
        result.append({"role": role, "content": parts})
        pending = []
        for tc in (msg.get("tool_calls") or []):
            f = tc.get("function", {})
            cid = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
            pending.append(cid)
            result.append({"type": "function_call", "call_id": cid, "name": f.get("name", ""), "arguments": f.get("arguments", "")})
    return result


def openai_tools_to_claude(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-format tools to Claude-format tools.

    ``[{type:'function', function:{name, description, parameters}}]``
    -> ``[{name, description, input_schema}]``.

    Tools already in Claude format (having ``input_schema``) are passed
    through unchanged.
    """
    result: list[dict[str, Any]] = []
    for t in tools:
        if 'input_schema' in t:
            result.append(t)
            continue
        fn = t.get('function', t)
        result.append({'name': fn['name'], 'description': fn.get('description', ''),
            'input_schema': fn.get('parameters', {'type': 'object', 'properties': {}})})
    return result

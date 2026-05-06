"""Message manipulation: compression, sanitization, trimming, and conversion.

Provides functions for compressing history tags, sanitizing leading user
messages, trimming message history, stamping cache markers, converting
between Claude and OpenAI message formats, and fixing Claude API
constraint violations.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .utils import logger


# ---------------------------------------------------------------------------
# History compression
# ---------------------------------------------------------------------------

def compress_history_tags(
    messages: list[dict[str, Any]],
    keep_recent: int = 10,
    max_len: int = 800,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Compress <thinking>/<tool_use>/<tool_result> tags in older messages to save tokens.

    Operates every 5th call (or when *force* is True).  Long content inside
    the specified tags is truncated to *max_len* characters in the older
    messages (those before *keep_recent* from the end).
    """
    compress_history_tags._cd = getattr(compress_history_tags, '_cd', 0) + 1  # type: ignore[attr-defined]
    if force:
        compress_history_tags._cd = 0  # type: ignore[attr-defined]
    if compress_history_tags._cd % 5 != 0:  # type: ignore[attr-defined]
        return messages
    _before = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    _pats = {tag: re.compile(rf'(<{tag}>)([\s\S]*?)(</{tag}>)') for tag in ('thinking', 'think', 'tool_use', 'tool_result')}
    _hist_pat = re.compile(r'<(history|key_info)>[\s\S]*?</\1>')

    def _trunc_str(s: str) -> str:
        if isinstance(s, str) and len(s) > max_len:
            return s[:max_len // 2] + '\n...[Truncated]...\n' + s[-max_len // 2:]
        return s

    def _trunc(text: str) -> str:
        text = _hist_pat.sub(lambda m: f'<{m.group(1)}>[...]</{m.group(1)}>', text)
        for pat in _pats.values():
            text = pat.sub(lambda m: m.group(1) + _trunc_str(m.group(2)) + m.group(3), text)
        return text

    for i, msg in enumerate(messages):
        if i >= len(messages) - keep_recent:
            break
        c = msg['content']
        if isinstance(c, str):
            msg['content'] = _trunc(c)
        elif isinstance(c, list):
            for b in c:
                if not isinstance(b, dict):
                    continue
                t = b.get('type')
                if t == 'text' and isinstance(b.get('text'), str):
                    b['text'] = _trunc(b['text'])
                elif t == 'tool_result':
                    tc = b.get('content')
                    if isinstance(tc, str):
                        b['content'] = _trunc_str(tc)
                    elif isinstance(tc, list):
                        for sub in tc:
                            if isinstance(sub, dict) and sub.get('type') == 'text':
                                sub['text'] = _trunc_str(sub.get('text'))
                elif t == 'tool_use' and isinstance(b.get('input'), dict):
                    for k, v in b['input'].items():
                        b['input'][k] = _trunc_str(v)
    after = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    logger.debug("[Cut] %d -> %d", _before, after)
    return messages

# ---------------------------------------------------------------------------
# Message sanitization
# ---------------------------------------------------------------------------

def _sanitize_leading_user_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Rewrite tool_result blocks in user messages as plain text to avoid orphan references.

    The history uses the Claude content-block format where ``content`` is a
    list of blocks.  When a user message becomes the leading message after
    trimming, any ``tool_result`` blocks must be flattened to plain text
    because their matching ``tool_use`` blocks may have been removed.
    """
    msg = dict(msg)  # Shallow copy
    content = msg.get('content')
    if not isinstance(content, list):
        return msg
    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'tool_result':
            c = block.get('content', '')
            if isinstance(c, list):
                texts.extend(b.get('text', '') for b in c if isinstance(b, dict))
            else:
                texts.append(str(c))
        elif block.get('type') == 'text':
            texts.append(block.get('text', ''))
    msg['content'] = [{"type": "text", "text": '\n'.join(t for t in texts if t)}]
    return msg

# ---------------------------------------------------------------------------
# History trimming
# ---------------------------------------------------------------------------

def trim_messages_history(history: list[dict[str, Any]], context_win: int) -> None:
    """Trim message history to fit within the context window.

    If the total character count exceeds ``context_win * 3``, messages are
    progressively removed from the front (oldest first), with compression
    applied more aggressively.

    This function uses an O(n) algorithm: message costs are pre-calculated
    once and decremented as messages are trimmed, avoiding the O(n²) pattern
    of recalculating ``json.dumps`` on every iteration.
    """
    compress_history_tags(history)
    # Pre-calculate the cost of each message once — O(n)
    msg_costs = [len(json.dumps(m, ensure_ascii=False)) for m in history]
    cost = sum(msg_costs)
    logger.debug("Current context: %d chars, %d messages.", cost, len(history))
    if cost > context_win * 3:
        compress_history_tags(history, keep_recent=4, force=True)
        # Recalculate costs after forced compression may have modified messages
        msg_costs = [len(json.dumps(m, ensure_ascii=False)) for m in history]
        cost = sum(msg_costs)
        target = context_win * 3 * 0.6
        # Find the cut point — O(n) single pass instead of repeated O(n) pop(0)
        cut = 0
        n = len(history)
        while cut < n - 5 and cost > target:
            # Remove one message from the front
            cost -= msg_costs[cut]
            cut += 1
            # Skip any non-user messages that follow (they belong to the removed round)
            while cut < n - 5 and history[cut].get('role') != 'user':
                cost -= msg_costs[cut]
                cut += 1
        # Apply the trim in a single operation — O(n) once, not O(n) per iteration
        if cut > 0:
            del history[:cut]
            # Sanitize the leading user message (its matching tool_use may have been removed)
            if history and history[0].get('role') == 'user':
                history[0] = _sanitize_leading_user_msg(history[0])
        logger.debug("Trimmed context, current: %d chars, %d messages.", cost, len(history))

# ---------------------------------------------------------------------------
# Cache markers
# ---------------------------------------------------------------------------

def _stamp_oai_cache_markers(messages: list[dict[str, Any]], model: str) -> None:
    """Add ``cache_control`` to the last 2 user messages for Anthropic models via OAI-compatible relay.

    This enables prompt caching on the relay's side when forwarding to the
    Anthropic API.  Non-Anthropic models are skipped.
    """
    ml = model.lower()
    if not any(k in ml for k in ('claude', 'anthropic')):
        return
    user_idxs = [i for i, m in enumerate(messages) if m.get('role') == 'user']
    for idx in user_idxs[-2:]:
        c = messages[idx].get('content')
        if isinstance(c, str):
            messages[idx] = {**messages[idx], 'content': [{'type': 'text', 'text': c, 'cache_control': {'type': 'ephemeral'}}]}
        elif isinstance(c, list) and c:
            c = list(c); c[-1] = dict(c[-1], cache_control={'type': 'ephemeral'})
            messages[idx] = {**messages[idx], 'content': c}

# ---------------------------------------------------------------------------
# Message conversion: Claude -> OpenAI
# ---------------------------------------------------------------------------

def _msgs_claude2oai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert messages from Claude content-block format to OpenAI chat-completions format.

    Handles ``thinking``, ``text``, ``tool_use``, ``tool_result``, and
    ``image`` content blocks.
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        if role == "assistant":
            text_parts: list[dict[str, Any]] = []
            tool_calls: list[dict[str, Any]] = []
            reasoning = ""
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "thinking" and b.get("thinking"):
                    reasoning = b["thinking"]
                elif b.get("type") == "text" and b.get("text"):
                    text_parts.append({"type": "text", "text": b.get("text", "")})
                elif b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id") or '', "type": "function",
                        "function": {"name": b.get("name", ""), "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                    })
            m: dict[str, Any] = {"role": "assistant"}
            if reasoning:
                m["reasoning_content"] = reasoning
            if text_parts:
                m["content"] = text_parts
            else:
                m["content"] = ""
            if tool_calls:
                m["tool_calls"] = tool_calls
            if not text_parts and not tool_calls and reasoning:
                m["content"] = "."
            result.append(m)
        elif role == "user":
            text_parts = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result":
                    if text_parts:
                        result.append({"role": "user", "content": text_parts})
                        text_parts = []
                    tr = b.get("content", "")
                    if isinstance(tr, list):
                        tr = "\n".join(x.get("text", "") for x in tr if isinstance(x, dict) and x.get("type") == "text")
                    result.append({"role": "tool", "tool_call_id": b.get("tool_use_id") or '', "content": tr if isinstance(tr, str) else str(tr)})
                elif b.get("type") == "image":
                    src = b.get("source") or {}
                    if src.get("type") == "base64" and src.get("data"):
                        text_parts.append({"type": "image_url", "image_url": {"url": f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"}})
                elif b.get("type") == "image_url":
                    text_parts.append(b)
                elif b.get("type") == "text" and b.get("text"):
                    text_parts.append({"type": "text", "text": b.get("text", "")})
            if text_parts:
                result.append({"role": "user", "content": text_parts})
        else:
            result.append(msg)
    return result

# ---------------------------------------------------------------------------
# Message fixing (Claude API constraints)
# ---------------------------------------------------------------------------

def _fix_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fix messages to satisfy Claude API constraints: alternation and tool_use/tool_result pairing.

    - Merges consecutive same-role messages with a newline separator.
    - Inserts missing ``tool_result`` blocks for orphaned ``tool_use`` blocks.
    - Converts orphaned ``tool_result`` blocks (without a matching ``tool_use``) to plain text.
    - Removes leading non-user messages.
    """
    if not messages:
        return messages
    _wrap = lambda c: c if isinstance(c, list) else [{"type": "text", "text": str(c)}]
    fixed: list[dict[str, Any]] = []
    for m in messages:
        if fixed and m['role'] == fixed[-1]['role']:
            fixed[-1] = {**fixed[-1], 'content': _wrap(fixed[-1]['content']) + [{"type": "text", "text": "\n"}] + _wrap(m['content'])}
            continue
        if fixed and fixed[-1]['role'] == 'assistant' and m['role'] == 'user':
            uses = [b.get('id') for b in fixed[-1].get('content', []) if isinstance(b, dict) and b.get('type') == 'tool_use' and b.get('id')]
            has = {b.get('tool_use_id') for b in _wrap(m['content']) if isinstance(b, dict) and b.get('type') == 'tool_result'}
            miss = [uid for uid in uses if uid not in has]
            if miss:
                m = {**m, 'content': [{"type": "tool_result", "tool_use_id": uid, "content": "(error)"} for uid in miss] + _wrap(m['content'])}
            orphan = has - set(uses)
            if orphan:
                m = {**m, 'content': [{"type": "text", "text": str(b.get('content', ''))} if isinstance(b, dict) and b.get('type') == 'tool_result' and b.get('tool_use_id') in orphan else b for b in _wrap(m['content'])]}
        fixed.append(m)
    while fixed and fixed[0]['role'] != 'user':
        fixed.pop(0)
    return fixed

# ---------------------------------------------------------------------------
# Thinking-block helpers
# ---------------------------------------------------------------------------

def _keep_claude_block(b: Any) -> bool:
    """Return True if a content block should be kept (drop unsigned thinking)."""
    return not isinstance(b, dict) or b.get("type") != "thinking" or b.get("signature")

def _drop_unsigned_thinking(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove thinking blocks that lack a signature (incomplete/redacted)."""
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            m["content"] = [b for b in c if _keep_claude_block(b)]
    return messages

def _ensure_thinking_blocks(messages: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    """Ensure DeepSeek models have thinking blocks in assistant history.

    DeepSeek requires thinking blocks to be present in the conversation
    history; if missing, a placeholder is inserted.
    """
    if 'deepseek' not in model.lower():
        return messages
    for m in messages:
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if not isinstance(c, list):
            continue
        has_thinking = any(isinstance(b, dict) and b.get("type") == "thinking" for b in c)
        if not has_thinking:
            m["content"] = [{"type": "thinking", "thinking": "...", "signature": "placeholder"}, *c]
    return messages

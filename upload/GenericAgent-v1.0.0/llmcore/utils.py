"""Utility functions and constants for the llmcore package.

Provides the shared logger, safeprint, URL construction, thinking prompts,
LLM debug logging, exception fallbacks, and the response-cache key.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Project root (one directory up from this package)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Custom exceptions -- graceful fallback if exceptions.py is unavailable
# ---------------------------------------------------------------------------
try:
    from exceptions import (                         # type: ignore[import-untyped]
        LLMConnectionError,
        LLMError,
        LLMRateLimitError,
        LLMResponseError,
        LLMStreamInterruptedError,
    )
except ImportError:
    LLMError = type("LLMError", (Exception,), {"__init__": lambda self, *a, **kw: Exception.__init__(self, *a)})  # type: ignore[misc,assignment]
    LLMConnectionError = LLMError  # type: ignore[misc,assignment]
    LLMRateLimitError = LLMError   # type: ignore[misc,assignment]
    LLMResponseError = LLMError    # type: ignore[misc,assignment]
    LLMStreamInterruptedError = LLMError  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("llmcore")

# ---------------------------------------------------------------------------
# Response cache key (shared across the package)
# ---------------------------------------------------------------------------
_RESP_CACHE_KEY = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Safe print utility
# ---------------------------------------------------------------------------
_oldprint = print

def safeprint(*argv: Any, **kwargs: Any) -> None:
    """Print wrapper that logs OSError instead of crashing.

    .. deprecated::
        This function is kept for backward compatibility only.  New code
        should use ``logger`` directly instead of ``safeprint``.
    """
    try:
        _oldprint(*argv, **kwargs)
    except OSError as e:
        try:
            logger.debug("print() OSError ignored: %s", e)
        except Exception:
            logger.debug("Failed to log OSError in safeprint", exc_info=True)

# NOTE : on ne remplace PLUS print globalement.
# C'etait une pratique dangereuse qui affectait tout le processus Python.
# Les modules qui utilisent encore print() fonctionneront normalement.
# Pour le logging interne, utiliser logger.info/debug/warning/error a la place.
# print = safeprint  # SUPPRIME

# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def auto_make_url(base: str, path: str) -> str:
    """Construct an API URL from a base and a path, handling /vN/ prefixes.

    Special cases:
    - If *base* ends with ``$``, the ``$`` is stripped and *path* is ignored.
    - If *base* already ends with *path*, it is returned as-is.
    - If *base* contains ``/vN/`` or ``/vN``, the path is appended directly;
      otherwise ``/v1/`` is inserted before the path.
    """
    b, p = base.rstrip('/'), path.strip('/')
    if b.endswith('$'):
        return b[:-1].rstrip('/')
    if b.endswith(p):
        return b
    return f"{b}/{p}" if re.search(r'/v\d+(/|$)', b) else f"{b}/v1/{p}"

# ---------------------------------------------------------------------------
# Usage tracking (internal)
# ---------------------------------------------------------------------------

def _record_usage(usage: dict[str, Any] | None, api_mode: str) -> None:
    """Log token-usage statistics at DEBUG level."""
    if not usage:
        return
    if api_mode == 'responses':
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        inp = usage.get("input_tokens", 0)
        logger.debug("[Cache] input=%d cached=%d", inp, cached)
    elif api_mode == 'chat_completions':
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        inp = usage.get("prompt_tokens", 0)
        logger.debug("[Cache] input=%d cached=%d", inp, cached)
    elif api_mode == 'messages':
        ci = usage.get("cache_creation_input_tokens", 0)
        cr = usage.get("cache_read_input_tokens", 0)
        inp = usage.get("input_tokens", 0)
        logger.debug("[Cache] input=%d creation=%d read=%d", inp, ci, cr)

# ---------------------------------------------------------------------------
# LLM logging (debug file)
# ---------------------------------------------------------------------------

def _write_llm_log(label: str, content: str) -> None:
    """Append a labelled entry to the per-pid model responses log file.

    Sensitive data (API keys) is redacted before writing (Task 8.2.4).
    """
    # Redact API keys before writing to disk
    try:
        from logging_config import redact_sensitive
        content = redact_sensitive(content)
    except ImportError:
        pass  # fallback: write as-is if logging_config unavailable
    log_dir = os.path.join(_PROJECT_ROOT, 'temp', 'model_responses')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f'model_responses_{os.getpid()}.txt')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_path, 'a', encoding='utf-8', errors='replace') as f:
        f.write(f"=== {label} === {ts}\n{content}\n\n")

# ---------------------------------------------------------------------------
# Thinking prompts
# ---------------------------------------------------------------------------

THINKING_PROMPT_FR = """
### Protocole d'action (toujours en vigueur)
Chaque réponse (y compris les tours d'appel d'outil) doit d'abord inclure un instantané minimaliste en une ligne (<30 mots) dans <summary></summary> : nouvelles infos du dernier résultat + intention actuelle. Ce contenu entre dans la mémoire de travail à long terme.
\n**Si la demande de l'utilisateur n'est pas encore satisfaite, un appel d'outil est obligatoire !**
""".strip()

THINKING_PROMPT_EN = """
### Action Protocol (always in effect)
The reply body should first include a minimal one-line (<30 words) physical snapshot in <summary></summary>: new info from last result + current intent. This goes into long-term working memory.
\n**If the user's request is not yet complete, tool calls are required!**
""".strip()

THINKING_PROMPT_ZH = """
### 行动规范（持续有效）
每次回复（含工具调用轮）都先在回复文字中包含一个<summary></summary> 中输出极简单行（<30字）物理快照：上次结果新信息+本次意图。此内容进入长期工作记忆。
\n**若用户需求未完成，必须进行工具调用！**
""".strip()

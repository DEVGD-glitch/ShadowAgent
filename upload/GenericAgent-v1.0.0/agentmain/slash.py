"""
Slash command handling for GenericAgent.

This module defines the ``/session.*`` and ``/resume`` slash commands that
are processed *before* user input reaches the LLM.  The core
:class:`~agentmain.core.GenericAgent` class delegates to
:func:`handle_slash_cmd` from its own ``_handle_slash_cmd`` method so that
the public API of the agent remains unchanged.
"""

from __future__ import annotations

import json
import os
import queue
import re
from typing import Any, Callable, Optional

from ga import smart_format

from agentmain.prompts import script_dir

# ---------------------------------------------------------------------------
# Allowlist of writable attributes for /session.* commands
# ---------------------------------------------------------------------------

SESSION_WRITABLE_ATTRS: frozenset[str] = frozenset({
    "model", "temperature", "max_tokens", "top_p",
    "frequency_penalty", "presence_penalty", "stream",
})

# Type / range validation rules for each allowed attribute.
# Each entry maps to a callable ``(value) -> str | None`` that returns an
# error message if validation fails, or ``None`` on success.

def _validate_model(v: Any) -> str | None:
    if not isinstance(v, str):
        return f"'model' must be a string, got {type(v).__name__}"
    if not v.strip():
        return "'model' must be a non-empty string"
    return None


def _validate_temperature(v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return f"'temperature' must be a number, got {type(v).__name__}"
    if not (0.0 <= float(v) <= 2.0):
        return "'temperature' must be between 0 and 2"
    return None


def _validate_max_tokens(v: Any) -> str | None:
    if not isinstance(v, int) or isinstance(v, bool):
        return f"'max_tokens' must be an integer, got {type(v).__name__}"
    if v <= 0:
        return "'max_tokens' must be a positive integer"
    return None


def _validate_top_p(v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return f"'top_p' must be a number, got {type(v).__name__}"
    if not (0.0 <= float(v) <= 1.0):
        return "'top_p' must be between 0 and 1"
    return None


def _validate_frequency_penalty(v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return f"'frequency_penalty' must be a number, got {type(v).__name__}"
    if not (-2.0 <= float(v) <= 2.0):
        return "'frequency_penalty' must be between -2 and 2"
    return None


def _validate_presence_penalty(v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return f"'presence_penalty' must be a number, got {type(v).__name__}"
    if not (-2.0 <= float(v) <= 2.0):
        return "'presence_penalty' must be between -2 and 2"
    return None


def _validate_stream(v: Any) -> str | None:
    if not isinstance(v, bool):
        return f"'stream' must be a boolean, got {type(v).__name__}"
    return None


_SESSION_VALIDATORS: dict[str, Callable[[Any], str | None]] = {
    "model": _validate_model,
    "temperature": _validate_temperature,
    "max_tokens": _validate_max_tokens,
    "top_p": _validate_top_p,
    "frequency_penalty": _validate_frequency_penalty,
    "presence_penalty": _validate_presence_penalty,
    "stream": _validate_stream,
}

# ---------------------------------------------------------------------------
# /resume prompt — extracted from the inline string in the original monolith
# ---------------------------------------------------------------------------

_RESUME_PROMPT_FR: str = (
    r'Parcours temp/model_responses/ pour trouver les 10 fichiers les plus récents (hors ce PID), '
    r'lit le contenu de chaque fichier en remplaçant "\\n"→"\n" et "\\r"→"\r", '
    r'puis utilise re.findall(r"<history>\n\[(?:USER|Agent)\].*?</history>", content, re.DOTALL) '
    r'pour extraire les sessions, prend la dernière correspondance par fichier, trie par mtime décroissant, '
    r'résume chaque session en une phrase pour me laisser choisir ; puis lis la fin du fichier sélectionné comme base de conversation.'
)

_RESUME_PROMPT_ZH: str = (
    r'扫temp/model_responses/下时间最近的10个文件(除本PID)，'
    r'读取每个文件content后先replace("\\n","\n").replace("\\r","\r")统一为真换行，'
    r'再用re.findall(r"<history>\n\[(?:USER|Agent)\].*?</history>", content, re.DOTALL)'
    r'提取，取每文件最后一个匹配作为该会话内容，按mtime倒序，'
    r'每个用一句话总结聊了什么让我选择；选定后再简单读该文件末尾作为聊天基础'
)

_RESUME_PROMPT_EN: str = (
    r'Scan temp/model_responses/ for the 10 most recent files (excluding this PID), '
    r'read each file content after replacing "\\n"→"\n" and "\\r"→"\r", '
    r'then use re.findall(r"<history>\n\[(?:USER|Agent)\].*?</history>", content, re.DOTALL) '
    r'to extract sessions, take the last match per file, sort by mtime descending, '
    r'summarize each session in one sentence for me to choose; then read the end of the selected file as conversation base.'
)

def _get_resume_prompt() -> str:
    """Return the resume prompt in the appropriate language."""
    lang = os.environ.get('GA_LANG', '')
    if lang == 'en':
        return _RESUME_PROMPT_EN
    if lang == 'zh':
        return _RESUME_PROMPT_ZH
    return _RESUME_PROMPT_FR


def handle_slash_cmd(
    agent: Any, raw_query: str, display_queue: queue.Queue
) -> Optional[str]:
    """Process slash commands before they reach the LLM.

    Supported commands:

    * ``/session.<attr>=<value>`` — set a backend attribute on the
      current LLM session.  If *value* is a file path the file contents
      are read; JSON values are parsed automatically.
    * ``/resume`` — inject the session-resume prompt.

    Parameters
    ----------
    agent : GenericAgent
        The agent instance (used to access ``llmclient.backend``).
    raw_query : str
        The raw user input.
    display_queue : queue.Queue
        Queue for sending feedback to the caller.

    Returns
    -------
    str | None
        The rewritten query to send to the LLM, or ``None`` if the
        command was handled entirely within this method (e.g. a session
        attribute was set).
    """
    if not raw_query.startswith("/"):
        return raw_query

    # /session.<attr>=<value>  (allowlist-protected)
    if _sm := re.match(r"/session\.(\w+)=(.*)", raw_query.strip()):
        k, v = _sm.group(1), _sm.group(2)

        # --- Allowlist check ---------------------------------------------------
        if k not in SESSION_WRITABLE_ATTRS:
            display_queue.put({
                "done": (
                    f"\u26d4 Attribut '{k}' non modifiable. "
                    f"Attributs autoris\u00e9s : {', '.join(sorted(SESSION_WRITABLE_ATTRS))}"
                ),
                "source": "system",
            })
            return None

        # --- Resolve value (file / JSON / raw string) --------------------------
        vfile = os.path.join(script_dir, "temp", v)
        if os.path.isfile(vfile):
            with open(vfile, encoding="utf-8") as fh:
                v = fh.read().strip()
        try:
            v = json.loads(v)  # cover number parsing
        except (json.JSONDecodeError, ValueError):
            pass

        # --- Type / range validation -------------------------------------------
        validator = _SESSION_VALIDATORS.get(k)
        if validator is not None:
            err = validator(v)
            if err is not None:
                display_queue.put({
                    "done": f"\u26d4 {err}",
                    "source": "system",
                })
                return None

        setattr(agent.llmclient.backend, k, v)
        display_queue.put(
            {
                "done": smart_format(f"\u2705 session.{k} = {repr(v)}", max_str_len=500),
                "source": "system",
            }
        )
        return None

    # /resume
    if raw_query.strip() == "/resume":
        return _get_resume_prompt()

    return raw_query

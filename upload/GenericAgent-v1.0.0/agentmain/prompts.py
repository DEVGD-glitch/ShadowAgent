"""
System prompt management and tool schema loading for GenericAgent.

This module is responsible for:

* Computing the :data:`script_dir` constant (project root).
* Loading and refreshing :data:`TOOLS_SCHEMA` from the assets directory.
* Initialising the memory directory and global memory files.
* Building the full system prompt via :func:`get_system_prompt`.

All of the above runs at import time so that other submodules can rely on
the state being ready.
"""

from __future__ import annotations

import json
import locale
import os
import time
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("agentmain")

# ---------------------------------------------------------------------------
# Project-level path setup
# ---------------------------------------------------------------------------

# Ensure the project root is on sys.path so that sibling packages (llmcore,
# ga, agent_loop, etc.) can be imported regardless of how the agent was
# launched.
import sys as _sys  # noqa: E402

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in _sys.path:
    _sys.path.append(_project_root)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# ``script_dir`` points to the project root — the same directory where the
# old monolithic ``agentmain.py`` lived.  Submodules and external code
# reference this to find ``assets/``, ``temp/``, and ``memory/``.
script_dir: str = _project_root

# Language detection — mirrors the original os.environ default logic
os.environ.setdefault(
    "GA_LANG",
    "zh" if any(k in (locale.getlocale()[0] or "").lower() for k in ("zh", "chinese")) else "en",
)

lang_suffix: str = "_en" if os.environ.get("GA_LANG", "") == "en" else ""

# ---------------------------------------------------------------------------
# Tool schema loading
# ---------------------------------------------------------------------------

TOOLS_SCHEMA: Dict[str, Any] = {}


def load_tool_schema(suffix: str = "") -> None:
    """Load the tool JSON schema from the assets directory.

    On non-Windows systems the string ``"powershell"`` is replaced with
    ``"bash"`` so that the agent uses the correct shell tool definition.

    The global :data:`TOOLS_SCHEMA` dict is updated **in-place** so that
    all existing references (including those in other submodules) see the
    new data without needing to re-import.

    Parameters
    ----------
    suffix : str
        A suffix appended to the filename (e.g. ``"_cn"``) to load a
        locale-specific variant.
    """
    global TOOLS_SCHEMA
    schema_path = os.path.join(script_dir, f"assets/tools_schema{suffix}.json")
    with open(schema_path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    new_schema = json.loads(raw)
    if os.name != "nt":
        # Only replace "powershell" in the "name" field of tool definitions
        for tool in new_schema:
            if "function" in tool and tool["function"].get("name") == "powershell":
                tool["function"]["name"] = "bash"
    TOOLS_SCHEMA.clear()
    TOOLS_SCHEMA.update(new_schema)


load_tool_schema()

# ---------------------------------------------------------------------------
# Memory initialisation
# ---------------------------------------------------------------------------

mem_dir: str = os.path.join(script_dir, "memory")
os.makedirs(mem_dir, exist_ok=True)

mem_txt: str = os.path.join(mem_dir, "global_mem.txt")
if not os.path.exists(mem_txt):
    with open(mem_txt, "w", encoding="utf-8") as fh:
        fh.write("# [Global Memory - L2]\n")

mem_insight: str = os.path.join(mem_dir, "global_mem_insight.txt")
if not os.path.exists(mem_insight):
    template_path = os.path.join(
        script_dir, f"assets/global_mem_insight_template{lang_suffix}.txt"
    )
    content = ""
    if os.path.exists(template_path):
        with open(template_path, encoding="utf-8") as fh:
            content = fh.read()
    with open(mem_insight, "w", encoding="utf-8") as fh:
        fh.write(content)

# CDP bridge config
cdp_cfg: str = os.path.join(script_dir, "assets/tmwd_cdp_bridge/config.js")
if not os.path.exists(cdp_cfg):
    try:
        os.makedirs(os.path.dirname(cdp_cfg), exist_ok=True)
        with open(cdp_cfg, "w", encoding="utf-8") as fh:
            import random as _random

            fh.write(
                f"const TID = '__ljq_{hex(_random.randint(0, 99999999))[2:8]}';"
            )
    except OSError as exc:
        logger.warning(
            "CDP config init failed: %s — advanced web features (tmwebdriver) will be unavailable.",
            exc,
        )


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def get_system_prompt() -> str:
    """Build the full system prompt by combining the template with the
    current date and global memory context.

    Returns
    -------
    str
        The assembled system prompt string.
    """
    from ga import get_global_memory

    prompt_path = os.path.join(script_dir, f"assets/sys_prompt{lang_suffix}.txt")
    with open(prompt_path, "r", encoding="utf-8") as fh:
        prompt = fh.read()
    prompt += f"\nToday: {time.strftime('%Y-%m-%d %a')}\n"
    prompt += get_global_memory()
    return prompt


def get_merged_tool_schemas() -> list[dict]:
    """Merge builtin tool schemas with plugin schemas from the tool registry.

    Returns
    -------
    list[dict]
        Combined OpenAI-compatible tool schema list.
    """
    builtin = TOOLS_SCHEMA if isinstance(TOOLS_SCHEMA, list) else []
    try:
        from tools.registry import get_registry
        registry = get_registry()
        return registry.merge_builtin_schemas(builtin)
    except ImportError:
        return builtin

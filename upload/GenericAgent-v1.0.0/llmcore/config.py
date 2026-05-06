"""Configuration loading for the llmcore package.

Handles API key loading from mykey.py / mykey.json with file-change
detection and lazy reloading via PEP 562.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any

from .utils import _PROJECT_ROOT, LLMError, logger

# ---------------------------------------------------------------------------
# Module-level state for key loading
# ---------------------------------------------------------------------------
_mykey_path: str | None = None
_mykey_mtime: int | None = None

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def _load_mykeys() -> dict[str, Any]:
    """Load API keys from mykey.py or mykey.json."""
    global _mykey_path
    try:
        import mykey; importlib.reload(mykey); _mykey_path = mykey.__file__  # type: ignore[import-untyped]
        return {k: v for k, v in vars(mykey).items() if not k.startswith('_')}
    except ImportError:
        pass
    _mykey_path = p = os.path.join(_PROJECT_ROOT, 'mykey.json')
    if not os.path.exists(p):
        raise LLMError('[ERROR] mykey.py or mykey.json not found, please create one from mykey_template.')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def reload_mykeys() -> tuple[dict[str, Any], bool]:
    """Reload API keys if the source file has changed.

    Returns
    -------
    tuple[dict, bool]
        The keys dict and whether they were freshly loaded.
    """
    global _mykey_mtime
    mt = os.stat(_mykey_path).st_mtime_ns if _mykey_path else -1
    if mt == _mykey_mtime:
        return globals().get('mykeys', {}), False
    mk = _load_mykeys()
    _mykey_mtime = os.stat(_mykey_path).st_mtime_ns
    logger.info("Load mykeys from %s", _mykey_path)
    globals().update(mykeys=mk)
    if mk.get('langfuse_config'):
        try:
            from plugins import langfuse_tracing  # type: ignore[import-untyped]
        except Exception:
            logger.debug("langfuse_tracing plugin not available")
    return mk, True

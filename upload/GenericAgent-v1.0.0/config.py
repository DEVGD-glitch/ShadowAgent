"""config.py — Centralized configuration management for GenericAgent.

Replaces scattered ``os.environ.get()`` calls and direct ``mykey`` imports
with typed, validated dataclasses.  Every subsystem (LLM, Agent, UI) gets
its own configuration container, and the :func:`load_llm_configs` function
preserves the existing ``mykey.py`` / ``mykey.json`` loading logic from
:mod:`llmcore`.

Typical usage::

    from config import load_llm_configs, get_agent_config, get_ui_config

    llm_cfgs = load_llm_configs()          # dict[str, LLMConfig]
    agent_cfg = get_agent_config()          # AgentConfig
    ui_cfg = get_ui_config()                # UIConfig
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("config")

# ══════════════════════════════════════════════════════════════════════════════
#  LLMConfig
# ══════════════════════════════════════════════════════════════════════════════

_VALID_REASONING_EFFORT = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"}
)
_VALID_SERVICE_TIER = frozenset({"auto", "default", "priority", "flex"})
_VALID_THINKING_TYPE = frozenset({"adaptive", "enabled", "disabled"})
_VALID_API_MODES = frozenset({"chat_completions", "responses"})


@dataclass
class LLMConfig:
    """Configuration for a single LLM session.

    Mirrors the dict-based config consumed by :class:`llmcore.BaseSession`.
    All fields are validated in :meth:`__post_init__`.

    Attributes:
        api_key: API key for authentication.
        api_base: Base URL of the API endpoint (trailing slashes stripped).
        model: Model identifier (e.g. ``"claude-sonnet-4-6"``).
        name: Display name used in UI and mixin references.
        context_win: Character-level history trimming threshold.
        stream: Whether to use SSE streaming.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens (``None`` = use provider default).
        max_retries: Number of automatic retries on transient errors.
        proxy: HTTP proxy URL, or ``None`` for direct connection.
        verify: Whether to verify SSL certificates.
        timeout: Connection timeout in seconds.
        read_timeout: Read timeout in seconds.
        api_mode: API protocol — ``"chat_completions"`` or ``"responses"``.
        reasoning_effort: Reasoning effort level (OpenAI / Claude).
        service_tier: Service tier for the API request.
        thinking_type: Claude native thinking block type.
        thinking_budget_tokens: Token budget when ``thinking_type="enabled"``.
    """

    api_key: str
    api_base: str
    model: str = ""
    name: str = ""
    context_win: int = 28000
    stream: bool = True
    temperature: float = 1.0
    max_tokens: Optional[int] = None
    max_retries: int = 4
    proxy: Optional[str] = None
    verify: bool = True
    timeout: int = 5
    read_timeout: int = 30
    api_mode: str = "chat_completions"
    reasoning_effort: Optional[str] = None
    service_tier: Optional[str] = None
    thinking_type: Optional[str] = None
    thinking_budget_tokens: Optional[int] = None

    # ── Validation ─────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Validate and normalise fields after initialisation."""
        # Strip whitespace from critical string fields
        self.api_key = self.api_key.strip()
        self.api_base = self.api_base.rstrip("/")
        self.model = self.model.strip()
        self.name = self.name.strip() or self.model

        if not self.api_key:
            raise ValueError("LLMConfig.api_key must not be empty")
        if not self.api_base:
            raise ValueError("LLMConfig.api_base must not be empty")

        # Numeric bounds
        if self.context_win < 1:
            raise ValueError(f"LLMConfig.context_win must be >= 1, got {self.context_win}")
        self.max_retries = max(0, self.max_retries)
        self.timeout = max(1, self.timeout)
        self.read_timeout = max(1, self.read_timeout)

        # Enum-like fields — invalid values are warned and set to None
        self.reasoning_effort = self._validate_enum(
            "reasoning_effort", self.reasoning_effort, _VALID_REASONING_EFFORT
        )
        self.service_tier = self._validate_enum(
            "service_tier", self.service_tier, _VALID_SERVICE_TIER
        )
        self.thinking_type = self._validate_enum(
            "thinking_type", self.thinking_type, _VALID_THINKING_TYPE
        )

        # api_mode normalisation
        mode = self.api_mode.strip().lower().replace("-", "_")
        if mode in ("responses", "response"):
            self.api_mode = "responses"
        elif mode != "chat_completions":
            logger.warning(
                "LLMConfig.api_mode %r is not recognised; "
                "falling back to 'chat_completions'",
                self.api_mode,
            )
            self.api_mode = "chat_completions"

        # thinking_type='enabled' requires thinking_budget_tokens
        if self.thinking_type == "enabled" and self.thinking_budget_tokens is None:
            logger.warning(
                "LLMConfig.thinking_type='enabled' requires "
                "thinking_budget_tokens; setting thinking_type to None"
            )
            self.thinking_type = None

    @staticmethod
    def _validate_enum(
        field_name: str,
        value: Optional[str],
        valid: frozenset[str],
    ) -> Optional[str]:
        """Return *value* lower-cased if valid, else ``None`` with a warning."""
        if value is None:
            return None
        value = str(value).strip().lower()
        if value in valid:
            return value
        logger.warning(
            "LLMConfig.%s=%r is not in %s; ignoring", field_name, value, sorted(valid)
        )
        return None

    # ── Conversion helpers ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to the dict format expected by :class:`llmcore.BaseSession`.

        Keys use the legacy naming convention (``apikey``, ``apibase``, etc.)
        so that the resulting dict can be passed directly to BaseSession
        constructors without modification.
        """
        d: dict = {
            "apikey": self.api_key,
            "apibase": self.api_base,
            "model": self.model,
            "name": self.name,
            "context_win": self.context_win,
            "stream": self.stream,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "verify": self.verify,
            "timeout": self.timeout,
            "read_timeout": self.read_timeout,
            "api_mode": self.api_mode,
        }
        if self.max_tokens is not None:
            d["max_tokens"] = self.max_tokens
        if self.proxy is not None:
            d["proxy"] = self.proxy
        if self.reasoning_effort is not None:
            d["reasoning_effort"] = self.reasoning_effort
        if self.service_tier is not None:
            d["service_tier"] = self.service_tier
        if self.thinking_type is not None:
            d["thinking_type"] = self.thinking_type
        if self.thinking_budget_tokens is not None:
            d["thinking_budget_tokens"] = self.thinking_budget_tokens
        return d

    @classmethod
    def from_dict(cls, cfg: dict) -> LLMConfig:
        """Create an :class:`LLMConfig` from a legacy mykey-style dict.

        The dict keys use the legacy naming (``apikey``, ``apibase``).
        """
        return cls(
            api_key=cfg.get("apikey", ""),
            api_base=cfg.get("apibase", ""),
            model=cfg.get("model", ""),
            name=cfg.get("name", ""),
            context_win=cfg.get("context_win", 28000),
            stream=cfg.get("stream", True),
            temperature=cfg.get("temperature", 1.0),
            max_tokens=cfg.get("max_tokens"),
            max_retries=cfg.get("max_retries", 4),
            proxy=cfg.get("proxy"),
            verify=cfg.get("verify", True),
            timeout=cfg.get("timeout", 5),
            read_timeout=cfg.get("read_timeout", 30),
            api_mode=cfg.get("api_mode", "chat_completions"),
            reasoning_effort=cfg.get("reasoning_effort"),
            service_tier=cfg.get("service_tier"),
            thinking_type=cfg.get("thinking_type"),
            thinking_budget_tokens=cfg.get("thinking_budget_tokens"),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  AgentConfig
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_DANGEROUS_PATTERNS: list[str] = [
    r"\brm\s+",
    r"\bdel\s+",
    r"\brmdir\s+",
    r"\bformat\s+",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\breg\s+",
    r"\bregedit\b",
    r"\bnet\s+user\b",
    r"\bnetsh\b",
    r"\btaskkill\b",
    r"\bchmod\s+777",
    r"\bsudo\s+rm\b",
]


@dataclass
class AgentConfig:
    """Configuration for the agent runtime.

    Attributes:
        workspace_dir: Isolated working directory for code execution.
        max_turns: Maximum number of agent loop iterations per task.
        default_timeout: Default execution timeout in seconds for code_run.
        dangerous_shell_patterns: Regex patterns that trigger user
            confirmation before shell execution.
        verbose: Whether to emit verbose debug output.
        language: Interface language code (``"fr"``, ``"en"``, ``"zh"``).
    """

    workspace_dir: str = ""
    max_turns: int = 70
    default_timeout: int = 60
    dangerous_shell_patterns: list[str] = field(
        default_factory=lambda: list(_DEFAULT_DANGEROUS_PATTERNS)
    )
    verbose: bool = False
    language: str = "fr"

    def __post_init__(self) -> None:
        if not self.workspace_dir:
            self.workspace_dir = os.environ.get(
                "GA_WORKSPACE",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace"),
            )
        # Ensure workspace directory exists
        os.makedirs(self.workspace_dir, exist_ok=True)

        if self.max_turns < 1:
            raise ValueError(f"AgentConfig.max_turns must be >= 1, got {self.max_turns}")
        if self.default_timeout < 1:
            raise ValueError(
                f"AgentConfig.default_timeout must be >= 1, got {self.default_timeout}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  UIConfig
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class UIConfig:
    """Configuration for the Qt / desktop UI frontend.

    Attributes:
        window_width: Default window width in pixels.
        window_height: Default window height in pixels.
        poll_interval_ms: Timer interval (ms) for polling the LLM output
            queue.
        autonomous_idle_timeout: Seconds of inactivity before autonomous
            mode is considered idle (default 1800 = 30 min).
        max_inline_chars: Maximum characters to render inline before
            truncating with a collapsible region.
    """

    window_width: int = 530
    window_height: int = 700
    poll_interval_ms: int = 40
    autonomous_idle_timeout: int = 1800
    max_inline_chars: int = 6000

    def __post_init__(self) -> None:
        if self.window_width < 100:
            raise ValueError(
                f"UIConfig.window_width must be >= 100, got {self.window_width}"
            )
        if self.window_height < 100:
            raise ValueError(
                f"UIConfig.window_height must be >= 100, got {self.window_height}"
            )
        if self.poll_interval_ms < 1:
            raise ValueError(
                f"UIConfig.poll_interval_ms must be >= 1, got {self.poll_interval_ms}"
            )
        if self.autonomous_idle_timeout < 1:
            raise ValueError(
                f"UIConfig.autonomous_idle_timeout must be >= 1, "
                f"got {self.autonomous_idle_timeout}"
            )
        if self.max_inline_chars < 1:
            raise ValueError(
                f"UIConfig.max_inline_chars must be >= 1, got {self.max_inline_chars}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  Loader functions
# ══════════════════════════════════════════════════════════════════════════════

# Cache for the mykey path discovered during loading
_mykey_path: Optional[str] = None


def _load_mykeys_raw() -> dict:
    """Load raw key-value pairs from ``mykey.py`` or ``mykey.json``.

    # Note: _load_mykeys_raw is also defined in config_schema.py
    # Both exist for backward compatibility. Prefer config_schema.py version.

    Reuses the same logic as :func:`llmcore._load_mykeys`:
    1. Try ``import mykey`` — if it succeeds, return all public
       attributes as a dict.
    2. Fall back to ``mykey.json`` in the project root.
    3. Raise an error if neither is found.
    """
    global _mykey_path
    try:
        import mykey

        importlib.reload(mykey)
        _mykey_path = mykey.__file__
        return {k: v for k, v in vars(mykey).items() if not k.startswith("_")}
    except ImportError:
        pass

    _mykey_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "mykey.json"
    )
    if not os.path.exists(_mykey_path):
        raise FileNotFoundError(
            "[ERROR] mykey.py or mykey.json not found. "
            "Please create one from mykey_template."
        )
    with open(_mykey_path, encoding="utf-8") as f:
        return json.load(f)


def load_llm_configs() -> dict[str, LLMConfig]:
    """Load all LLM configurations from ``mykey.py`` / ``mykey.json``.

    Only entries whose variable name contains at least one of the keywords
    ``"api"``, ``"config"``, or ``"cookie"`` are considered LLM configs
    (matching the filtering logic in :mod:`agentmain`).

    Returns:
        A dict mapping the variable name to an :class:`LLMConfig` instance.
        Entries that fail validation are skipped with a warning.
    """
    raw = _load_mykeys_raw()
    _KEYWORDS = {"api", "config", "cookie"}
    result: dict[str, LLMConfig] = {}

    for key, value in raw.items():
        if not any(kw in key for kw in _KEYWORDS):
            continue
        # mixin_config is not an LLM session config; skip it
        if key == "mixin_config":
            continue
        if not isinstance(value, dict):
            continue
        try:
            result[key] = LLMConfig.from_dict(value)
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping LLM config %r: %s", key, exc)

    return result


def _safe_int(val: str, default: int) -> int:
    """Safely convert a string to int with a fallback default."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_agent_config() -> AgentConfig:
    """Build an :class:`AgentConfig` from environment variables.

    Environment variables:
        ``GA_WORKSPACE``    — workspace directory (default: ``./workspace``)
        ``GA_MAX_TURNS``    — max agent loop turns (default: 70)
        ``GA_TIMEOUT``      — default code execution timeout (default: 60)
        ``GA_VERBOSE``      — verbose mode, ``"1"`` / ``"true"`` to enable
        ``GA_LANG``         — interface language (default: ``"fr"``)
    """
    return AgentConfig(
        workspace_dir=os.environ.get("GA_WORKSPACE", ""),
        max_turns=_safe_int(os.environ.get("GA_MAX_TURNS", "70"), 70),
        default_timeout=_safe_int(os.environ.get("GA_TIMEOUT", "60"), 60),
        verbose=os.environ.get("GA_VERBOSE", "").strip().lower()
        in ("1", "true", "yes"),
        language=os.environ.get("GA_LANG", "fr").strip().lower(),
    )


def get_ui_config() -> UIConfig:
    """Build a :class:`UIConfig` from environment variables.

    Environment variables:
        ``GA_UI_WIDTH``             — window width in px (default: 530)
        ``GA_UI_HEIGHT``            — window height in px (default: 700)
        ``GA_UI_POLL_MS``           — poll interval in ms (default: 40)
        ``GA_UI_IDLE_TIMEOUT``      — autonomous idle timeout in s (default: 1800)
        ``GA_UI_MAX_INLINE_CHARS``  — max inline chars (default: 6000)
    """
    return UIConfig(
        window_width=_safe_int(os.environ.get("GA_UI_WIDTH", "530"), 530),
        window_height=_safe_int(os.environ.get("GA_UI_HEIGHT", "700"), 700),
        poll_interval_ms=_safe_int(os.environ.get("GA_UI_POLL_MS", "40"), 40),
        autonomous_idle_timeout=_safe_int(
            os.environ.get("GA_UI_IDLE_TIMEOUT", "1800"), 1800
        ),
        max_inline_chars=_safe_int(os.environ.get("GA_UI_MAX_INLINE_CHARS", "6000"), 6000),
    )


__all__ = [
    "LLMConfig",
    "AgentConfig",
    "UIConfig",
    "load_llm_configs",
    "get_agent_config",
    "get_ui_config",
]

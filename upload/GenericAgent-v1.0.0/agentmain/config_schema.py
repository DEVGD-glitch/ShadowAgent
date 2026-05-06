"""Validated configuration schema for GenericAgent.

This module provides Pydantic-validated (or dataclass-validated) configuration
classes and a multi-layer configuration loader.  Configuration is resolved
from the following sources in priority order (highest wins):

1. **OS keyring** — API keys retrieved via the ``keyring`` library.
2. **mykey.py / mykey.json** — Full configuration from the project root.
3. **.env file** — Environment variable overrides.
4. **Environment variables** — ``GA_*`` prefixed variables.
5. **Built-in defaults** — Sensible fallback values.

Classes:
    LLMProviderConfig: Per-provider configuration (API key, base URL, model).
    AgentConfigSchema: Top-level agent configuration (language, providers).

Functions:
    load_config: Load and validate the full agent configuration.
    _load_mykeys_raw: Load raw key-value pairs from mykey.py/json.
    _try_keyring: Attempt to retrieve an API key from the OS keyring.
    _load_dotenv: Load variables from a .env file.

Example::

    from agentmain.config_schema import load_config

    config = load_config()
    for provider in config.providers:
        print(f"Provider: {provider.name}, model: {provider.model}")
"""
from __future__ import annotations

import importlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ga.agentmain.config_schema")

try:
    from pydantic import BaseModel, Field, field_validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic-based schema (preferred)
# ══════════════════════════════════════════════════════════════════════════════

if HAS_PYDANTIC:

    class LLMProviderConfig(BaseModel):
        """Configuration for a single LLM provider.

        Attributes:
            name: Display name for this provider (e.g. "claude-sonnet").
            api_key: API key for authentication (sensitive — never log).
            api_base: Base URL of the API endpoint.
            model: Model identifier (e.g. "claude-sonnet-4-6").
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum output tokens (> 0).
        """

        name: str = ""
        api_key: str = Field(default="", repr=False)
        api_base: str = ""
        model: str = ""
        temperature: float = 1.0
        max_tokens: Optional[int] = None

        @field_validator("temperature")
        @classmethod
        def validate_temperature(cls, v: float) -> float:
            if not (0.0 <= v <= 2.0):
                raise ValueError(
                    f"temperature must be between 0.0 and 2.0, got {v}"
                )
            return v

        @field_validator("max_tokens")
        @classmethod
        def validate_max_tokens(cls, v: Optional[int]) -> Optional[int]:
            if v is not None and v <= 0:
                raise ValueError(
                    f"max_tokens must be > 0, got {v}"
                )
            return v

        @field_validator("api_base")
        @classmethod
        def normalize_api_base(cls, v: str) -> str:
            return v.rstrip("/")

        @field_validator("name")
        @classmethod
        def default_name(cls, v: str, info: Any) -> str:
            """Default name to model if not provided."""
            return v.strip() or ""

        model_config = {"extra": "allow"}

    class AgentConfigSchema(BaseModel):
        """Top-level agent configuration.

        Attributes:
            language: Interface language code (fr, en, zh).
            providers: List of LLM provider configurations.
            default_provider: Name of the default provider to use.
            workspace_dir: Isolated working directory for code execution.
        """

        language: str = "fr"
        providers: List[LLMProviderConfig] = Field(default_factory=list)
        default_provider: str = ""
        workspace_dir: str = ""

        @field_validator("language")
        @classmethod
        def validate_language(cls, v: str) -> str:
            v = v.strip().lower()
            if v not in ("fr", "en", "zh"):
                logger.warning(
                    "language %r is not in ('fr', 'en', 'zh'); using 'en'", v
                )
                return "en"
            return v

        model_config = {"extra": "allow"}


# ══════════════════════════════════════════════════════════════════════════════
#  Dataclass-based fallback (when pydantic is not installed)
# ══════════════════════════════════════════════════════════════════════════════

else:

    @dataclass
    class LLMProviderConfig:  # type: ignore[no-redef]
        """Configuration for a single LLM provider (dataclass fallback).

        Attributes:
            name: Display name for this provider.
            api_key: API key for authentication (sensitive — never log).
            api_base: Base URL of the API endpoint.
            model: Model identifier.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum output tokens (> 0).
        """

        name: str = ""
        api_key: str = ""
        api_base: str = ""
        model: str = ""
        temperature: float = 1.0
        max_tokens: Optional[int] = None

        def __post_init__(self) -> None:
            self.api_base = self.api_base.rstrip("/")
            self.name = self.name.strip()
            if not (0.0 <= self.temperature <= 2.0):
                raise ValueError(
                    f"temperature must be between 0.0 and 2.0, got {self.temperature}"
                )
            if self.max_tokens is not None and self.max_tokens <= 0:
                raise ValueError(
                    f"max_tokens must be > 0, got {self.max_tokens}"
                )

    @dataclass
    class AgentConfigSchema:  # type: ignore[no-redef]
        """Top-level agent configuration (dataclass fallback).

        Attributes:
            language: Interface language code (fr, en, zh).
            providers: List of LLM provider configurations.
            default_provider: Name of the default provider to use.
            workspace_dir: Isolated working directory for code execution.
        """

        language: str = "fr"
        providers: List[LLMProviderConfig] = field(default_factory=list)
        default_provider: str = ""
        workspace_dir: str = ""

        def __post_init__(self) -> None:
            self.language = self.language.strip().lower()
            if self.language not in ("fr", "en", "zh"):
                logger.warning(
                    "language %r is not in ('fr', 'en', 'zh'); using 'en'",
                    self.language,
                )
                self.language = "en"


# ══════════════════════════════════════════════════════════════════════════════
#  Configuration loader
# ══════════════════════════════════════════════════════════════════════════════

# Keywords that identify LLM session config entries in mykey.py
_LLM_CONFIG_KEYWORDS = frozenset({"api", "config", "cookie"})


def _load_mykeys_raw() -> dict:
    """Load raw key-value pairs from mykey.py or mykey.json.
    
    ⚠️  SECURITY WARNING: This executes arbitrary Python code from mykey.py.
    In production, prefer using the OS keyring via credential_store.py
    or environment variables instead of mykey.py.

    Search order:
      1. ``import mykey`` (Python file)
      2. ``mykey.json`` in the project root

    Returns:
        Dict of all public attributes from the mykey module / JSON.
    """
    try:
        import mykey  # type: ignore[import-untyped]

        importlib.reload(mykey)
        return {k: v for k, v in vars(mykey).items() if not k.startswith("_")}
    except ImportError:
        pass

    json_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "mykey.json"
    )
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            "mykey.py or mykey.json not found. "
            "Please create one from mykey_template."
        )
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def _try_keyring(provider_name: str) -> Optional[str]:
    """Attempt to retrieve an API key from the OS keyring.

    Returns:
        The API key string if found, ``None`` otherwise.
    """
    try:
        import keyring  # type: ignore[import-untyped]

        return keyring.get_password("GenericAgent", provider_name)
    except Exception:
        return None


def _load_dotenv() -> dict:
    """Load variables from a .env file if present.

    Returns:
        Dict of environment variable overrides from .env.
    """
    env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".env"
    )
    if not os.path.exists(env_path):
        return {}

    result: dict = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            result[key] = value
    return result


def load_config() -> AgentConfigSchema:
    """Load and validate the full agent configuration.

    Priority order (highest wins):
      1. OS keyring (API keys only)
      2. mykey.py / mykey.json (full config)
      3. .env file
      4. Environment variables (GA_* prefix)
      5. Built-in defaults

    Returns:
        A validated :class:`AgentConfigSchema` instance.

    Raises:
        FileNotFoundError: If no mykey.py or mykey.json can be found.
        ValueError: If validation fails and cannot be auto-corrected.
    """
    # --- Layer 2: mykey.py / mykey.json ---
    raw = _load_mykeys_raw()

    providers: List[LLMProviderConfig] = []
    for key, value in raw.items():
        if not any(kw in key for kw in _LLM_CONFIG_KEYWORDS):
            continue
        if key == "mixin_config":
            continue
        if not isinstance(value, dict):
            continue
        try:
            provider_cfg = _build_provider_config(key, value)
            providers.append(provider_cfg)
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping LLM config %r: %s", key, exc)

    # --- Layer 3: .env file ---
    dotenv_vars = _load_dotenv()

    # --- Layer 4: environment variables ---
    language = (
        dotenv_vars.get("GA_LANG")
        or os.environ.get("GA_LANG", "")
        or raw.get("lang", "")
        or "fr"
    )
    workspace_dir = (
        dotenv_vars.get("GA_WORKSPACE")
        or os.environ.get("GA_WORKSPACE", "")
        or ""
    )
    default_provider = raw.get("default_provider", "")

    # Determine default provider if not explicitly set
    if not default_provider and providers:
        default_provider = providers[0].name or ""

    config = AgentConfigSchema(
        language=language,
        providers=providers,
        default_provider=default_provider,
        workspace_dir=workspace_dir,
    )

    logger.info(
        "Loaded config: %d providers, language=%r, default_provider=%r",
        len(config.providers),
        config.language,
        config.default_provider,
    )
    return config


def _build_provider_config(key: str, raw_dict: dict) -> LLMProviderConfig:
    """Build an LLMProviderConfig from a mykey-style dict.

    Also attempts keyring lookup for the API key.

    Args:
        key: The variable name in mykey.py (e.g. "native_oai_config").
        raw_dict: The dict value associated with that variable.

    Returns:
        A validated LLMProviderConfig.
    """
    name = raw_dict.get("name", "")
    api_key = raw_dict.get("apikey", "") or raw_dict.get("api_key", "")

    # --- Layer 1: keyring override ---
    keyring_key = _try_keyring(name or key)
    if keyring_key:
        api_key = keyring_key

    # --- Layer 4: environment variable override ---
    env_key_name = f"GA_API_KEY_{key.upper()}"
    env_key = os.environ.get(env_key_name)
    if env_key:
        api_key = env_key

    return LLMProviderConfig(
        name=name,
        api_key=api_key,
        api_base=raw_dict.get("apibase", "") or raw_dict.get("api_base", ""),
        model=raw_dict.get("model", ""),
        temperature=float(raw_dict.get("temperature", 1.0)),
        max_tokens=raw_dict.get("max_tokens"),
    )


__all__ = [
    "HAS_PYDANTIC",
    "LLMProviderConfig",
    "AgentConfigSchema",
    "load_config",
]

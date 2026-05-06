"""Tests for the config module.

Covers LLMConfig creation, validation, conversion, AgentConfig, UIConfig,
and the loader functions load_llm_configs, get_agent_config, get_ui_config.
"""

from __future__ import annotations

import logging
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import (
    LLMConfig,
    AgentConfig,
    UIConfig,
    load_llm_configs,
    get_agent_config,
    get_ui_config,
    _load_mykeys_raw,
)


# ══════════════════════════════════════════════════════════════════════
# LLMConfig — creation & defaults
# ══════════════════════════════════════════════════════════════════════

class TestLLMConfigCreation:
    """Tests for LLMConfig creation and default values."""

    def test_minimal_creation(self):
        """LLMConfig can be created with just api_key and api_base."""
        cfg = LLMConfig(api_key="sk-test", api_base="https://api.example.com")
        assert cfg.api_key == "sk-test"
        assert cfg.api_base == "https://api.example.com"

    def test_defaults(self):
        """LLMConfig has sensible default values."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com")
        assert cfg.model == ""
        assert cfg.name == ""  # will be set to model by __post_init__
        assert cfg.context_win == 28000
        assert cfg.stream is True
        assert cfg.temperature == 1.0
        assert cfg.max_tokens is None
        assert cfg.max_retries == 4
        assert cfg.proxy is None
        assert cfg.verify is True
        assert cfg.timeout == 5
        assert cfg.read_timeout == 30
        assert cfg.api_mode == "chat_completions"
        assert cfg.reasoning_effort is None
        assert cfg.service_tier is None
        assert cfg.thinking_type is None
        assert cfg.thinking_budget_tokens is None

    def test_name_defaults_to_model(self):
        """When name is empty, it defaults to model."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com", model="gpt-4")
        assert cfg.name == "gpt-4"

    def test_name_kept_if_provided(self):
        """When name is provided, it is kept."""
        cfg = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            model="gpt-4", name="MyGPT4"
        )
        assert cfg.name == "MyGPT4"

    def test_api_key_whitespace_stripped(self):
        """Whitespace in api_key is stripped."""
        cfg = LLMConfig(api_key="  sk-test  ", api_base="https://api.example.com")
        assert cfg.api_key == "sk-test"

    def test_api_base_trailing_slash_stripped(self):
        """Trailing slash in api_base is stripped."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com/")
        assert cfg.api_base == "https://api.example.com"

    def test_api_base_multiple_trailing_slashes(self):
        """Multiple trailing slashes in api_base are stripped."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com///")
        assert not cfg.api_base.endswith("/")


# ══════════════════════════════════════════════════════════════════════
# LLMConfig — validation
# ══════════════════════════════════════════════════════════════════════

class TestLLMConfigValidation:
    """Tests for LLMConfig validation in __post_init__."""

    def test_empty_api_key_raises(self):
        """Empty api_key raises ValueError."""
        with pytest.raises(ValueError, match="api_key"):
            LLMConfig(api_key="", api_base="https://api.example.com")

    def test_whitespace_api_key_raises(self):
        """Whitespace-only api_key raises ValueError after stripping."""
        with pytest.raises(ValueError, match="api_key"):
            LLMConfig(api_key="   ", api_base="https://api.example.com")

    def test_empty_api_base_raises(self):
        """Empty api_base raises ValueError."""
        with pytest.raises(ValueError, match="api_base"):
            LLMConfig(api_key="sk-test", api_base="")

    def test_invalid_context_win(self):
        """context_win < 1 raises ValueError."""
        with pytest.raises(ValueError, match="context_win"):
            LLMConfig(api_key="k", api_base="https://api.example.com", context_win=0)

    def test_negative_context_win(self):
        """Negative context_win raises ValueError."""
        with pytest.raises(ValueError, match="context_win"):
            LLMConfig(api_key="k", api_base="https://api.example.com", context_win=-10)

    def test_negative_max_retries_clamped(self):
        """Negative max_retries is clamped to 0."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com", max_retries=-1)
        assert cfg.max_retries == 0

    def test_zero_timeout_clamped(self):
        """Timeout < 1 is clamped to 1."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com", timeout=0)
        assert cfg.timeout == 1

    def test_negative_timeout_clamped(self):
        """Negative timeout is clamped to 1."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com", timeout=-5)
        assert cfg.timeout == 1

    def test_zero_read_timeout_clamped(self):
        """Read timeout < 1 is clamped to 1."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com", read_timeout=0)
        assert cfg.read_timeout == 1

    def test_invalid_reasoning_effort_ignored(self):
        """Invalid reasoning_effort is set to None with a warning."""
        with patch('config.logger') as mock_logger:
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                reasoning_effort="super_high"
            )
            assert cfg.reasoning_effort is None
            mock_logger.warning.assert_called()

    def test_valid_reasoning_effort(self):
        """Valid reasoning_effort values are accepted."""
        for effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                reasoning_effort=effort
            )
            assert cfg.reasoning_effort == effort

    def test_invalid_service_tier_ignored(self):
        """Invalid service_tier is set to None."""
        with patch('config.logger'):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                service_tier="platinum"
            )
            assert cfg.service_tier is None

    def test_valid_service_tier(self):
        """Valid service_tier values are accepted."""
        for tier in ("auto", "default", "priority", "flex"):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                service_tier=tier
            )
            assert cfg.service_tier == tier

    def test_invalid_thinking_type_ignored(self):
        """Invalid thinking_type is set to None."""
        with patch('config.logger'):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                thinking_type="maybe"
            )
            assert cfg.thinking_type is None

    def test_valid_thinking_type(self):
        """Valid thinking_type values are accepted."""
        for tt in ("adaptive", "enabled", "disabled"):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                thinking_type=tt,
                thinking_budget_tokens=1000 if tt == "enabled" else None,
            )
            assert cfg.thinking_type == tt

    def test_thinking_type_enabled_without_budget(self):
        """thinking_type='enabled' without budget is reset to None."""
        with patch('config.logger'):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                thinking_type="enabled",
                thinking_budget_tokens=None,
            )
            assert cfg.thinking_type is None

    def test_thinking_type_enabled_with_budget(self):
        """thinking_type='enabled' with budget is accepted."""
        cfg = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            thinking_type="enabled",
            thinking_budget_tokens=1000,
        )
        assert cfg.thinking_type == "enabled"
        assert cfg.thinking_budget_tokens == 1000

    def test_api_mode_responses(self):
        """api_mode='responses' is accepted."""
        cfg = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            api_mode="responses"
        )
        assert cfg.api_mode == "responses"

    def test_api_mode_response_alias(self):
        """api_mode='response' is normalised to 'responses'."""
        cfg = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            api_mode="response"
        )
        assert cfg.api_mode == "responses"

    def test_api_mode_invalid_fallback(self):
        """Invalid api_mode falls back to 'chat_completions'."""
        with patch('config.logger'):
            cfg = LLMConfig(
                api_key="k", api_base="https://api.example.com",
                api_mode="graphql"
            )
            assert cfg.api_mode == "chat_completions"


# ══════════════════════════════════════════════════════════════════════
# LLMConfig — to_dict / from_dict
# ══════════════════════════════════════════════════════════════════════

class TestLLMConfigConversion:
    """Tests for LLMConfig.to_dict and from_dict."""

    def test_to_dict_basic_keys(self):
        """to_dict includes all basic keys."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com")
        d = cfg.to_dict()
        assert d["apikey"] == "k"
        assert d["apibase"] == "https://api.example.com"
        assert "model" in d
        assert "stream" in d
        assert "temperature" in d

    def test_to_dict_optional_keys_excluded(self):
        """to_dict excludes None optional keys by default."""
        cfg = LLMConfig(api_key="k", api_base="https://api.example.com")
        d = cfg.to_dict()
        assert "max_tokens" not in d
        assert "proxy" not in d
        assert "reasoning_effort" not in d

    def test_to_dict_optional_keys_included(self):
        """to_dict includes optional keys when set."""
        cfg = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            max_tokens=4096, proxy="http://proxy:8080",
            reasoning_effort="high",
        )
        d = cfg.to_dict()
        assert d["max_tokens"] == 4096
        assert d["proxy"] == "http://proxy:8080"
        assert d["reasoning_effort"] == "high"

    def test_from_dict_basic(self):
        """from_dict creates LLMConfig from a legacy dict."""
        raw = {
            "apikey": "sk-test",
            "apibase": "https://api.example.com",
            "model": "gpt-4",
        }
        cfg = LLMConfig.from_dict(raw)
        assert cfg.api_key == "sk-test"
        assert cfg.api_base == "https://api.example.com"
        assert cfg.model == "gpt-4"

    def test_from_dict_with_all_fields(self):
        """from_dict handles all known fields."""
        raw = {
            "apikey": "k",
            "apibase": "https://api.example.com",
            "model": "gpt-4",
            "name": "MyModel",
            "context_win": 50000,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 2048,
            "max_retries": 2,
            "proxy": "http://proxy:8080",
            "verify": False,
            "timeout": 10,
            "read_timeout": 60,
            "api_mode": "responses",
            "reasoning_effort": "medium",
            "service_tier": "auto",
            "thinking_type": "adaptive",
            "thinking_budget_tokens": 5000,
        }
        cfg = LLMConfig.from_dict(raw)
        assert cfg.context_win == 50000
        assert cfg.stream is False
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 2048
        assert cfg.max_retries == 2
        assert cfg.proxy == "http://proxy:8080"
        assert cfg.verify is False
        assert cfg.timeout == 10
        assert cfg.read_timeout == 60
        assert cfg.api_mode == "responses"
        assert cfg.reasoning_effort == "medium"
        assert cfg.service_tier == "auto"
        assert cfg.thinking_type == "adaptive"
        assert cfg.thinking_budget_tokens == 5000

    def test_from_dict_missing_fields_use_defaults(self):
        """from_dict uses defaults for missing fields."""
        raw = {"apikey": "k", "apibase": "https://api.example.com"}
        cfg = LLMConfig.from_dict(raw)
        assert cfg.context_win == 28000
        assert cfg.stream is True
        assert cfg.max_retries == 4

    def test_roundtrip(self):
        """from_dict(to_dict()) preserves the essential data."""
        original = LLMConfig(
            api_key="k", api_base="https://api.example.com",
            model="gpt-4", max_tokens=4096,
        )
        d = original.to_dict()
        restored = LLMConfig.from_dict(d)
        assert restored.api_key == original.api_key
        assert restored.api_base == original.api_base
        assert restored.model == original.model
        assert restored.max_tokens == original.max_tokens


# ══════════════════════════════════════════════════════════════════════
# AgentConfig
# ══════════════════════════════════════════════════════════════════════

class TestAgentConfig:
    """Tests for AgentConfig defaults and validation."""

    def test_defaults(self, tmp_workspace):
        """AgentConfig has sensible defaults."""
        cfg = AgentConfig()
        assert cfg.max_turns == 70
        assert cfg.default_timeout == 60
        assert cfg.verbose is False
        assert cfg.language == "fr"
        assert len(cfg.dangerous_shell_patterns) > 0

    def test_workspace_from_env(self, tmp_workspace):
        """AgentConfig reads workspace from GA_WORKSPACE env var."""
        cfg = AgentConfig()
        assert cfg.workspace_dir == tmp_workspace

    def test_custom_workspace(self, tmp_path):
        """AgentConfig accepts a custom workspace directory."""
        ws = str(tmp_path / "custom_ws")
        cfg = AgentConfig(workspace_dir=ws)
        assert cfg.workspace_dir == ws
        assert os.path.isdir(ws)

    def test_invalid_max_turns(self):
        """max_turns < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_turns"):
            AgentConfig(max_turns=0)

    def test_invalid_default_timeout(self):
        """default_timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="default_timeout"):
            AgentConfig(default_timeout=0)

    def test_env_var_overrides(self, isolated_config):
        """AgentConfig reads overrides from environment variables."""
        isolated_config(GA_MAX_TURNS="20", GA_TIMEOUT="30", GA_VERBOSE="true", GA_LANG="en")
        cfg = get_agent_config()
        assert cfg.max_turns == 20
        assert cfg.default_timeout == 30
        assert cfg.verbose is True
        assert cfg.language == "en"

    def test_verbose_false_values(self, isolated_config):
        """GA_VERBOSE with non-true values keeps verbose=False."""
        for val in ("0", "false", "no", "maybe"):
            isolated_config(GA_VERBOSE=val)
            cfg = get_agent_config()
            assert cfg.verbose is False


# ══════════════════════════════════════════════════════════════════════
# UIConfig
# ══════════════════════════════════════════════════════════════════════

class TestUIConfig:
    """Tests for UIConfig defaults and validation."""

    def test_defaults(self):
        """UIConfig has sensible defaults."""
        cfg = UIConfig()
        assert cfg.window_width == 530
        assert cfg.window_height == 700
        assert cfg.poll_interval_ms == 40
        assert cfg.autonomous_idle_timeout == 1800
        assert cfg.max_inline_chars == 6000

    def test_invalid_window_width(self):
        """window_width < 100 raises ValueError."""
        with pytest.raises(ValueError, match="window_width"):
            UIConfig(window_width=50)

    def test_invalid_window_height(self):
        """window_height < 100 raises ValueError."""
        with pytest.raises(ValueError, match="window_height"):
            UIConfig(window_height=50)

    def test_invalid_poll_interval(self):
        """poll_interval_ms < 1 raises ValueError."""
        with pytest.raises(ValueError, match="poll_interval_ms"):
            UIConfig(poll_interval_ms=0)

    def test_invalid_idle_timeout(self):
        """autonomous_idle_timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="autonomous_idle_timeout"):
            UIConfig(autonomous_idle_timeout=0)

    def test_invalid_max_inline_chars(self):
        """max_inline_chars < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_inline_chars"):
            UIConfig(max_inline_chars=0)

    def test_env_var_overrides(self, isolated_config):
        """UIConfig reads overrides from environment variables."""
        isolated_config(
            GA_UI_WIDTH="800", GA_UI_HEIGHT="600",
            GA_UI_POLL_MS="100", GA_UI_IDLE_TIMEOUT="3600",
            GA_UI_MAX_INLINE_CHARS="10000",
        )
        cfg = get_ui_config()
        assert cfg.window_width == 800
        assert cfg.window_height == 600
        assert cfg.poll_interval_ms == 100
        assert cfg.autonomous_idle_timeout == 3600
        assert cfg.max_inline_chars == 10000


# ══════════════════════════════════════════════════════════════════════
# load_llm_configs
# ══════════════════════════════════════════════════════════════════════

class TestLoadLLMConfigs:
    """Tests for load_llm_configs."""

    def test_loads_api_configs(self):
        """load_llm_configs loads entries with 'api' in the key name."""
        mock_data = {
            "api_claude": {
                "apikey": "sk-test",
                "apibase": "https://api.anthropic.com",
                "model": "claude-3",
            },
            "some_other_var": "not a config",
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert "api_claude" in result
        assert isinstance(result["api_claude"], LLMConfig)

    def test_loads_config_entries(self):
        """load_llm_configs loads entries with 'config' in the key name."""
        mock_data = {
            "my_config": {
                "apikey": "sk-test",
                "apibase": "https://api.example.com",
            },
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert "my_config" in result

    def test_loads_cookie_entries(self):
        """load_llm_configs loads entries with 'cookie' in the key name."""
        mock_data = {
            "cookie_auth": {
                "apikey": "sk-test",
                "apibase": "https://api.example.com",
            },
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert "cookie_auth" in result

    def test_skips_non_dict_values(self):
        """load_llm_configs skips entries that are not dicts."""
        mock_data = {
            "api_string": "not a dict",
            "api_number": 42,
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert len(result) == 0

    def test_skips_mixin_config(self):
        """load_llm_configs skips mixin_config even though it has 'config'."""
        mock_data = {
            "mixin_config": {
                "apikey": "k",
                "apibase": "https://api.example.com",
            },
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert "mixin_config" not in result

    def test_skips_invalid_configs_with_warning(self):
        """load_llm_configs skips entries that fail validation."""
        mock_data = {
            "api_invalid": {
                "apikey": "",  # empty key — will fail validation
                "apibase": "https://api.example.com",
            },
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert len(result) == 0

    def test_skips_non_matching_keys(self):
        """load_llm_configs skips entries without keyword match."""
        mock_data = {
            "random_var": {"apikey": "k", "apibase": "https://api.example.com"},
            "another_thing": 42,
        }
        with patch('config._load_mykeys_raw', return_value=mock_data):
            result = load_llm_configs()
        assert len(result) == 0

    def test_empty_raw_data(self):
        """load_llm_configs handles empty raw data."""
        with patch('config._load_mykeys_raw', return_value={}):
            result = load_llm_configs()
        assert result == {}


# ══════════════════════════════════════════════════════════════════════
# get_agent_config / get_ui_config
# ══════════════════════════════════════════════════════════════════════

class TestGetAgentConfig:
    """Tests for get_agent_config helper."""

    def test_returns_agent_config(self, tmp_workspace):
        """get_agent_config returns an AgentConfig instance."""
        cfg = get_agent_config()
        assert isinstance(cfg, AgentConfig)

    def test_default_max_turns(self, isolated_config, tmp_workspace):
        """get_agent_config returns default max_turns."""
        cfg = get_agent_config()
        assert cfg.max_turns == 70


class TestGetUIConfig:
    """Tests for get_ui_config helper."""

    def test_returns_ui_config(self):
        """get_ui_config returns a UIConfig instance."""
        cfg = get_ui_config()
        assert isinstance(cfg, UIConfig)

    def test_defaults(self):
        """get_ui_config returns default values."""
        cfg = get_ui_config()
        assert cfg.window_width == 530
        assert cfg.window_height == 700

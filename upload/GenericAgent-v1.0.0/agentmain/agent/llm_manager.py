"""LLM Manager — Session loading, switching, and name resolution.

Extracted from :mod:`agentmain.core` (task 3.1.2) so that LLM lifecycle
logic can be tested and reused independently of the full agent runtime.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, List, Optional, Tuple

from llmcore import (
    reload_mykeys,
    LLMSession,
    ToolClient,
    ClaudeSession,
    MixinSession,
    NativeToolClient,
    NativeClaudeSession,
    NativeOAISession,
)
from agentmain.prompts import load_tool_schema
from exceptions import SessionConfigError

logger = logging.getLogger("agentmain.agent.llm_manager")

# Maximum number of history exchanges to preserve across reloads.
DEFAULT_MAX_HISTORY_EXCHANGES: int = 50


class LLMManager:
    """Manages a list of LLM client backends and the active selection.

    Responsibilities:
      - Load / reload LLM sessions from :mod:`llmcore`
      - Switch between clients while preserving conversation history
      - Provide human-readable names for clients
    """

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY_EXCHANGES) -> None:
        self.llmclients: List[Any] = []
        self.llmclient: Any = None
        self.llm_no: int = 0
        self._max_history = max_history

    # ── Session loading ─────────────────────────────────────────────────

    def load_llm_sessions(self) -> None:
        """Reload LLM sessions from :mod:`llmcore` if the key file has changed.

        On first call (or when keys have changed) this rebuilds the
        ``self.llmclients`` list and preserves the existing conversation
        history on the active backend.
        """
        mykeys, changed = reload_mykeys()
        if not changed and self.llmclients:
            return

        # Preserve conversation history across reloads
        old_history: Optional[list] = None
        try:
            old_history = self.llmclient.backend.history
        except Exception:
            logger.debug("No existing history to preserve on LLM session reload")

        llm_sessions: List[Any] = []
        for k, cfg in mykeys.items():
            if not any(x in k for x in ["api", "config", "cookie"]):
                continue
            try:
                if "native" in k and "claude" in k:
                    llm_sessions.append(NativeToolClient(NativeClaudeSession(cfg=cfg)))
                elif "native" in k and "oai" in k:
                    llm_sessions.append(NativeToolClient(NativeOAISession(cfg=cfg)))
                elif "claude" in k:
                    llm_sessions.append(ToolClient(ClaudeSession(cfg=cfg)))
                elif "oai" in k:
                    llm_sessions.append(ToolClient(LLMSession(cfg=cfg)))
                elif "google" in k:
                    try:
                        from llmcore.google_provider import GoogleAIConfig, GoogleAISession
                        gconfig = GoogleAIConfig(api_key=cfg.get("api_key", cfg if isinstance(cfg, str) else ""))
                        from llmcore.clients import LLMSession as _LS
                        ga_session = GoogleAISession(gconfig)
                        llm_sessions.append(ToolClient(_LS(cfg=cfg)))  # fallback to generic
                    except Exception:
                        logger.debug("Google AI session init skipped for %s", k, exc_info=True)
                elif "mixin" in k:
                    llm_sessions.append({"mixin_cfg": cfg})
            except Exception:
                logger.debug("Skipping LLM session config %s due to init error", k, exc_info=True)

        # Resolve mixin placeholders
        for i, s in enumerate(llm_sessions):
            if isinstance(s, dict) and "mixin_cfg" in s:
                try:
                    mixin = MixinSession(llm_sessions, s["mixin_cfg"])
                    if isinstance(mixin._sessions[0], (NativeClaudeSession, NativeOAISession)):
                        llm_sessions[i] = NativeToolClient(mixin)
                    else:
                        llm_sessions[i] = ToolClient(mixin)
                except Exception as exc:
                    logger.error("Failed to init MixinSession: %s", exc)

        self.llmclients = llm_sessions
        if not self.llmclients:
            logger.error("No LLM sessions configured — check mykey.py / mykey.json")
            self.llmclient = None
            return
        self.llmclient = self.llmclients[self.llm_no % len(self.llmclients)]
        if old_history:
            self.llmclient.backend.history = copy.deepcopy(
                old_history[-self._max_history:]
            )

    # ── Client switching ────────────────────────────────────────────────

    def next_llm(self, n: int = -1) -> None:
        """Switch to the next (or specified) LLM client.

        Parameters
        ----------
        n : int
            If ``-1``, advance to the next client; otherwise switch to the
            client at index *n* (modulo the number of available clients).
        """
        self.load_llm_sessions()
        self.llm_no = ((self.llm_no + 1) if n < 0 else n) % len(self.llmclients)
        last_client = self.llmclient
        self.llmclient = self.llmclients[self.llm_no]
        try:
            self.llmclient.backend.history = copy.deepcopy(
                last_client.backend.history[-self._max_history:]
            )
        except Exception:
            raise SessionConfigError(
                f"Invalid Mixin configuration: failed to copy history from "
                f"{type(last_client.backend).__name__}. Check your mykey.py LLM_SESSIONS setting."
            )
        self.llmclient.last_tools = ""
        name = self.get_llm_name(model=True)
        if "glm" in name or "minimax" in name or "kimi" in name:
            load_tool_schema("_cn")
        else:
            load_tool_schema()

    # ── Name resolution ─────────────────────────────────────────────────

    def list_llms(self) -> List[Tuple[int, str, bool]]:
        """Return a summary of available LLM backends.

        Returns
        -------
        list[tuple[int, str, bool]]
            Each tuple contains ``(index, display_name, is_currently_active)``.
        """
        self.load_llm_sessions()
        return [
            (i, self.get_llm_name(b), i == self.llm_no)
            for i, b in enumerate(self.llmclients)
        ]

    def get_llm_name(self, b: Any = None, model: bool = False) -> str:
        """Return a human-readable name for an LLM client.

        Parameters
        ----------
        b : Any
            The client object.  Defaults to ``self.llmclient``.
        model : bool
            If ``True``, return the lowercase model name; otherwise return
            ``SessionType/name``.
        """
        b = self.llmclient if b is None else b
        if isinstance(b, dict):
            return "BADCONFIG_MIXIN"
        if model:
            return b.backend.model.lower()
        return f"{type(b.backend).__name__}/{b.backend.name}"

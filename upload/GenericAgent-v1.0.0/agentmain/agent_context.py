"""AgentContext — Dependency injection container for GenericAgent.

Provides a central registry for shared services (LLM manager, tool registry,
memory store, event bus) that are passed explicitly to constructors instead
of being accessed as globals.

Phase 3 (task 3.2.1) enhancements:
  - ``_driver``, ``_shell_confirm_callback``, ``_read_dirs`` as first-class
    attributes instead of module-level globals
  - Typed accessors for all well-known services
  - Integration with :class:`EventBus`
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Protocol

logger = logging.getLogger("ga.agentmain.agent_context")


class AgentContext:
    """Central service locator / DI container.

    Holds references to all shared services and passes them explicitly
    instead of using module-level globals.

    Usage::

        ctx = AgentContext()
        ctx.event_bus = get_event_bus()
        ctx.tool_registry = get_registry()
        ctx.llm_manager = agent._llm_mgr
        # Pass ctx to handlers, agents, etc.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

        # ── Well-known service references (set during initialization) ──
        self.event_bus: Any = None
        self.tool_registry: Any = None
        self.memory_store: Any = None
        self.llm_manager: Any = None

        # ── Formerly module-level globals in ga.py ─────────────────────
        self._driver: Any = None
        self._shell_confirm_callback: Optional[Callable[[str, str], bool]] = None
        self._read_dirs: List[str] = []

    # ── Generic service registry ─────────────────────────────────────────

    def register(self, name: str, service: Any) -> None:
        """Register a named service."""
        self._services[name] = service

    def get(self, name: str) -> Any:
        """Get a named service."""
        return self._services.get(name)

    # ── Formerly module-level globals (ga.py) ────────────────────────────

    @property
    def driver(self) -> Any:
        """The Selenium/WebDriver instance (was ``ga._driver``)."""
        return self._driver

    @driver.setter
    def driver(self, value: Any) -> None:
        self._driver = value

    @property
    def shell_confirm_callback(self) -> Optional[Callable[[str, str], bool]]:
        """Callback for confirming shell execution (was ``ga._shell_confirm_callback``).

        Signature: ``(code: str, code_type: str) -> bool``
        """
        return self._shell_confirm_callback

    @shell_confirm_callback.setter
    def shell_confirm_callback(self, value: Optional[Callable[[str, str], bool]]) -> None:
        self._shell_confirm_callback = value

    @property
    def read_dirs(self) -> List[str]:
        """Directories the agent is allowed to read from (was ``ga._read_dirs``)."""
        return self._read_dirs

    @read_dirs.setter
    def read_dirs(self, value: List[str]) -> None:
        self._read_dirs = value

    # ── Convenience: check if shell execution is allowed ─────────────────

    def should_confirm_shell(self, code: str, code_type: str) -> bool:
        """Ask the shell confirm callback whether execution is allowed.

        Returns ``True`` if the callback approves or if no callback is set
        *and* the ``--allow-dangerous-shell`` flag is active.
        Returns ``False`` (refuse) if the callback is ``None`` and no
        override is set.
        """
        if self._shell_confirm_callback is not None:
            return self._shell_confirm_callback(code, code_type)
        # No callback → refuse by default (safer)
        logger.warning("Shell execution requested but no confirm callback set — refusing")
        return False

    def __repr__(self) -> str:
        services = list(self._services.keys())
        parts = [f"services={services}"]
        if self._driver:
            parts.append("driver=set")
        if self._shell_confirm_callback:
            parts.append("shell_cb=set")
        if self._read_dirs:
            parts.append(f"read_dirs={len(self._read_dirs)}")
        return f"AgentContext({', '.join(parts)})"


# Global singleton
_global_context: Optional[AgentContext] = None


def get_agent_context() -> AgentContext:
    """Return the global AgentContext singleton."""
    global _global_context
    if _global_context is None:
        _global_context = AgentContext()
    return _global_context


def reset_agent_context() -> None:
    """Reset the global AgentContext (useful for testing)."""
    global _global_context
    _global_context = None


__all__ = [
    "AgentContext",
    "get_agent_context",
    "reset_agent_context",
]

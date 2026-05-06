"""Health check — Monitors agent subsystem health and exposes status.

This module provides :class:`HealthMonitor`, a lightweight singleton that
tracks agent runtime metrics: uptime, LLM call count, token usage, and
error rate.  All data stays local — nothing is sent externally.

Usage::

    from agentmain.health_check import get_health_monitor

    monitor = get_health_monitor()
    monitor.record_llm_call(tokens=150)

    status = monitor.get_status()
    # {"status": "healthy", "uptime_seconds": 42.3, "llm_calls": 1, ...}
"""

from __future__ import annotations

import logging
import os
import platform
import time
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("ga.agentmain.health_check")


class HealthMonitor:
    """Monitors agent subsystem health.

    Tracks: uptime, LLM call count, token usage, memory usage, error rate.
    All data stays local — nothing is sent externally.

    Thread-safe via an internal lock.

    Attributes
    ----------
    _start_time : float
        Monotonic clock value at initialisation.
    _llm_calls : int
        Number of LLM API calls made since startup.
    _token_usage : int
        Cumulative token consumption across all LLM calls.
    _errors : int
        Number of errors recorded since startup.
    _lock : threading.Lock
        Guard for thread-safe counter updates.
    """

    def __init__(self) -> None:
        self._start_time: float = time.monotonic()
        self._llm_calls: int = 0
        self._token_usage: int = 0
        self._errors: int = 0
        self._lock = threading.Lock()

    def record_llm_call(self, tokens: int = 0) -> None:
        """Record a completed LLM call.

        Parameters
        ----------
        tokens : int
            Number of tokens consumed by this call.  Defaults to 0.
        """
        with self._lock:
            self._llm_calls += 1
            self._token_usage += tokens

    def record_error(self) -> None:
        """Record an error occurrence.

        Call this whenever an LLM call, tool execution, or other subsystem
        operation fails.
        """
        with self._lock:
            self._errors += 1

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the current health status.

        Returns
        -------
        dict[str, Any]
            A dictionary containing:

            - ``status``: always ``"healthy"`` (future: ``"degraded"`` /
              ``"unhealthy"`` based on error rate thresholds)
            - ``uptime_seconds``: seconds since the monitor was created
            - ``llm_calls``: total LLM API calls
            - ``token_usage``: total tokens consumed
            - ``error_count``: total errors recorded
            - ``error_rate``: ratio of errors to LLM calls (0.0 if no calls)
            - ``platform``: OS name
            - ``python_version``: Python version string
        """
        with self._lock:
            uptime = time.monotonic() - self._start_time
            return {
                "status": "healthy",
                "uptime_seconds": round(uptime, 1),
                "llm_calls": self._llm_calls,
                "token_usage": self._token_usage,
                "error_count": self._errors,
                "error_rate": round(self._errors / max(self._llm_calls, 1), 4),
                "platform": platform.system(),
                "python_version": platform.python_version(),
            }

    def reset(self) -> None:
        """Reset all counters and restart the uptime clock.

        Useful in tests or when re-initialising the agent.
        """
        with self._lock:
            self._start_time = time.monotonic()
            self._llm_calls = 0
            self._token_usage = 0
            self._errors = 0


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Return the global :class:`HealthMonitor` singleton.

    Creates the instance on first call; returns the same instance on
    subsequent calls.

    Returns
    -------
    HealthMonitor
        The global health monitor instance.
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = HealthMonitor()
        logger.info("HealthMonitor initialized")
    return _global_monitor


__all__ = [
    "HealthMonitor",
    "get_health_monitor",
]

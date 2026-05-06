"""Opt-in crash reporting using Sentry (disabled by default).

This module provides a privacy-respecting crash reporting system:
- **Disabled by default** — no data is sent without explicit user opt-in
- **No PII** — ``send_default_pii=False`` ensures no personally identifiable information
- **No performance tracing** — ``traces_sample_rate=0.0``
- **Only exceptions** — captures unhandled exceptions for debugging

Usage::

    from agentmain.crash_reporter import init_crash_reporting, capture_exception

    # Initialize (called once at startup if user opts in)
    init_crash_reporting(dsn="https://xxx@sentry.io/123", enabled=True)

    # Capture an exception manually
    try:
        risky_operation()
    except Exception as exc:
        capture_exception(exc)
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Optional

logger = logging.getLogger("ga.crash_reporter")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_sentry_initialized: bool = False
_sentry_dsn: Optional[str] = None
_crash_log_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_crash_reporting(
    dsn: str = "",
    enabled: bool = False,
    crash_log_dir: Optional[str] = None,
) -> None:
    """Initialize crash reporting.

    This is a no-op if ``enabled`` is ``False`` or ``dsn`` is empty.
    Sentry is the remote backend; a local crash log is always written
    regardless of the Sentry setting.

    Parameters
    ----------
    dsn : str
        The Sentry DSN (Data Source Name). Must be provided if ``enabled``
        is ``True``.
    enabled : bool
        Whether to enable remote crash reporting. Defaults to ``False``.
    crash_log_dir : str | None
        Directory for local crash log files. Defaults to
        ``~/.genericagent/crash_logs/``.
    """
    global _sentry_initialized, _sentry_dsn, _crash_log_path

    # Local crash log directory
    if crash_log_dir is None:
        crash_log_dir = os.path.join(os.path.expanduser("~"), ".genericagent", "crash_logs")
    _crash_log_path = crash_log_dir
    os.makedirs(crash_log_dir, exist_ok=True)

    if not enabled or not dsn:
        logger.debug("Crash reporting disabled (enabled=%s, dsn=%s)", enabled, bool(dsn))
        return

    _sentry_dsn = dsn

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.0,  # No performance tracing
            send_default_pii=False,  # No personally identifiable information
            attach_stacktrace=True,
            max_breadcrumbs=20,
            # Release version for filtering
            release="genericagent@0.6.0",
        )
        _sentry_initialized = True
        logger.info("Crash reporting initialized (opt-in, no PII, Sentry DSN: %s...%s)",
                     dsn[:20], dsn[-8:] if len(dsn) > 28 else "")
    except ImportError:
        logger.debug("sentry-sdk not installed — remote crash reporting unavailable; "
                     "local crash logs will still be written")
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)


def capture_exception(exc: Exception, context: Optional[dict] = None) -> None:
    """Capture an exception for crash reporting.

    Always writes to the local crash log. If Sentry is initialized,
    also sends the exception remotely (without PII).

    Parameters
    ----------
    exc : Exception
        The exception to capture.
    context : dict | None
        Optional context dict to include with the crash report.
    """
    # 1. Local crash log (always)
    _write_local_crash_log(exc, context)

    # 2. Sentry (if initialized)
    if _sentry_initialized:
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                if context:
                    for key, value in context.items():
                        # Truncate long values to prevent oversized events
                        scope.set_extra(key, str(value)[:500])
                sentry_sdk.capture_exception(exc)
            logger.debug("Exception captured and sent to Sentry")
        except Exception as report_exc:
            logger.debug("Failed to send exception to Sentry: %s", report_exc)


def is_enabled() -> bool:
    """Return whether remote crash reporting is currently active."""
    return _sentry_initialized


# ---------------------------------------------------------------------------
# Local crash log
# ---------------------------------------------------------------------------


def _write_local_crash_log(exc: Exception, context: Optional[dict] = None) -> None:
    """Write exception details to a local crash log file.

    Each crash gets its own timestamped file in the crash log directory.
    Files are rotated — only the last 50 are kept.
    """
    if not _crash_log_path:
        return

    import time

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"crash_{timestamp}.log"
    filepath = os.path.join(_crash_log_path, filename)

    try:
        lines = [
            f"GenericAgent Crash Log — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"=" * 60,
            f"Exception Type: {type(exc).__name__}",
            f"Exception Message: {str(exc)[:500]}",
            "",
            "Traceback:",
            traceback.format_exc()[:5000],
        ]

        if context:
            lines.append("")
            lines.append("Context:")
            for k, v in context.items():
                lines.append(f"  {k}: {str(v)[:200]}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Rotate: keep only last 50 crash logs
        _rotate_crash_logs()

        logger.debug("Crash log written to %s", filepath)
    except Exception as log_exc:
        logger.debug("Failed to write crash log: %s", log_exc)


def _rotate_crash_logs(max_files: int = 50) -> None:
    """Remove old crash logs to keep only the most recent *max_files*."""
    if not _crash_log_path or not os.path.isdir(_crash_log_path):
        return

    try:
        crash_files = sorted(
            [f for f in os.listdir(_crash_log_path) if f.startswith("crash_") and f.endswith(".log")],
            reverse=True,
        )
        for old_file in crash_files[max_files:]:
            os.remove(os.path.join(_crash_log_path, old_file))
    except Exception:
        pass  # Non-critical


# ---------------------------------------------------------------------------
# Global exception hook
# ---------------------------------------------------------------------------


def install_global_exception_hook() -> None:
    """Install a global exception hook that captures unhandled exceptions.

    Call this once during application startup to automatically capture
    any exceptions that are not caught by the application code.
    """
    import sys

    original_excepthook = sys.excepthook

    def _crash_excepthook(exc_type, exc_value, exc_tb):
        """Custom excepthook that logs crashes before delegating to the original."""
        try:
            capture_exception(exc_value, context={"unhandled": True})
        except Exception:
            pass  # Don't let crash reporting cause more crashes
        finally:
            # Call the original excepthook to display the traceback normally
            original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_excepthook
    logger.debug("Global crash exception hook installed")


__all__ = [
    "init_crash_reporting",
    "capture_exception",
    "is_enabled",
    "install_global_exception_hook",
]

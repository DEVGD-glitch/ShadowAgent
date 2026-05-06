"""
Centralized logging configuration for Shadow Agent.

This module provides a unified logging setup for the entire Shadow Agent project,
replacing scattered ``logging.getLogger()`` calls and ``print()`` statements with
a consistent, configurable logging hierarchy rooted under the ``ga`` namespace.

Usage::

    from logging_config import setup_logging, get_logger

    # One-time initialisation (typically in the entry-point)
    root_logger = setup_logging(level=logging.DEBUG, log_file="ga.log")

    # Elsewhere in the project
    logger = get_logger("llmcore")
    logger.info("LLM request sent")

The logger hierarchy mirrors the dotted namespace convention so that
``get_logger("llmcore")`` returns a logger named ``ga.llmcore``, which
inherits configuration from the ``ga`` root logger.
"""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LOG_FORMAT: str = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
"""Default log message format string."""

DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
"""Default timestamp format applied to the ``%(asctime)s`` placeholder."""

LOG_LEVELS: Dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
"""Mapping of human-readable level names to :mod:`logging` constants."""


# ---------------------------------------------------------------------------
# Sensitive data redaction (Task 8.2.4)
# ---------------------------------------------------------------------------

# Patterns that match API keys and other secrets in log output.
# - sk-ant-... : Anthropic API keys
# - sk-...    : OpenAI-style API keys (20+ chars after sk-)
# - Generic long alphanumeric strings that look like API tokens
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Anthropic keys: sk-ant-api03-XXXX... (typically 100+ chars)
    (re.compile(r'sk-ant-[A-Za-z0-9_\-]{20,}'), 'sk-ant-***REDACTED***'),
    # OpenAI-style keys: sk-XXXX... (at least 20 chars after sk-, may contain hyphens)
    (re.compile(r'sk-[A-Za-z0-9_\-]{20,}'), 'sk-***REDACTED***'),
    # Generic Bearer tokens in URLs or headers (long hex/base64 strings)
    (re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]{20,}'), r'\1***REDACTED***'),
    # x-api-key header values
    (re.compile(r'(x-api-key["\s:=]+)[A-Za-z0-9_\-]{20,}'), r'\1***REDACTED***'),
    # API key in dict-style logging: 'apikey': '...'
    (re.compile(r"('apikey'['\"]?\s*:\s*['\"])[^'\"]{8,}(['\"])?"), r'\1***REDACTED***\2'),
    # api_key=... pattern
    (re.compile(r'(api_key["\s:=]+)[A-Za-z0-9_\-]{20,}'), r'\1***REDACTED***'),
    # key_* patterns (e.g. key_openai, key_anthropic)
    (re.compile(r'(key_[A-Za-z0-9_]+["\s:=]+)[A-Za-z0-9_\-]{20,}'), r'\1***REDACTED***'),
    # *_API_KEY environment variable values
    (re.compile(r'(_API_KEY["\s:=]+)[A-Za-z0-9_\-]{20,}'), r'\1***REDACTED***'),
]

# Maximum length for user messages in logs (to prevent leaking user content).
_MAX_USER_MESSAGE_LEN: int = 50

# Maximum length for file contents in logs.
_MAX_FILE_CONTENT_LEN: int = 100


def redact_sensitive(text: str) -> str:
    """Redact API keys, user messages, and file contents from *text*.

    Applies the following redaction steps in order:

    1. **API key patterns** — Replace known secret patterns (``sk-*``,
       ``key_*``, ``*_API_KEY``, Bearer tokens, etc.) with
       ``***REDACTED***`` placeholders.

    2. **User message truncation** — Truncate user-facing messages
       (patterns like ``[USER]: ...``) to 50 characters to prevent
       sensitive user content from appearing in log files.

    3. **File content truncation** — Truncate file content previews
       (patterns like ``<file_content>...</file_content>``) to 100
       characters.

    Parameters
    ----------
    text : str
        The log message text to redact.

    Returns
    -------
    str
        The redacted text with secrets replaced and content truncated.
    """
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)

    # Truncate user messages to prevent logging sensitive user content
    text = re.sub(
        r'(\[USER\]:\s*)(.{1,' + str(_MAX_USER_MESSAGE_LEN) + r'}).*',
        r'\1\2[...truncated]',
        text,
    )

    # Truncate file content previews in logs
    text = re.sub(
        r'(<file_content>)(.{1,' + str(_MAX_FILE_CONTENT_LEN) + r'})(.*?)(</file_content>)',
        r'\1\2[...truncated]\4',
        text,
        flags=re.DOTALL,
    )

    return text


class RedactingFilter(logging.Filter):
    """Logging filter that redacts API keys, user messages, and file contents.

    Applied to all handlers under the ``ga`` logger hierarchy so that
    secrets and sensitive user content never appear in log files or
    console output.

    Redaction rules:
    - API key patterns (``sk-*``, ``key_*``, ``*_API_KEY``, Bearer tokens)
      are replaced with ``***REDACTED***``.
    - User messages (``[USER]: ...``) are truncated to 50 characters.
    - File content previews (``<file_content>...</file_content>``) are
      truncated to 100 characters.

    This is a **defence-in-depth** measure — code should also avoid
    passing secrets to logger calls in the first place.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log record's message."""
        record.msg = redact_sensitive(str(record.msg))
        # Also redact any already-formatted args
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive(str(v)) if isinstance(v, str) else v
                    for v in record.args
                )
        return True


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

class LogColors:
    """ANSI colour codes for terminal log output.

    Each constant is a raw ANSI escape sequence that can be prepended to a
    string to colourise it.  :attr:`RESET` should be appended afterwards to
    return the terminal to its default colour.

    Example::

        coloured = f"{LogColors.INFO}Something happened{LogColors.RESET}"
    """

    DEBUG: str = "\033[36m"       # Cyan
    INFO: str = "\033[32m"        # Green
    WARNING: str = "\033[33m"     # Yellow
    ERROR: str = "\033[31m"       # Red
    CRITICAL: str = "\033[1;31m"  # Bold Red
    RESET: str = "\033[0m"

    @staticmethod
    def colorize(text: str, level: int) -> str:
        """Return *text* wrapped in the ANSI colour that corresponds to *level*.

        Parameters
        ----------
        text : str
            The message to colourise.
        level : int
            A standard :mod:`logging` level (e.g. ``logging.INFO``).

        Returns
        -------
        str
            The colour-wrapped string.  If *level* does not map to a known
            colour, the original *text* is returned unchanged.
        """
        colour_map: Dict[int, str] = {
            logging.DEBUG: LogColors.DEBUG,
            logging.INFO: LogColors.INFO,
            logging.WARNING: LogColors.WARNING,
            logging.ERROR: LogColors.ERROR,
            logging.CRITICAL: LogColors.CRITICAL,
        }
        colour = colour_map.get(level)
        if colour is None:
            return text
        return f"{colour}{text}{LogColors.RESET}"


# ---------------------------------------------------------------------------
# ColoredFormatter
# ---------------------------------------------------------------------------

class ColoredFormatter(logging.Formatter):
    """A :class:`logging.Formatter` subclass that injects ANSI colours into
    the formatted output based on the record's log level.

    Only the *levelname* portion of the message is colourised so that the
    timestamp and logger name remain uncoloured, keeping log files readable
    when colours are not supported (e.g. when writing to a file).

    If the target stream is not a TTY the colour codes are omitted
    automatically — call :meth:`set_tty` to control this behaviour.
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        *,
        tty: bool = True,
    ) -> None:
        """Initialise the formatter.

        Parameters
        ----------
        fmt : str | None
            Format string.  Falls back to :data:`DEFAULT_LOG_FORMAT` when
            *None*.
        datefmt : str | None
            Date format string.  Falls back to :data:`DEFAULT_DATE_FORMAT`
            when *None*.
        tty : bool
            Whether the output stream is a TTY.  When ``True`` (the default)
            ANSI colour codes are emitted; when ``False`` they are suppressed.
        """
        super().__init__(fmt or DEFAULT_LOG_FORMAT, datefmt or DEFAULT_DATE_FORMAT)
        self._tty: bool = tty

    # -- public helper ------------------------------------------------------

    def set_tty(self, tty: bool) -> None:
        """Enable or disable colour output at runtime.

        This is useful when a handler is attached to a stream whose TTY
        status is determined after the formatter is created.
        """
        self._tty = tty

    # -- Formatter override -------------------------------------------------

    def format(self, record: logging.LogRecord) -> str:
        """Format *record*, colourising the level name when appropriate."""
        # Preserve the original levelname so that other formatters in the
        # chain are not affected.
        original_levelname = record.levelname
        if self._tty:
            record.levelname = LogColors.colorize(record.levelname, record.levelno)
        result = super().format(record)
        record.levelname = original_levelname  # restore
        return result


# ---------------------------------------------------------------------------
# Core setup
# ---------------------------------------------------------------------------

def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """Configure and return the root ``ga`` logger.

    This function is the single entry-point for all logging configuration in
    Shadow Agent.  Call it once during application start-up; all subsequent
    calls to :func:`get_logger` will inherit the configuration applied here.

    Parameters
    ----------
    level : int
        The minimum severity level that will be processed.  Defaults to
        ``logging.INFO``.
    log_file : str | None
        Optional path to a log file.  When provided a
        :class:`~logging.handlers.RotatingFileHandler` is attached that
        rotates at 10 MB with up to 3 backup files.
    format_string : str | None
        Custom format string.  Falls back to :data:`DEFAULT_LOG_FORMAT` when
        *None*.

    Returns
    -------
    logging.Logger
        The configured root ``ga`` logger.

    Notes
    -----
    * A :class:`logging.StreamHandler` writing to *stderr* is always added.
    * The ``ga`` root logger does **not** propagate to the global root logger
      to avoid duplicate output when the application has configured the root
      logger independently.
    * The ``ga.llmcore`` sub-logger is explicitly created so that callers
      can retrieve it via :func:`get_logger` without additional setup.
    """
    fmt = format_string or DEFAULT_LOG_FORMAT

    # -- Root "ga" logger ---------------------------------------------------
    ga_logger = logging.getLogger("ga")
    ga_logger.setLevel(level)
    ga_logger.propagate = False  # avoid duplicate output via global root

    # Remove any pre-existing handlers so that repeated calls to setup_logging
    # do not stack duplicate handlers (useful during testing or re-config).
    ga_logger.handlers.clear()

    # RedactingFilter — applied to all handlers to strip API keys (Task 8.2.4)
    redacting_filter = RedactingFilter()

    # StreamHandler (stderr) with coloured output
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(level)
    is_stderr_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    stream_handler.setFormatter(ColoredFormatter(fmt, DEFAULT_DATE_FORMAT, tty=is_stderr_tty))
    stream_handler.addFilter(redacting_filter)
    ga_logger.addHandler(stream_handler)

    # RotatingFileHandler (optional)
    if log_file is not None:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        # File output should not contain ANSI escape codes
        file_handler.setFormatter(
            logging.Formatter(fmt, DEFAULT_DATE_FORMAT)
        )
        file_handler.addFilter(redacting_filter)
        ga_logger.addHandler(file_handler)

    # -- "llmcore" sub-logger -----------------------------------------------
    llmcore_logger = logging.getLogger("ga.llmcore")
    llmcore_logger.setLevel(level)
    llmcore_logger.propagate = True  # inherit handlers from "ga" root

    return ga_logger


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``ga`` hierarchy.

    If *name* already starts with ``ga.`` it is used as-is; otherwise the
    ``ga.`` prefix is prepended so that the returned logger always sits
    beneath the ``ga`` root logger and inherits its configuration.

    Parameters
    ----------
    name : str
        A short, dot-free identifier (e.g. ``"llmcore"``) or a dotted path
        that may or may not already include the ``ga.`` prefix.

    Returns
    -------
    logging.Logger
        A logger named ``ga.<name>`` (or ``ga`` when *name* is ``"ga"``).

    Examples
    --------
    >>> get_logger("llmcore")      # -> logger named "ga.llmcore"
    >>> get_logger("ga.llmcore")   # -> same logger, prefix preserved
    >>> get_logger("ga")           # -> the root "ga" logger itself
    """
    if name == "ga" or name.startswith("ga."):
        return logging.getLogger(name)
    return logging.getLogger(f"ga.{name}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_DATE_FORMAT",
    "LOG_LEVELS",
    "LogColors",
    "ColoredFormatter",
    "RedactingFilter",
    "redact_sensitive",
    "setup_logging",
    "get_logger",
]

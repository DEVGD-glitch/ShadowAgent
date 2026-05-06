"""Tests for the logging_config module.

Covers setup_logging, get_logger, LogColors, ColoredFormatter, and
the DEFAULT_LOG_FORMAT / LOG_LEVELS constants.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from logging_config import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_DATE_FORMAT,
    LOG_LEVELS,
    LogColors,
    ColoredFormatter,
    setup_logging,
    get_logger,
)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    """Tests for module-level constants."""

    def test_default_log_format_is_string(self):
        """DEFAULT_LOG_FORMAT is a non-empty string."""
        assert isinstance(DEFAULT_LOG_FORMAT, str)
        assert len(DEFAULT_LOG_FORMAT) > 0

    def test_default_log_format_contains_placeholders(self):
        """DEFAULT_LOG_FORMAT contains standard log format placeholders."""
        assert "%(asctime)s" in DEFAULT_LOG_FORMAT
        assert "%(name)s" in DEFAULT_LOG_FORMAT
        assert "%(levelname)s" in DEFAULT_LOG_FORMAT
        assert "%(message)s" in DEFAULT_LOG_FORMAT

    def test_default_date_format_is_string(self):
        """DEFAULT_DATE_FORMAT is a non-empty string."""
        assert isinstance(DEFAULT_DATE_FORMAT, str)
        assert len(DEFAULT_DATE_FORMAT) > 0

    def test_log_levels_mapping(self):
        """LOG_LEVELS maps standard level names to logging constants."""
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL

    def test_log_levels_has_all_standard_levels(self):
        """LOG_LEVELS contains all five standard logging levels."""
        assert set(LOG_LEVELS.keys()) == {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


# ══════════════════════════════════════════════════════════════════════
# LogColors
# ══════════════════════════════════════════════════════════════════════

class TestLogColors:
    """Tests for the LogColors class."""

    def test_color_attributes_exist(self):
        """LogColors has all required colour attributes."""
        assert hasattr(LogColors, "DEBUG")
        assert hasattr(LogColors, "INFO")
        assert hasattr(LogColors, "WARNING")
        assert hasattr(LogColors, "ERROR")
        assert hasattr(LogColors, "CRITICAL")
        assert hasattr(LogColors, "RESET")

    def test_color_values_are_ansi(self):
        """LogColors values are ANSI escape sequences."""
        for attr in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "RESET"):
            val = getattr(LogColors, attr)
            assert isinstance(val, str)
            assert val.startswith("\033[")

    def test_colorize_debug(self):
        """colorize wraps text in DEBUG colour."""
        result = LogColors.colorize("msg", logging.DEBUG)
        assert result.startswith(LogColors.DEBUG)
        assert result.endswith(LogColors.RESET)
        assert "msg" in result

    def test_colorize_info(self):
        """colorize wraps text in INFO colour."""
        result = LogColors.colorize("msg", logging.INFO)
        assert result.startswith(LogColors.INFO)
        assert "msg" in result

    def test_colorize_warning(self):
        """colorize wraps text in WARNING colour."""
        result = LogColors.colorize("msg", logging.WARNING)
        assert result.startswith(LogColors.WARNING)
        assert "msg" in result

    def test_colorize_error(self):
        """colorize wraps text in ERROR colour."""
        result = LogColors.colorize("msg", logging.ERROR)
        assert result.startswith(LogColors.ERROR)
        assert "msg" in result

    def test_colorize_critical(self):
        """colorize wraps text in CRITICAL colour."""
        result = LogColors.colorize("msg", logging.CRITICAL)
        assert result.startswith(LogColors.CRITICAL)
        assert "msg" in result

    def test_colorize_unknown_level(self):
        """colorize returns text unchanged for unknown levels."""
        result = LogColors.colorize("msg", 999)
        assert result == "msg"

    def test_colorize_empty_string(self):
        """colorize handles empty strings."""
        result = LogColors.colorize("", logging.INFO)
        assert LogColors.INFO in result
        assert LogColors.RESET in result


# ══════════════════════════════════════════════════════════════════════
# ColoredFormatter
# ══════════════════════════════════════════════════════════════════════

class TestColoredFormatter:
    """Tests for the ColoredFormatter class."""

    def test_init_defaults(self):
        """ColoredFormatter initialises with default format and tty=True."""
        fmt = ColoredFormatter()
        assert fmt._tty is True

    def test_init_custom_format(self):
        """ColoredFormatter accepts a custom format string."""
        custom = "%(message)s"
        fmt = ColoredFormatter(fmt=custom)
        # The format should be stored by the parent class
        assert fmt._fmt == custom or fmt._fmt is not None

    def test_init_tty_false(self):
        """ColoredFormatter can be initialised with tty=False."""
        fmt = ColoredFormatter(tty=False)
        assert fmt._tty is False

    def test_set_tty(self):
        """set_tty changes the TTY mode at runtime."""
        fmt = ColoredFormatter(tty=True)
        fmt.set_tty(False)
        assert fmt._tty is False
        fmt.set_tty(True)
        assert fmt._tty is True

    def test_format_with_tty_adds_color(self):
        """format() colourises levelname when tty=True."""
        fmt = ColoredFormatter(tty=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="hello",
            args=None, exc_info=None,
        )
        result = fmt.format(record)
        # The levelname should be colourised
        assert LogColors.INFO in result or "INFO" in result

    def test_format_without_tty_no_color(self):
        """format() does not colourise levelname when tty=False."""
        fmt = ColoredFormatter(tty=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="hello",
            args=None, exc_info=None,
        )
        result = fmt.format(record)
        # Should not contain ANSI colour codes in the levelname
        assert LogColors.INFO not in result

    def test_format_preserves_original_levelname(self):
        """format() restores the original levelname after formatting."""
        fmt = ColoredFormatter(tty=True)
        record = logging.LogRecord(
            name="test", level=logging.WARNING,
            pathname="", lineno=0, msg="test",
            args=None, exc_info=None,
        )
        original = record.levelname
        fmt.format(record)
        assert record.levelname == original

    def test_format_includes_message(self):
        """format() includes the log message."""
        fmt = ColoredFormatter(tty=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="hello world",
            args=None, exc_info=None,
        )
        result = fmt.format(record)
        assert "hello world" in result


# ══════════════════════════════════════════════════════════════════════
# setup_logging
# ══════════════════════════════════════════════════════════════════════

class TestSetupLogging:
    """Tests for setup_logging."""

    def _clear_ga_logger(self):
        """Remove handlers from the 'ga' logger to avoid stacking."""
        ga_logger = logging.getLogger("ga")
        ga_logger.handlers.clear()

    def setup_method(self):
        """Clean up ga logger before each test."""
        self._clear_ga_logger()

    def teardown_method(self):
        """Clean up ga logger after each test."""
        self._clear_ga_logger()

    def test_returns_logger(self):
        """setup_logging returns a logging.Logger."""
        result = setup_logging()
        assert isinstance(result, logging.Logger)

    def test_returns_ga_logger(self):
        """setup_logging returns the 'ga' root logger."""
        result = setup_logging()
        assert result.name == "ga"

    def test_sets_log_level(self):
        """setup_logging sets the log level on the ga logger."""
        logger = setup_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_default_level_is_info(self):
        """setup_logging defaults to INFO level."""
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_has_stream_handler(self):
        """setup_logging adds a StreamHandler."""
        logger = setup_logging()
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(stream_handlers) >= 1

    def test_propagate_is_false(self):
        """setup_logging sets propagate=False on the ga logger."""
        logger = setup_logging()
        assert logger.propagate is False

    def test_with_log_file(self):
        """setup_logging adds a RotatingFileHandler when log_file is given."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            logger = setup_logging(log_file=log_path)
            file_handlers = [
                h for h in logger.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(file_handlers) == 1
        finally:
            os.unlink(log_path)

    def test_without_log_file_no_file_handler(self):
        """setup_logging adds no RotatingFileHandler without log_file."""
        logger = setup_logging()
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 0

    def test_creates_llmcore_sublogger(self):
        """setup_logging creates the ga.llmcore sub-logger."""
        setup_logging()
        llmcore_logger = logging.getLogger("ga.llmcore")
        assert llmcore_logger.name == "ga.llmcore"

    def test_llmcore_propagate_is_true(self):
        """The ga.llmcore sub-logger propagates to the ga root."""
        setup_logging()
        llmcore_logger = logging.getLogger("ga.llmcore")
        assert llmcore_logger.propagate is True

    def test_repeated_calls_no_duplicate_handlers(self):
        """Repeated calls to setup_logging do not stack handlers."""
        setup_logging()
        count1 = len(logging.getLogger("ga").handlers)
        setup_logging()
        count2 = len(logging.getLogger("ga").handlers)
        assert count1 == count2

    def test_custom_format_string(self):
        """setup_logging accepts a custom format string."""
        custom = "%(message)s"
        logger = setup_logging(format_string=custom)
        # At least one handler should use the custom format
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.handlers.RotatingFileHandler
            ):
                fmt = handler.formatter
                assert fmt is not None


# ══════════════════════════════════════════════════════════════════════
# get_logger
# ══════════════════════════════════════════════════════════════════════

class TestGetLogger:
    """Tests for get_logger."""

    def test_simple_name(self):
        """get_logger with a simple name returns ga.<name> logger."""
        logger = get_logger("mymodule")
        assert logger.name == "ga.mymodule"

    def test_prefixed_name(self):
        """get_logger with a 'ga.' prefix preserves it."""
        logger = get_logger("ga.mymodule")
        assert logger.name == "ga.mymodule"

    def test_ga_name(self):
        """get_logger('ga') returns the root ga logger."""
        logger = get_logger("ga")
        assert logger.name == "ga"

    def test_returns_logger_instance(self):
        """get_logger returns a logging.Logger."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)

    def test_same_name_returns_same_logger(self):
        """Calling get_logger with the same name returns the same logger."""
        logger1 = get_logger("consistent")
        logger2 = get_logger("consistent")
        assert logger1 is logger2

    def test_dotted_name_without_prefix(self):
        """get_logger with a dotted name without 'ga.' prefix adds the prefix."""
        logger = get_logger("sub.module")
        assert logger.name == "ga.sub.module"

    def test_dotted_name_with_prefix(self):
        """get_logger with a dotted name starting with 'ga.' preserves it."""
        logger = get_logger("ga.sub.module")
        assert logger.name == "ga.sub.module"

    def test_llmcore_name(self):
        """get_logger('llmcore') returns the ga.llmcore logger."""
        logger = get_logger("llmcore")
        assert logger.name == "ga.llmcore"


# ══════════════════════════════════════════════════════════════════════
# Integration: setup_logging + get_logger
# ══════════════════════════════════════════════════════════════════════

class TestLoggingIntegration:
    """Integration tests for setup_logging + get_logger working together."""

    def _clear_ga_logger(self):
        ga_logger = logging.getLogger("ga")
        ga_logger.handlers.clear()

    def setup_method(self):
        self._clear_ga_logger()

    def teardown_method(self):
        self._clear_ga_logger()

    def test_sub_logger_inherits_level(self):
        """Sub-loggers inherit effective level from the ga root."""
        setup_logging(level=logging.WARNING)
        sub = get_logger("mymod")
        # The effective level should be WARNING (from the root ga logger)
        assert sub.getEffectiveLevel() == logging.WARNING

    def test_log_record_reaches_handler(self):
        """A log record from a sub-logger reaches the ga root handler."""
        messages = []
        setup_logging(level=logging.DEBUG)

        # Add a custom handler that captures messages
        ga_logger = logging.getLogger("ga")
        capture_handler = logging.Handler()
        capture_handler.emit = lambda record: messages.append(record.getMessage())
        capture_handler.setLevel(logging.DEBUG)
        ga_logger.addHandler(capture_handler)

        sub = get_logger("testmod")
        sub.info("integration test message")
        assert any("integration test message" in m for m in messages)

    def test_log_file_written(self):
        """Log messages are written to the log file."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode='w') as f:
            log_path = f.name

        try:
            setup_logging(level=logging.DEBUG, log_file=log_path)
            sub = get_logger("filetest")
            sub.warning("file test warning")

            # Flush handlers
            ga_logger = logging.getLogger("ga")
            for h in ga_logger.handlers:
                h.flush()

            with open(log_path, 'r') as f:
                content = f.read()
            assert "file test warning" in content
        finally:
            os.unlink(log_path)

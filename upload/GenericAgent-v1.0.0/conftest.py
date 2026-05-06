"""Root-level pytest configuration with shared fixtures for GenericAgent tests.

Provides reusable fixtures for temporary workspaces, mock agents, isolated
configuration overrides, and logging capture.  Also registers custom markers
for test categorisation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Custom markers
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so that ``pytest --strict-markers`` passes."""
    config.addinivalue_line("markers", "qt: tests requiring PySide6")
    config.addinivalue_line("markers", "slow: slow tests")
    config.addinivalue_line("markers", "integration: integration tests")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_workspace(tmp_path):
    """Create a temporary directory and set ``GA_WORKSPACE`` to it.

    The environment variable is restored after the test so that parallel
    or subsequent tests are not affected.

    Returns
    -------
    str
        The absolute path of the temporary workspace directory.
    """
    workspace = str(tmp_path / "ga_workspace")
    os.makedirs(workspace, exist_ok=True)
    old = os.environ.get("GA_WORKSPACE")
    os.environ["GA_WORKSPACE"] = workspace
    try:
        yield workspace
    finally:
        if old is None:
            os.environ.pop("GA_WORKSPACE", None)
        else:
            os.environ["GA_WORKSPACE"] = old


@pytest.fixture()
def mock_agent():
    """Create a :class:`~unittest.mock.MagicMock` agent with common attributes.

    The mock exposes ``put_task``, ``abort``, and ``is_running`` so that
    tests can exercise code paths that interact with the agent without
    requiring a real agent instance.

    Returns
    -------
    unittest.mock.MagicMock
        A mock agent instance.
    """
    agent = MagicMock()
    agent.put_task.return_value = None
    agent.abort.return_value = None
    agent.is_running = False
    return agent


@pytest.fixture()
def isolated_config():
    """Temporarily override configuration values and restore them afterwards.

    The fixture yields a helper function that accepts keyword arguments
    representing the config overrides.  The original values (or their
    absence) are restored when the test finishes.

    Usage::

        def test_something(isolated_config):
            isolated_config(GA_MAX_TURNS="20", GA_LANG="en")
            # ... test code that reads GA_MAX_TURNS / GA_LANG ...

    Returns
    -------
    callable
        A function ``override(**kwargs)`` that sets environment variables.
    """
    saved: dict[str, str | None] = {}

    def _override(**kwargs):
        for key, value in kwargs.items():
            saved[key] = os.environ.get(key)
            os.environ[key] = str(value)

    yield _override

    # Restore original values
    for key, original in saved.items():
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original


@pytest.fixture()
def caplog_available():
    """Ensure that :mod:`logging` capture works with the ``caplog`` fixture.

    Some loggers propagate to the root logger which may have its handlers
    configured in a way that prevents ``caplog`` from capturing records.
    This fixture temporarily ensures that the ``ga`` root logger propagates
    so that ``caplog`` sees all log events during the test.

    Returns
    -------
    None
    """
    ga_logger = logging.getLogger("ga")
    original_propagate = ga_logger.propagate
    ga_logger.propagate = True
    try:
        yield
    finally:
        ga_logger.propagate = original_propagate

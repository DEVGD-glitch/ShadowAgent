#!/usr/bin/env python3
"""GenericAgent — Sidecar Entry Point for PyInstaller Bundle

This is the ACTUAL entry point used by PyInstaller to create the sidecar exe.
Unlike launch_backend.py (which tries to find server.py on the filesystem),
this script works in BUNDLED mode where all backend source files are packed
inside the PyInstaller archive via --add-data.

When the exe runs:
  1. PyInstaller extracts all --add-data files to a temp dir (sys._MEIPASS)
  2. We add that dir to sys.path so Python can import server.py, agentmain/, etc.
  3. We import and start the FastAPI server

For DEVELOPMENT mode (not frozen):
  - Falls back to finding the backend directory from the project structure
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

# ─── Version ─────────────────────────────────────────────────────
_VERSION = "v1.2.0"

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,  # stderr so Tauri captures it via CommandEvent::Stderr
)
logger = logging.getLogger("sidecar_entry")


def _setup_bundled_path() -> Path | None:
    """In PyInstaller bundled mode, add _MEIPASS to sys.path.

    Returns the _MEIPASS path if bundled, None otherwise.
    """
    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        return None

    base = Path(sys._MEIPASS)  # type: ignore[attr-defined]

    # Add extraction dir to sys.path so imports work
    base_str = str(base)
    if base_str not in sys.path:
        sys.path.insert(0, base_str)
        logger.info("Added bundled path to sys.path: %s", base_str)

    # Also add parent for package imports
    parent_str = str(base.parent)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)

    # Set working directory to the extraction dir
    os.chdir(base)
    logger.info("Working directory set to: %s", base)

    # Set environment variable so server.py can find its files
    os.environ["GA_BACKEND_DIR"] = base_str

    return base


def _setup_dev_path() -> Path | None:
    """In development mode, find the backend directory.

    Returns the backend dir path if found, None otherwise.
    """
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir / ".." / ".." / "upload" / f"GenericAgent-{_VERSION}",
        script_dir / f"GenericAgent-{_VERSION}",
        script_dir,
    ]

    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.is_dir() and (candidate / "server.py").exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            parent_str = str(candidate.parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)
            os.chdir(candidate)
            os.environ["GA_BACKEND_DIR"] = candidate_str
            logger.info("Using development backend at: %s", candidate)
            return candidate

    return None


def _setup_ssl() -> None:
    """Configure SSL certificate paths."""
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass


_server_instance = None


def _signal_handler(sig: int, frame: object) -> None:
    """Signal handler that triggers graceful uvicorn shutdown."""
    global _server_instance
    sig_name = signal.Signals(sig).name
    logger.info("Received %s, shutting down...", sig_name)
    if _server_instance is not None:
        _server_instance.should_exit = True


def _setup_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, _signal_handler)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def main() -> int:
    """Main entry point for the sidecar backend."""
    logger.info("=" * 60)
    logger.info("GenericAgent Sidecar Backend")
    logger.info("=" * 60)
    logger.info("Python %s on %s", sys.version, sys.platform)

    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        logger.info("Mode: BUNDLED (PyInstaller)")
    else:
        logger.info("Mode: DEVELOPMENT")

    # Setup paths
    if is_frozen:
        backend_path = _setup_bundled_path()
    else:
        backend_path = _setup_dev_path()

    if backend_path is None:
        logger.error("FATAL: Cannot locate backend source files!")
        logger.error("In bundled mode, ensure --add-data was used correctly.")
        logger.error("In dev mode, ensure upload/GenericAgent-%s/ exists.", _VERSION)
        return 1

    # SSL
    _setup_ssl()

    # Signals
    _setup_signal_handlers()

    # Import server
    try:
        import server as server_module
        logger.info("Imported server module successfully")
    except ImportError as exc:
        logger.error("FATAL: Failed to import server: %s", exc)
        logger.error("sys.path entries:")
        for p in sys.path[:10]:
            logger.error("  - %s", p)
        return 1

    # Check if FastAPI is available
    if hasattr(server_module, "is_available") and not server_module.is_available():
        logger.error("FATAL: FastAPI not available")
        return 1

    # Configuration
    host = os.environ.get("GA_HOST", "127.0.0.1")

    def _safe_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    port = _safe_int(os.environ.get("GA_PORT", "8765"), 8765)
    logger.info("Starting server on %s:%d", host, port)

    # Start the server
    try:
        import uvicorn
        if hasattr(server_module, "create_app"):
            app = server_module.create_app()
        elif hasattr(server_module, "app"):
            app = server_module.app
        else:
            logger.error("FATAL: server module has no create_app() or app attribute")
            return 1
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        global _server_instance
        _server_instance = uvicorn.Server(config)
        _server_instance.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted")
    except Exception as exc:
        logger.error("Server error: %s", exc, exc_info=True)
        return 1

    logger.info("Backend shut down cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

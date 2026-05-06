#!/usr/bin/env python3
"""GenericAgent — Sidecar Backend Launcher

This is the entry point for the Tauri sidecar backend process.
When bundled with PyInstaller, it becomes the standalone executable
that the Tauri desktop app launches as a child process.

Responsibilities:
  1. Locate the GenericAgent backend directory
  2. Add it to sys.path so server.py and its modules can be imported
  3. Import and start the FastAPI server on port 8765
  4. Handle SIGINT/SIGTERM for graceful shutdown
  5. Log all startup status to stderr (captured by Tauri shell plugin)

Environment Variables:
  GA_BACKEND_DIR   — Override the backend directory path
  GA_HOST          — Bind address (default: 127.0.0.1)
  GA_PORT          — Port number (default: 8765)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

# ─── Version ─────────────────────────────────────────────────────
_VERSION = "v1.2.0"

# ─── Logging Setup ─────────────────────────────────────────────────────
# All output goes to stderr so Tauri's CommandEvent::Stderr captures it.
# stdout is reserved for any future JSON protocol between sidecar & Tauri.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("launch_backend")


def _find_backend_dir() -> Path:
    """Locate the GenericAgent backend directory.

    Search order:
      1. GA_BACKEND_DIR environment variable (explicit override)
      2. Adjacent to the executable (bundled with PyInstaller)
      3. Relative to this script (development mode)
      4. Common install locations

    Returns:
        Path to the backend directory.

    Raises:
        FileNotFoundError: If the backend directory cannot be located.
    """
    # 1. Explicit override
    env_dir = os.environ.get("GA_BACKEND_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir() and (p / "server.py").exists():
            logger.info("Using GA_BACKEND_DIR=%s", p)
            return p
        logger.warning("GA_BACKEND_DIR=%s does not contain server.py, ignoring", p)

    # 2. Bundled mode — PyInstaller sets sys._MEIPASS to the temp extraction dir
    is_bundled = getattr(sys, "frozen", False)
    if is_bundled:
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        # The backend files are collected into the bundle root
        if (base / "server.py").exists():
            logger.info("Using bundled backend at %s", base)
            return base
        # Check for a sub-directory (if --add-data was used)
        for candidate in [
            base / f"GenericAgent-{_VERSION}",
            base / "backend",
            base / "app",
        ]:
            if candidate.is_dir() and (candidate / "server.py").exists():
                logger.info("Using bundled backend at %s", candidate)
                return candidate

    # 3. Development mode — relative to this script
    script_dir = Path(__file__).resolve().parent
    for candidate in [
        script_dir / ".." / ".." / "upload" / f"GenericAgent-{_VERSION}",
        script_dir / f"GenericAgent-{_VERSION}",
        script_dir,
    ]:
        candidate = candidate.resolve()
        if candidate.is_dir() and (candidate / "server.py").exists():
            logger.info("Using development backend at %s", candidate)
            return candidate

    # 4. Common install locations
    home = Path.home()
    for candidate in [
        home / "GenericAgent" / f"GenericAgent-{_VERSION}",
        Path(f"/opt/GenericAgent/GenericAgent-{_VERSION}"),
        Path(f"C:/GenericAgent/GenericAgent-{_VERSION}"),
    ]:
        if candidate.is_dir() and (candidate / "server.py").exists():
            logger.info("Using installed backend at %s", candidate)
            return candidate

    raise FileNotFoundError(
        f"Cannot locate GenericAgent-{_VERSION} backend directory. "
        "Set GA_BACKEND_DIR to the directory containing server.py."
    )


def _setup_ssl() -> None:
    """Configure SSL certificate paths for the bundled application."""
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        logger.debug("certifi not available, using system SSL certificates")


_server_instance = None


def _signal_handler(sig: int, frame: object) -> None:
    """Signal handler that triggers graceful uvicorn shutdown."""
    global _server_instance
    sig_name = signal.Signals(sig).name
    logger.info("Received %s, initiating graceful shutdown...", sig_name)
    if _server_instance is not None:
        _server_instance.should_exit = True


def _setup_signal_handlers() -> None:
    """Register SIGINT/SIGTERM handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # On Windows, SIGTERM is not available; also handle CTRL_BREAK_EVENT
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, _signal_handler)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass


def main() -> int:
    """Main entry point for the sidecar backend launcher.

    Returns:
        Exit code: 0 for clean shutdown, 1 for error.
    """
    logger.info("=" * 60)
    logger.info("GenericAgent Sidecar Backend Launcher")
    logger.info("=" * 60)
    logger.info("Python %s on %s", sys.version, sys.platform)
    logger.info("Executable: %s", sys.executable)

    is_bundled = getattr(sys, "frozen", False)
    if is_bundled:
        logger.info("Running as bundled PyInstaller executable")
    else:
        logger.info("Running in development mode")

    # ── SSL setup ──────────────────────────────────────────────────
    _setup_ssl()

    # ── Locate backend directory ───────────────────────────────────
    try:
        backend_dir = _find_backend_dir()
    except FileNotFoundError as exc:
        logger.error("FATAL: %s", exc)
        return 1

    # ── Add to sys.path ────────────────────────────────────────────
    backend_dir_str = str(backend_dir)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)
        logger.info("Added to sys.path: %s", backend_dir_str)

    # Also add the parent so `import agentmain` works
    parent_dir = str(backend_dir.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        logger.info("Added to sys.path: %s", parent_dir)

    # ── Set working directory ──────────────────────────────────────
    os.chdir(backend_dir)
    logger.info("Working directory: %s", backend_dir)

    # ── Import and verify server module ────────────────────────────
    try:
        import server as server_module
        logger.info("Imported server module successfully")
    except ImportError as exc:
        logger.error("FATAL: Failed to import server module: %s", exc)
        logger.error("sys.path entries:")
        for p in sys.path:
            logger.error("  - %s", p)
        return 1

    # ── Check FastAPI availability ─────────────────────────────────
    if hasattr(server_module, 'is_available') and not server_module.is_available():
        logger.error(
            "FATAL: FastAPI is not available. "
            "Ensure fastapi and uvicorn are installed."
        )
        return 1

    logger.info("FastAPI is available")

    # ── Configuration from environment ─────────────────────────────
    host = os.environ.get("GA_HOST", "127.0.0.1")

    def _safe_int(val, default):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    port = _safe_int(os.environ.get("GA_PORT", "8765"), 8765)
    logger.info("Server will bind to %s:%d", host, port)

    # ── Signal handling ────────────────────────────────────────────
    _setup_signal_handlers()

    # ── Start the server ───────────────────────────────────────────
    logger.info("Starting GenericAgent FastAPI server...")
    try:
        import uvicorn
        app = server_module.create_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        global _server_instance
        _server_instance = uvicorn.Server(config)
        _server_instance.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by KeyboardInterrupt")
    except Exception as exc:
        logger.error("Server exited with error: %s", exc, exc_info=True)
        return 1

    logger.info("GenericAgent backend shut down cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

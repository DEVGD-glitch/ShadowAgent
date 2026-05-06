"""plugins/tools/system_tools.py — System information and OS integration tools.

Provides tools for system information, clipboard access, and OS-level
operations that augment the agent's capabilities.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger("plugins.tools.system_tools")


def do_system_info(args: dict, response: Any) -> dict[str, Any]:
    """Get system information about the current environment.

    Returns OS details, Python version, hardware info, and environment
    variables that are useful for the agent's operations.

    Args (from LLM):
        section: Optional section to query ("os", "python", "hardware", "env", "all").

    Returns:
        dict with system information.
    """
    section = args.get("section", "all")

    info: dict[str, Any] = {}

    if section in ("os", "all"):
        info["os"] = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "cwd": os.getcwd(),
        }

    if section in ("python", "all"):
        info["python"] = {
            "version": sys.version,
            "executable": sys.executable,
            "path": sys.path[:5],  # First 5 entries
        }

    if section in ("hardware", "all"):
        try:
            import psutil
            info["hardware"] = {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
                "disk_total_gb": round(psutil.disk_usage("/").total / (1024**3), 1),
                "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
            }
        except ImportError:
            info["hardware"] = {"cpu_count": os.cpu_count(), "note": "psutil not installed, limited info"}

    if section in ("env", "all"):
        # Only show GA_ prefixed env vars for safety
        ga_vars = {k: v for k, v in os.environ.items() if k.startswith("GA_")}
        info["environment"] = ga_vars

    info["timestamp"] = datetime.now().isoformat()

    return {"status": "success", "info": info}


def do_directory_tree(args: dict, response: Any) -> dict[str, Any]:
    """Get a directory tree structure for exploring the filesystem.

    Returns a formatted tree view of the specified directory, useful
    for understanding project structure before making changes.

    Args (from LLM):
        path: Directory path to scan.
        depth: Maximum depth (1-5, default 2).
        include_files: Whether to include files (default True).

    Returns:
        dict with formatted tree string.
    """
    path = args.get("path", ".")
    max_depth = min(max(args.get("depth", 2), 1), 5)
    include_files = args.get("include_files", True)

    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {"status": "error", "msg": f"Directory not found: {path}"}

    # Skip patterns for common noise directories
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
    skip_ext = {".pyc", ".pyo", ".so", ".dll", ".exe"}

    lines: list[str] = []

    def _walk(dir_path: str, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
            return

        dirs = []
        files = []
        for entry in entries:
            if entry.startswith(".") and entry not in (".env",):
                continue
            full = os.path.join(dir_path, entry)
            if os.path.isdir(full):
                if entry not in skip_dirs:
                    dirs.append(entry)
            elif include_files:
                if not any(entry.endswith(ext) for ext in skip_ext):
                    files.append(entry)

        for i, d in enumerate(dirs):
            is_last = (i == len(dirs) - 1) and not files
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{d}/")
            extension = "    " if is_last else "│   "
            _walk(os.path.join(dir_path, d), prefix + extension, depth + 1)

        if include_files:
            for i, f in enumerate(files):
                is_last = i == len(files) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{f}")

    lines.append(os.path.basename(path) + "/")
    _walk(path, "", 1)

    tree = "\n".join(lines)

    # Limit output size
    if len(tree) > 5000:
        tree = tree[:5000] + "\n... [truncated]"

    return {"status": "success", "path": path, "tree": tree}


def do_list_processes(args: dict, response: Any) -> dict[str, Any]:
    """List running processes on the system.

    Returns information about running processes, useful for debugging
    and system monitoring.

    Args (from LLM):
        filter_name: Optional name filter (case-insensitive).
        top_n: Number of processes to return (1-50, default 10).

    Returns:
        dict with process list.
    """
    filter_name = args.get("filter_name", "").lower()
    top_n = min(max(args.get("top_n", 10), 1), 50)

    try:
        import psutil

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                name = info.get("name", "")
                if filter_name and filter_name not in name.lower():
                    continue
                processes.append({
                    "pid": info["pid"],
                    "name": name,
                    "cpu_percent": info.get("cpu_percent", 0),
                    "memory_mb": round(info["memory_info"].rss / (1024 * 1024), 1) if info.get("memory_info") else 0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by memory usage
        processes.sort(key=lambda p: p["memory_mb"], reverse=True)
        processes = processes[:top_n]

        return {"status": "success", "count": len(processes), "processes": processes}

    except ImportError:
        return {"status": "error", "msg": "psutil not installed. Run: pip install psutil"}


# ── Register tools ────────────────────────────────────────────────────────

try:
    from tools import register_tool

    register_tool(
        name="system_info",
        handler=do_system_info,
        description=(
            "Get system information about the current environment (OS, Python, "
            "hardware, environment variables). Useful for debugging and understanding "
            "the execution context."
        ),
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Section to query: os, python, hardware, env, all.",
                    "default": "all",
                    "enum": ["os", "python", "hardware", "env", "all"],
                },
            },
        },
        category="system",
        source="plugin",
    )

    register_tool(
        name="directory_tree",
        handler=do_directory_tree,
        description=(
            "Get a directory tree structure for exploring the filesystem. "
            "Shows the organization of files and folders, useful for understanding "
            "project structure before making changes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to scan.",
                    "default": ".",
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth (1-5).",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 5,
                },
                "include_files": {
                    "type": "boolean",
                    "description": "Whether to include files in the tree.",
                    "default": True,
                },
            },
        },
        category="system",
        source="plugin",
    )

    register_tool(
        name="list_processes",
        handler=do_list_processes,
        description=(
            "List running processes on the system. Useful for debugging, "
            "monitoring, and finding conflicting processes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "filter_name": {
                    "type": "string",
                    "description": "Optional name filter (case-insensitive).",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of processes to return (1-50).",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        },
        category="system",
        source="plugin",
    )

except ImportError:
    logger.debug("Tool registry not available, system tools not registered")

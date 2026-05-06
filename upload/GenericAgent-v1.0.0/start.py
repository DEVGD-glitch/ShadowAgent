#!/usr/bin/env python3
"""Shadow Agent — Cross-platform launcher.

Replaces the Windows-only start.bat with a Python script that works on
Windows, macOS, and Linux.

Usage:
    python start.py          # Interactive menu
    python start.py --gui    # Launch GUI directly
    python start.py --cli    # Launch CLI directly
    python start.py --config # Launch configuration
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
VENV_DIR = BASE_DIR / ".venv"


def get_python_path() -> str:
    """Get the Python executable path from the virtual environment."""
    if platform.system() == "Windows":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def get_pip_path() -> str:
    """Get the pip executable path from the virtual environment."""
    if platform.system() == "Windows":
        return str(VENV_DIR / "Scripts" / "pip.exe")
    return str(VENV_DIR / "bin" / "pip")


def venv_exists() -> bool:
    """Check if the virtual environment exists."""
    return VENV_DIR.is_dir() and Path(get_python_path()).is_file()


def mykey_exists() -> bool:
    """Check if mykey.py or mykey.json exists."""
    return (BASE_DIR / "mykey.py").is_file() or (BASE_DIR / "mykey.json").is_file()


def activate_venv() -> None:
    """Activate the virtual environment by updating sys.path and PATH."""
    if not venv_exists():
        print("  [!] Virtual environment not found.")
        print("  Please run setup first (setup_windows.bat or python start.py --setup)")
        sys.exit(1)

    # Add venv site-packages to sys.path
    python_path = get_python_path()
    os.environ["VIRTUAL_ENV"] = str(VENV_DIR)
    # Add venv's bin/Scripts dir to PATH
    venv_bin = str(VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin"))
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")


def run_command(cmd: list[str], **kwargs) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), **kwargs)
        return result.returncode
    except FileNotFoundError:
        print(f"  [!] Command not found: {cmd[0]}")
        return 1
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return 130


def launch_gui() -> None:
    """Launch the graphical interface."""
    print("\n  Launching graphical interface...\n")
    python = get_python_path()
    ret = run_command([python, "launch.pyw"])
    if ret != 0:
        print()
        print("  [!] Error launching graphical interface.")
        print("  Try command-line mode instead (choice 2).")


def launch_cli() -> None:
    """Launch the command-line interface."""
    print("\n  Launching command-line interface...")
    print("  Type your question and press Enter.")
    print("  Type /quit to quit.\n")
    python = get_python_path()
    run_command([python, "-m", "agentmain"])


def launch_config() -> None:
    """Launch the configuration wizard."""
    print("\n  Launching interactive configuration...\n")
    python = get_python_path()
    run_command([python, "configure.py"])


def reinstall_deps() -> None:
    """Reinstall dependencies."""
    print("\n  Reinstalling dependencies...\n")
    pip = get_pip_path()
    packages = [
        "requests", "beautifulsoup4", "websockets", "markdown2",
        "PySide6", "bottle", "lxml",
    ]
    run_command([pip, "install"] + packages + ["--quiet"])
    print("\n  [OK] Dependencies reinstalled")


def interactive_menu() -> None:
    """Display the interactive menu and handle user choice."""
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║              Shadow Agent - Launcher                      ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    # Check prerequisites
    if not venv_exists():
        print("  [!] Virtual environment not found.")
        print("  Please run setup first.")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    if not mykey_exists():
        print("  [!] mykey.py / mykey.json not found.")
        print("  Please run setup first.")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    # Activate venv
    activate_venv()

    print("  What would you like to do?")
    print()
    print("    1) Graphical interface (recommended)")
    print("    2) Command line")
    print("    3) Configure API keys")
    print("    4) Reinstall dependencies")
    print("    5) Quit")
    print()

    try:
        choice = input("  Your choice (1-5): ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)

    if choice == "1":
        launch_gui()
    elif choice == "2":
        launch_cli()
    elif choice == "3":
        launch_config()
    elif choice == "4":
        reinstall_deps()
    elif choice == "5":
        sys.exit(0)
    else:
        print("  Invalid choice.")
        sys.exit(1)


def main() -> None:
    """Entry point for the cross-platform launcher."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().lstrip("-")
        if arg in ("gui", "g"):
            if not venv_exists():
                sys.exit(1)
            activate_venv()
            launch_gui()
        elif arg in ("cli", "c"):
            if not venv_exists():
                sys.exit(1)
            activate_venv()
            launch_cli()
        elif arg in ("config", "configure"):
            if not venv_exists():
                sys.exit(1)
            activate_venv()
            launch_config()
        elif arg in ("setup", "install"):
            python = sys.executable
            run_command([python, "-m", "venv", str(VENV_DIR)])
            activate_venv()
            pip = get_pip_path()
            run_command([pip, "install", "-r", str(BASE_DIR / "requirements.txt")])
            launch_config()
        elif arg in ("help", "h"):
            print(__doc__)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage: python start.py [--gui|--cli|--config|--setup|--help]")
            sys.exit(1)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()

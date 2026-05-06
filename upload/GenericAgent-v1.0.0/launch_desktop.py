"""
GenericAgent — Windows Desktop Launcher

This is the entry point for the bundled Windows desktop application.
It handles:
  - Python environment setup (bundled or system)
  - First-run setup wizard
  - Qt UI launch
  - System tray integration
  - Auto-update checks

When bundled with PyInstaller, this runs as GenericAgent.exe
When in development, it runs as: python launch_desktop.py
"""
import os
import sys
import traceback
from pathlib import Path


def setup_environment():
    """Configure environment for the application."""
    is_bundled = getattr(sys, 'frozen', False)

    if is_bundled:
        # Running as bundled PyInstaller app
        base_path = Path(sys._MEIPASS)
        os.environ['GENERICAGENT_BUNDLED'] = '1'
        os.environ['GENERICAGENT_BASE_PATH'] = str(base_path)
    else:
        # Running in development
        base_path = Path(__file__).parent

    # Set up user data directories
    home = Path.home()
    for subdir in ['workspace', 'config', 'data', 'memory']:
        d = home / 'GenericAgent' / subdir
        d.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault('AGENT_WORKSPACE_DIR', str(home / 'GenericAgent' / 'workspace'))
    os.environ.setdefault('GENERICAGENT_CONFIG_DIR', str(home / 'GenericAgent' / 'config'))
    os.environ.setdefault('GENERICAGENT_DATA_DIR', str(home / 'GenericAgent' / 'data'))

    # SSL certificates
    try:
        import certifi
        os.environ.setdefault('SSL_CERT_FILE', certifi.where())
        os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
    except ImportError:
        pass

    return base_path


def check_first_run():
    """Check if this is the first run and set up config if needed."""
    config_dir = Path(os.environ.get('GENERICAGENT_CONFIG_DIR', Path.home() / 'GenericAgent' / 'config'))
    first_run_marker = config_dir / '.initialized'

    if first_run_marker.exists():
        return False

    # First run — create mykey.py from template if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    base_path = Path(os.environ.get('GENERICAGENT_BASE_PATH', Path(__file__).parent))

    mykey_dest = config_dir / 'mykey.py'
    if not mykey_dest.exists():
        # Try templates in order
        for template_name in ['mykey_template_fr.py', 'mykey_template_en.py', 'mykey_template.py']:
            template = base_path / template_name
            if template.exists():
                import shutil
                shutil.copy2(template, mykey_dest)
                break

    first_run_marker.write_text('1')
    return True


def launch_qt_app():
    """Launch the Qt desktop application."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt, QSharedMemory
    except ImportError:
        print("ERROR: PySide6 is not installed. Install it with: pip install PySide6")
        print("Falling back to CLI mode...")
        launch_cli_app()
        return

    # Prevent multiple instances
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("GenericAgent")
    app.setOrganizationName("GenericAgent")
    app.setDesktopFileName("genericagent")

    # Single instance check using QSharedMemory
    shared_memory = QSharedMemory("GenericAgentSingleton")
    if not shared_memory.create(1):
        QMessageBox.information(
            None,
            "GenericAgent",
            "Another instance of GenericAgent is already running.\n"
            "Check your system tray or task manager."
        )
        sys.exit(0)

    try:
        # Import and launch the Qt app
        # We import here so the splash screen shows quickly
        from frontends.qtapp import GenericAgentWindow

        window = GenericAgentWindow()
        window.show()

        # Check for updates in background (non-blocking)
        try:
            from agentmain.auto_update import check_and_notify_async
            def on_update(info):
                if info:
                    window.show_update_notification(info)
            check_and_notify_async(on_update)
        except Exception:
            pass  # Update check is non-critical

        sys.exit(app.exec())

    except Exception as e:
        QMessageBox.critical(
            None,
            "GenericAgent — Error",
            f"Failed to start GenericAgent:\n\n{traceback.format_exc()}"
        )
        sys.exit(1)


def launch_cli_app():
    """Launch the CLI version as fallback."""
    from agentmain import main_cli
    main_cli()


def main():
    """Main entry point."""
    setup_environment()

    is_first_run = check_first_run()

    # Try Qt first, fall back to CLI
    try:
        launch_qt_app()
    except ImportError:
        print("Qt not available, starting in CLI mode...")
        launch_cli_app()
    except Exception as e:
        print(f"Qt launch failed: {e}")
        print("Starting in CLI mode...")
        launch_cli_app()


if __name__ == '__main__':
    main()

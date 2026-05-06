"""
GenericAgent — Auto-Update System

Checks for new versions on GitHub and provides one-click updates.
Works both in bundled (PyInstaller) and development mode.

Inspired by ClawX's electron-updater approach, but adapted for
Python/PyInstaller desktop apps.
"""
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Callable, Optional

# SecurityError import with fallback
try:
    from agentmain.safe_eval import SecurityError
except ImportError:
    class SecurityError(Exception):
        """Fallback SecurityError when safe_eval module is not available."""
        pass

logger = logging.getLogger("agentmain.auto_update")

# ═══════════════════════════════════════════════════════════════════════════
#  Update Verification — Security Functions
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
#  Keypair Generation & Configuration
# ═══════════════════════════════════════════════════════════════════════════
#
#  Auto-update signature verification uses Ed25519 (RFC 8032).  Before
#  auto-update can work, you must generate a keypair and configure the
#  public key:
#
#    1. Generate the keypair:
#         python -c "from agentmain.auto_update import generate_keypair; generate_keypair()"
#       This creates  ga_update_private.key  and  ga_update_public.key  in the
#       project root.  KEEP THE PRIVATE KEY SECURE — anyone who obtains it can
#       sign malicious updates.
#
#    2. Set the public key in this file (or via environment variable
#       GA_UPDATE_PUBLIC_KEY_HEX):
#         _UPDATE_PUBLIC_KEY = bytes.fromhex("<contents of ga_update_public.key>")
#
#    3. Sign each release artifact:
#         python -c "
#           from agentmain.auto_update import sign_file
#           sign_file('dist/update.zip', 'ga_update_private.key')"
#
#  The verification function ``_verify_signature`` will reject any update
#  when no public key is configured — this is the safe default.
# ═══════════════════════════════════════════════════════════════════════════

# Public key for update verification - must be replaced with actual key
_UPDATE_PUBLIC_KEY: Optional[bytes] = os.environ.get(
    "GA_UPDATE_PUBLIC_KEY_HEX", None
)
if _UPDATE_PUBLIC_KEY is not None:
    try:
        _UPDATE_PUBLIC_KEY = bytes.fromhex(_UPDATE_PUBLIC_KEY)
    except (ValueError, TypeError):
        logger.error("GA_UPDATE_PUBLIC_KEY_HEX is not valid hex — ignoring")
        _UPDATE_PUBLIC_KEY = None


def _verify_signature(file_path: str, signature_path: str) -> bool:
    """Verify Ed25519 signature of update file.

    When _UPDATE_PUBLIC_KEY is None (the default), signature verification
    is mandatory but impossible — the update is **rejected** as a safe default.
    Operators must generate a keypair (see :func:`generate_keypair`) and set
    ``_UPDATE_PUBLIC_KEY`` before auto-update will accept any package.
    """
    if _UPDATE_PUBLIC_KEY is None:
        logger.error(
            "SECURITY: Update rejected - no public key configured for signature verification. "
            "Generate a keypair with generate_keypair() and set _UPDATE_PUBLIC_KEY."
        )
        return False

    if not os.path.exists(signature_path):
        logger.warning(f"No signature file found at {signature_path}")
        return False

    try:
        from cryptography.hazmat.primitives import serialization, signatures
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        # Full implementation with cryptography library
        public_key = Ed25519PublicKey.from_public_bytes(_UPDATE_PUBLIC_KEY)
        with open(signature_path, 'rb') as f:
            signature = f.read()
        with open(file_path, 'rb') as f:
            data = f.read()
        public_key.verify(signature, data)
        return True
    except ImportError:
        logger.error(
            "SECURITY: Update rejected - cryptography library not installed. "
            "Install with: pip install cryptography"
        )
        return False
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def _verify_checksum(file_path: str, expected_sha256: str) -> bool:
    """Verify file integrity using SHA-256."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest() == expected_sha256


def generate_keypair(output_dir: Optional[str] = None) -> tuple[str, str]:
    """Generate an Ed25519 keypair for update signing and verification.

    Creates two files:
      - ``ga_update_private.key`` — the private signing key (hex-encoded)
      - ``ga_update_public.key``  — the public verification key (hex-encoded)

    **IMPORTANT**: The private key must be kept secret.  Anyone who obtains
    it can sign malicious updates that will be accepted by all installations
    configured with the corresponding public key.

    Args
    ----
    output_dir : str | None
        Directory to write the key files.  Defaults to the project root.

    Returns
    -------
    tuple[str, str]
        ``(private_key_path, public_key_path)`` — paths to the generated files.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    if output_dir is None:
        output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    priv_path = os.path.join(output_dir, "ga_update_private.key")
    pub_path = os.path.join(output_dir, "ga_update_public.key")

    # Write raw bytes as hex for easy embedding
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    with open(priv_path, "w") as f:
        f.write(private_bytes.hex())
    os.chmod(priv_path, 0o600)  # Owner read/write only

    with open(pub_path, "w") as f:
        f.write(public_bytes.hex())

    logger.info("Ed25519 keypair generated: private=%s, public=%s", priv_path, pub_path)
    return (priv_path, pub_path)


def sign_file(file_path: str, private_key_path: str, output_path: Optional[str] = None) -> str:
    """Sign a file using the Ed25519 private key.

    Args
    ----
    file_path : str
        Path to the file to sign.
    private_key_path : str
        Path to the hex-encoded private key file.
    output_path : str | None
        Path to write the signature.  Defaults to ``file_path + ".sig"``.

    Returns
    -------
    str
        Path to the signature file.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    with open(private_key_path, "r") as f:
        private_bytes = bytes.fromhex(f.read().strip())
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)

    with open(file_path, "rb") as f:
        data = f.read()

    signature = private_key.sign(data)

    if output_path is None:
        output_path = file_path + ".sig"
    with open(output_path, "wb") as f:
        f.write(signature)

    logger.info("Signed %s → %s", file_path, output_path)
    return output_path


def _safe_extract_zip(zip_path: str, target_dir: str) -> None:
    """Extract zip safely, preventing zip slip path traversal attacks."""
    target_dir = os.path.realpath(target_dir)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            member_path = os.path.realpath(os.path.join(target_dir, member.filename))
            if not member_path.startswith(target_dir + os.sep) and member_path != target_dir:
                raise SecurityError(
                    f"Zip slip detected: '{member.filename}' attempts to write "
                    f"outside of {target_dir}"
                )
            zf.extract(member, target_dir)


# ═══════════════════════════════════════════════════════════════════════════
#  GitHub Release API
# ═══════════════════════════════════════════════════════════════════════════

GITHUB_REPO = "genericagent/genericagent"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_DOWNLOAD = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Local state
UPDATE_DIR = Path.home() / "GenericAgent" / "updates"
STATE_FILE = UPDATE_DIR / "update_state.json"


def get_current_version() -> str:
    """Get the current application version."""
    try:
        # Try importing from the package
        from importlib.metadata import version
        return version("genericagent")
    except Exception:
        logger.debug("get_current_version: failed to get version from importlib.metadata")
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith("version ="):
                return line.split("=")[1].strip().strip("\"'")
    except Exception:
        logger.debug("get_current_version: failed to read version from pyproject.toml")

    return "0.0.0"


def is_bundled() -> bool:
    """Check if running as a bundled PyInstaller app."""
    return getattr(sys, "frozen", False)


def get_install_dir() -> Path:
    """Get the installation directory."""
    if is_bundled():
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def check_for_update(timeout: float = 10.0) -> Optional[dict]:
    """
    Check GitHub for a new version.

    Returns:
        dict with release info if update available, None if up-to-date.
        {
            "version": "0.5.1",
            "download_url": "https://...",
            "changelog": "...",
            "size": 123456789,
        }
    """
    import requests

    current = get_current_version()
    try:
        resp = requests.get(
            GITHUB_API,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        release = resp.json()
    except Exception as e:
        logger.error("Check failed: %s", e)
        return None

    latest_tag = release.get("tag_name", "").lstrip("v")
    if not latest_tag:
        return None

    # Compare versions (simple semver comparison)
    if _compare_versions(latest_tag, current) <= 0:
        return None  # Already up-to-date

    # Find the right asset for this platform
    assets = release.get("assets", [])
    download_url = None
    asset_size = 0

    # Determine the expected asset name
    system = platform.system().lower()
    arch = "x64" if platform.machine().endswith("64") else "x86"

    for asset in assets:
        name = asset.get("name", "").lower()
        if system == "windows" and ("setup" in name or "installer" in name):
            if arch in name or name.endswith(".exe"):
                download_url = asset.get("browser_download_url")
                asset_size = asset.get("size", 0)
                break
        elif system == "darwin" and (".dmg" in name or "macos" in name):
            download_url = asset.get("browser_download_url")
            asset_size = asset.get("size", 0)
            break
        elif system == "linux" and (".appimage" in name or "linux" in name):
            download_url = asset.get("browser_download_url")
            asset_size = asset.get("size", 0)
            break

    # Fallback to main download page if no direct asset found
    if not download_url:
        download_url = release.get("html_url", GITHUB_DOWNLOAD)

    return {
        "version": latest_tag,
        "download_url": download_url,
        "changelog": release.get("body", ""),
        "size": asset_size,
        "current_version": current,
    }


def download_update(
    update_info: dict,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Optional[Path]:
    """
    Download the update file.

    Args:
        update_info: Dict from check_for_update()
        progress_callback: Called with download progress (0.0 to 1.0)

    Returns:
        Path to the downloaded file, or None on failure.
    """
    import requests

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    url = update_info["download_url"]
    filename = url.split("/")[-1]
    dest = UPDATE_DIR / filename

    if dest.exists():
        # Already downloaded
        if progress_callback:
            progress_callback(1.0)
        return dest

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and progress_callback:
                        progress_callback(downloaded / total)

        # ── SHA-256 checksum verification (Task 0.3.3) ──
        sha256_url = url + ".sha256"
        sha256_dest = Path(str(dest) + ".sha256")
        try:
            sha256_resp = requests.get(sha256_url, timeout=10)
            sha256_resp.raise_for_status()
            expected_hash = sha256_resp.text.strip().split()[0]  # format: "<hash>  <filename>"
            if not _verify_checksum(str(dest), expected_hash):
                logger.error(
                    f"SHA-256 checksum mismatch for {dest}. "
                    f"Expected: {expected_hash}"
                )
                dest.unlink()
                if sha256_dest.exists():
                    sha256_dest.unlink()
                return None
            logger.info("SHA-256 checksum verified successfully")
            # Save .sha256 file for record
            sha256_dest.write_text(sha256_resp.text)
        except Exception as e:
            # No .sha256 file available — log warning and continue (backwards compat)
            logger.warning(
                f"No SHA-256 checksum file available at {sha256_url}: {e}. "
                f"Proceeding without integrity verification."
            )

        # ── Download .sig file for signature verification (Task 0.3.1) ──
        sig_url = url + ".sig"
        sig_dest = Path(str(dest) + ".sig")
        try:
            sig_resp = requests.get(sig_url, timeout=10)
            sig_resp.raise_for_status()
            sig_dest.write_bytes(sig_resp.content)
            logger.info("Downloaded signature file for update")
        except Exception:
            # No .sig file available — will be handled during verification
            logger.debug(f"No signature file available at {sig_url}")

        return dest
    except Exception as e:
        logger.error(f"Download failed: {e}")
        if dest.exists():
            dest.unlink()
        return None


def apply_update(downloaded_file: Path) -> bool:
    """
    Apply the downloaded update.

    For Windows: Launch the installer and exit the current app.
    For portable: Extract and replace files.
    """
    system = platform.system().lower()

    # ── Signature verification before applying update (Task 0.3.1) ──
    sig_path = Path(str(downloaded_file) + ".sig")
    if not _verify_signature(str(downloaded_file), str(sig_path)):
        logger.error(
            f"Update signature verification failed for {downloaded_file}. "
            f"Aborting update for security reasons."
        )
        return False

    if system == "windows":
        # Windows: Launch the installer and exit
        if downloaded_file.suffix.lower() == ".exe":
            try:
                subprocess.Popen(
                    [str(downloaded_file), "/SILENT", "--update"],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                )
                # Give the installer a moment to start
                import time
                time.sleep(2)
                # Exit the current app so the installer can overwrite files
                sys.exit(0)
            except Exception as e:
                logger.error("Failed to launch installer: %s", e)
                return False
        else:
            # ZIP archive: extract and replace
            return _apply_portable_update(downloaded_file)

    elif system == "darwin":
        # macOS: Open the DMG
        try:
            subprocess.Popen(["open", str(downloaded_file)])
            sys.exit(0)
        except Exception as e:
            logger.error("Failed to open DMG: %s", e)
            return False

    elif system == "linux":
        # Linux: AppImage — replace the current AppImage
        try:
            current_exe = Path(sys.executable)
            shutil.move(str(downloaded_file), str(current_exe))
            os.chmod(str(current_exe), 0o755)
            # Restart
            os.execv(str(current_exe), [str(current_exe)] + sys.argv[1:])
        except Exception as e:
            logger.error("Failed to apply update: %s", e)
            return False

    return False


def _apply_portable_update(zip_file: Path) -> bool:
    """Apply an update from a ZIP archive (portable distribution)."""
    install_dir = get_install_dir()
    backup_dir = install_dir.parent / f"{install_dir.name}.backup"

    try:
        # Backup current installation
        if install_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.move(str(install_dir), str(backup_dir))

        # Extract new version — using safe extraction to prevent zip slip
        _safe_extract_zip(str(zip_file), str(install_dir.parent))

        # Remove backup
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        # Restart — find the correct executable for the current platform
        system = platform.system().lower()
        if system == "windows":
            new_exe = install_dir / "GenericAgent.exe"
        elif system == "darwin":
            new_exe = install_dir / "GenericAgent.app" / "Contents" / "MacOS" / "GenericAgent"
            if not new_exe.exists():
                new_exe = install_dir / "GenericAgent"
        else:
            new_exe = install_dir / "GenericAgent"
        if new_exe.exists():
            subprocess.Popen([str(new_exe)])
            sys.exit(0)

        return True
    except Exception as e:
        logger.error("Portable update failed: %s", e)
        # Restore backup
        if backup_dir.exists() and not install_dir.exists():
            shutil.move(str(backup_dir), str(install_dir))
        return False


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two semver version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    def parse(v):
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return parts

    p1, p2 = parse(v1), parse(v2)
    for a, b in zip(p1, p2):
        if a > b:
            return 1
        if a < b:
            return -1
    if len(p1) > len(p2):
        return 1
    if len(p1) < len(p2):
        return -1
    return 0


def save_update_state(state: dict):
    """Save update state to disk."""
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_update_state() -> dict:
    """Load update state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            logger.debug("Failed to read update state file", exc_info=True)
    return {}


def check_and_notify_async(
    callback: Optional[Callable[[Optional[dict]], None]] = None,
):
    """
    Check for updates in a background thread.

    Args:
        callback: Called with update info when check completes.
                  None means no update available or check failed.
    """
    def _check():
        result = check_for_update()
        if callback:
            callback(result)

    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


# ═══════════════════════════════════════════════════════════════════════════
#  Qt Integration (for the desktop app)
# ═══════════════════════════════════════════════════════════════════════════

def create_update_dialog(parent=None):
    """
    Create a Qt dialog for checking and applying updates.
    Returns a QWidget that can be shown in the settings page.
    """
    try:
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QLabel, QPushButton,
            QProgressBar, QHBoxLayout, QTextEdit,
        )
        from PySide6.QtCore import Qt, QTimer, Signal, QObject
    except ImportError:
        return None

    class UpdateSignaler(QObject):
        update_found = Signal(dict)
        update_progress = Signal(float)
        update_error = Signal(str)
        check_complete = Signal()

    signaler = UpdateSignaler()

    widget = QWidget()
    layout = QVBoxLayout(widget)

    # Version label
    current_ver = get_current_version()
    ver_label = QLabel(f"Current version: {current_ver}")
    ver_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(ver_label)

    # Status label
    status = QLabel("Checking for updates...")
    layout.addWidget(status)

    # Progress bar (hidden initially)
    progress = QProgressBar()
    progress.setVisible(False)
    layout.addWidget(progress)

    # Changelog (hidden initially)
    changelog = QTextEdit()
    changelog.setReadOnly(True)
    changelog.setMaximumHeight(150)
    changelog.setVisible(False)
    changelog.setPlaceholderText("Changelog will appear here when an update is found.")
    layout.addWidget(changelog)

    # Buttons
    btn_layout = QHBoxLayout()
    check_btn = QPushButton("Check for Updates")
    update_btn = QPushButton("Download & Install Update")
    update_btn.setVisible(False)
    update_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px;")
    btn_layout.addWidget(check_btn)
    btn_layout.addWidget(update_btn)
    btn_layout.addStretch()
    layout.addLayout(btn_layout)

    # State
    update_info = [None]  # Use list for mutation in closures

    def on_check():
        status.setText("Checking for updates...")
        check_btn.setEnabled(False)

        def on_result(info):
            signaler.update_found.emit(info) if info else signaler.check_complete.emit()

        check_and_notify_async(on_result)

    def on_update_found(info):
        update_info[0] = info
        status.setText(f"Update available: v{info['version']} (current: v{info['current_version']})")
        status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        update_btn.setVisible(True)

        if info.get("changelog"):
            changelog.setVisible(True)
            changelog.setMarkdown(info["changelog"])

        check_btn.setEnabled(True)

    def on_check_complete():
        status.setText("You are running the latest version.")
        status.setStyleSheet("color: #2196F3;")
        check_btn.setEnabled(True)

    def on_download():
        if not update_info[0]:
            return

        update_btn.setEnabled(False)
        status.setText("Downloading update...")
        progress.setVisible(True)
        progress.setValue(0)

        def on_progress(p):
            signaler.update_progress.emit(p)

        def download_thread():
            path = download_update(update_info[0], on_progress)
            if path:
                signaler.update_progress.emit(1.0)
                # Apply after a brief delay
                import time
                time.sleep(1)
                apply_update(path)
            else:
                signaler.update_error.emit("Download failed")

        threading.Thread(target=download_thread, daemon=True).start()

    def on_progress(p):
        progress.setValue(int(p * 100))

    def on_error(msg):
        status.setText(f"Update failed: {msg}")
        status.setStyleSheet("color: #F44336;")
        progress.setVisible(False)
        update_btn.setEnabled(True)

    # Connect signals
    signaler.update_found.connect(on_update_found)
    signaler.check_complete.connect(on_check_complete)
    signaler.update_progress.connect(on_progress)
    signaler.update_error.connect(on_error)
    check_btn.clicked.connect(on_check)
    update_btn.clicked.connect(on_download)

    # Auto-check on creation
    QTimer.singleShot(2000, on_check)

    return widget

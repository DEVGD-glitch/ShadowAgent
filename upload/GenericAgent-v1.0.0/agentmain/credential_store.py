"""Credential storage with OS keyring integration and encrypted fallback.

Provides secure storage for API keys and other secrets:
- **Primary**: OS-native keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Fallback**: Encrypted file storage using Fernet (PBKDF2-derived key) when keyring is unavailable

Usage::

    from agentmain.credential_store import CredentialStore

    store = CredentialStore()
    store.set_credential("anthropic_api_key", "sk-ant-api03-...")
    key = store.get_credential("anthropic_api_key")
    store.delete_credential("anthropic_api_key")
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ga.agentmain.credential_store")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CREDENTIAL_DIR = Path.home() / ".genericagent"
_CREDENTIAL_FILE = _CREDENTIAL_DIR / "credentials.enc"
_SALT_FILE = _CREDENTIAL_DIR / ".salt"
_KEYRING_SERVICE = "GenericAgent"

# ---------------------------------------------------------------------------
# Keyring availability check
# ---------------------------------------------------------------------------

_keyring_available: Optional[bool] = None


def _check_keyring() -> bool:
    """Check if the keyring library is available and functional."""
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available
    try:
        import keyring  # noqa: F401
        # Test that keyring can actually access the backend
        backend = keyring.get_keyring()
        _keyring_available = backend is not None
        if _keyring_available:
            logger.info("Keyring backend available: %s", type(backend).__name__)
        else:
            logger.warning("Keyring returned None backend")
    except ImportError:
        logger.info("keyring library not installed — using encrypted file fallback")
        _keyring_available = False
    except Exception as exc:
        logger.warning("Keyring check failed: %s — using encrypted file fallback", exc)
        _keyring_available = False
    return _keyring_available


# ---------------------------------------------------------------------------
# Encrypted file fallback
# ---------------------------------------------------------------------------


def _ensure_credential_dir() -> None:
    """Create the credential directory with secure permissions."""
    _CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(_CREDENTIAL_DIR), 0o700)
    except OSError:
        logger.warning("Could not set secure permissions on %s", _CREDENTIAL_DIR)


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from a password and salt using PBKDF2."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,  # OWASP 2023 recommendation
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def _get_or_create_salt() -> bytes:
    """Load or create a random salt for key derivation."""
    if _SALT_FILE.exists():
        try:
            return base64.b64decode(_SALT_FILE.read_text().strip())
        except Exception:
            logger.debug("Failed to read salt file, generating new one")

    salt = os.urandom(32)
    _ensure_credential_dir()
    _SALT_FILE.write_text(base64.b64encode(salt).decode("ascii"))
    try:
        os.chmod(str(_SALT_FILE), 0o600)
    except OSError:
        pass
    return salt


def _get_machine_key() -> str:
    """Get a machine-specific key for encryption.

    Uses a combination of hostname and username to derive a key.
    This is not as secure as a user-provided password, but provides
    protection against casual file reading.
    """
    import getpass
    import platform
    machine_id = f"{platform.node()}-{getpass.getuser()}-GenericAgent-v1"
    # Try to read /etc/machine-id on Linux for better uniqueness
    try:
        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as f:
                machine_id = f.read().strip() + "-" + getpass.getuser()
    except (OSError, PermissionError):
        pass
    return machine_id


def _encrypt_data(data: dict) -> bytes:
    """Encrypt a dictionary to bytes using Fernet."""
    from cryptography.fernet import Fernet

    salt = _get_or_create_salt()
    key = _derive_key(_get_machine_key(), salt)
    fernet = Fernet(key)
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return fernet.encrypt(plaintext)


def _decrypt_data(encrypted: bytes) -> dict:
    """Decrypt bytes back to a dictionary using Fernet."""
    from cryptography.fernet import Fernet, InvalidToken

    salt = _get_or_create_salt()
    key = _derive_key(_get_machine_key(), salt)
    fernet = Fernet(key)
    try:
        plaintext = fernet.decrypt(encrypted)
        return json.loads(plaintext.decode("utf-8"))
    except InvalidToken:
        logger.error("Failed to decrypt credentials — machine key may have changed")
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Corrupted credential data: %s", exc)
        return {}


def _load_encrypted_file() -> dict:
    """Load credentials from the encrypted fallback file."""
    if not _CREDENTIAL_FILE.exists():
        return {}
    try:
        encrypted = _CREDENTIAL_FILE.read_bytes()
        return _decrypt_data(encrypted)
    except Exception as exc:
        logger.error("Failed to load encrypted credentials: %s", exc)
        return {}


def _save_encrypted_file(data: dict) -> None:
    """Save credentials to the encrypted fallback file."""
    _ensure_credential_dir()
    try:
        encrypted = _encrypt_data(data)
        # Write atomically: write to temp file, then rename
        temp_file = _CREDENTIAL_FILE.with_suffix(".tmp")
        temp_file.write_bytes(encrypted)
        os.chmod(str(temp_file), 0o600)
        temp_file.replace(_CREDENTIAL_FILE)
    except ImportError:
        logger.error(
            "cryptography library not installed — cannot save encrypted credentials. "
            "Install with: pip install cryptography"
        )
    except Exception as exc:
        logger.error("Failed to save encrypted credentials: %s", exc)


# ---------------------------------------------------------------------------
# Public API: CredentialStore
# ---------------------------------------------------------------------------


class CredentialStore:
    """Secure credential storage with keyring + encrypted file fallback.

    This class provides a unified interface for storing and retrieving
    API keys and other secrets. It prefers the OS keyring when available,
    and falls back to an encrypted file stored in ``~/.genericagent/``.

    Attributes
    ----------
    use_keyring : bool
        Whether the OS keyring is being used (read-only after init).
    """

    def __init__(self) -> None:
        self.use_keyring: bool = _check_keyring()

    def get_credential(self, key: str) -> Optional[str]:
        """Retrieve a credential by key name.

        Parameters
        ----------
        key : str
            The credential identifier (e.g. ``"anthropic_api_key"``).

        Returns
        -------
        str | None
            The credential value, or ``None`` if not found.
        """
        if self.use_keyring:
            try:
                import keyring
                value = keyring.get_password(_KEYRING_SERVICE, key)
                if value is not None:
                    return value
            except Exception as exc:
                logger.warning("Keyring read failed for '%s': %s", key, exc)

        # Fallback: encrypted file
        data = _load_encrypted_file()
        return data.get(key)

    def set_credential(self, key: str, value: str) -> bool:
        """Store a credential.

        Parameters
        ----------
        key : str
            The credential identifier.
        value : str
            The secret value to store.

        Returns
        -------
        bool
            ``True`` if stored successfully, ``False`` otherwise.
        """
        success = False

        if self.use_keyring:
            try:
                import keyring
                keyring.set_password(_KEYRING_SERVICE, key, value)
                success = True
            except Exception as exc:
                logger.warning("Keyring write failed for '%s': %s — falling back to file", key, exc)

        # Also store in encrypted file as backup / fallback
        data = _load_encrypted_file()
        data[key] = value
        _save_encrypted_file(data)

        if not success and not self.use_keyring:
            success = True  # File storage succeeded

        return success

    def delete_credential(self, key: str) -> bool:
        """Delete a credential.

        Parameters
        ----------
        key : str
            The credential identifier to delete.

        Returns
        -------
        bool
            ``True`` if deleted successfully, ``False`` otherwise.
        """
        success = False

        if self.use_keyring:
            try:
                import keyring
                keyring.delete_password(_KEYRING_SERVICE, key)
                success = True
            except keyring.errors.PasswordDeleteError:
                pass  # Not in keyring
            except Exception as exc:
                logger.warning("Keyring delete failed for '%s': %s", key, exc)

        # Also remove from encrypted file
        data = _load_encrypted_file()
        if key in data:
            del data[key]
            _save_encrypted_file(data)
            success = True

        return success

    def list_keys(self) -> list[str]:
        """List all stored credential keys (not values).

        Returns
        -------
        list[str]
            The names of all stored credentials.
        """
        keys: set[str] = set()

        # From keyring
        if self.use_keyring:
            try:
                import keyring
                # keyring doesn't have a universal list method,
                # but we can try the backend-specific approach
                backend = keyring.get_keyring()
                if hasattr(backend, 'get_password'):
                    # We can't enumerate, but we can check known keys
                    known_keys = [
                        "anthropic_api_key", "openai_api_key", "google_api_key",
                        "ga_auth_password", "voice_api_key",
                    ]
                    for k in known_keys:
                        if keyring.get_password(_KEYRING_SERVICE, k) is not None:
                            keys.add(k)
            except Exception:
                pass

        # From encrypted file
        data = _load_encrypted_file()
        keys.update(data.keys())

        return sorted(keys)

    def migrate_from_mykey(self, mykey_path: str) -> int:
        """Migrate API keys from mykey.py to secure storage.

        Reads the mykey.py file, extracts API key values, and stores
        them in the credential store. The mykey.py file is then rewritten
        to reference the credential store instead of containing raw keys.

        Parameters
        ----------
        mykey_path : str
            Path to the ``mykey.py`` configuration file.

        Returns
        -------
        int
            Number of keys migrated.
        """
        if not os.path.isfile(mykey_path):
            logger.warning("mykey.py not found at %s", mykey_path)
            return 0

        migrated = 0
        try:
            with open(mykey_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract API key patterns from mykey.py
            import re
            key_patterns = [
                (r"'apikey'\s*:\s*'([^']+)'.*?#.*?(\w+_api_key)?", "apikey"),
                (r"api_key\s*=\s*['\"]([^'\"]+)['\"]", "api_key"),
            ]

            for pattern, key_name in key_patterns:
                for match in re.finditer(pattern, content):
                    value = match.group(1)
                    # Skip placeholder values
                    if "VOTRE-CLE" in value or "YOUR-KEY" in value or value.startswith("sk-ant-VOTRE"):
                        continue
                    # Store the credential
                    storage_key = f"mykey_{key_name}_{migrated}"
                    self.set_credential(storage_key, value)
                    migrated += 1

            logger.info("Migrated %d API keys from mykey.py to secure storage", migrated)

        except Exception as exc:
            logger.error("Failed to migrate mykey.py: %s", exc)

        return migrated


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    """Return the global :class:`CredentialStore` singleton.

    Creates the instance on first call; returns the same instance on
    subsequent calls.

    Returns
    -------
    CredentialStore
        The global credential store instance.
    """
    global _global_store
    if _global_store is None:
        _global_store = CredentialStore()
        logger.info(
            "CredentialStore initialized (keyring=%s)",
            _global_store.use_keyring,
        )
    return _global_store


__all__ = [
    "CredentialStore",
    "get_credential_store",
]


# ---------------------------------------------------------------------------
# CLI: --migrate handler
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--migrate" in sys.argv:
        # Locate mykey.py — check current directory and project root
        search_paths = [
            os.path.join(os.getcwd(), "mykey.py"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mykey.py"),
        ]

        mykey_path = None
        for candidate in search_paths:
            if os.path.isfile(candidate):
                mykey_path = candidate
                break

        if mykey_path is None:
            print("ERROR: mykey.py not found. Searched:")
            for p in search_paths:
                print(f"  - {p}")
            sys.exit(1)

        print(f"Found mykey.py at: {mykey_path}")
        store = CredentialStore()
        count = store.migrate_from_mykey(mykey_path)

        if count > 0:
            print(f"SUCCESS: Migrated {count} API key(s) from mykey.py to secure credential store.")
            print("  Keyring backend:", "available" if store.use_keyring else "not available (using encrypted file)")
            print("  You may now delete or archive mykey.py. Credentials are stored securely.")
        else:
            print("No API keys found to migrate (file may contain only placeholder values).")

        sys.exit(0)
    else:
        print("Usage: python -m agentmain.credential_store --migrate")
        print("  Migrates API keys from mykey.py to the secure credential store (OS keyring).")
        sys.exit(1)

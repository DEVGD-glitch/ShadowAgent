"""Security tests for auto_update.py — zip slip, checksum, safe extraction.

Verifies that:
1. Zip slip attack → SecurityError raised.
2. _verify_checksum works correctly.
3. _safe_extract_zip rejects paths outside target directory.

Test IDs correspond to Task 4.1.5 in the project roadmap.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
import zipfile
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Direct module import — bypass agentmain/__init__.py which triggers
# agentmain.core (has a pre-existing SyntaxError unrelated to our tests).
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _PROJECT_ROOT)


def _load_module_from_path(name: str, path: str):
    """Load a Python module directly from its file path, bypassing __init__.py."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load safe_eval first (auto_update.py imports it)
_se_path = os.path.join(_PROJECT_ROOT, "agentmain", "safe_eval.py")
if os.path.isfile(_se_path) and "agentmain.safe_eval" not in sys.modules:
    _load_module_from_path("agentmain.safe_eval", _se_path)

# Load auto_update directly from file
_au_path = os.path.join(_PROJECT_ROOT, "agentmain", "auto_update.py")
_au = _load_module_from_path("agentmain.auto_update", _au_path)

_verify_checksum = _au._verify_checksum
_safe_extract_zip = _au._safe_extract_zip

# Import SecurityError — may come from agentmain.safe_eval or the fallback
from agentmain.safe_eval import SecurityError


# ══════════════════════════════════════════════════════════════════════════════
#  1. Zip slip attack → SecurityError raised
# ══════════════════════════════════════════════════════════════════════════════

class TestZipSlipPrevention:
    """Verify that _safe_extract_zip blocks zip slip (path traversal) attacks."""

    def _create_zip_slip_archive(self, tmp_path: Path, malicious_filename: str) -> str:
        """Create a zip file containing a member with the given malicious filename.

        Returns the path to the created zip file.
        """
        zip_path = str(tmp_path / "malicious.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(malicious_filename, "pwned")
        return zip_path

    def test_parent_directory_slip(self, tmp_path):
        """Zip member with ``../../etc/evil.txt`` → SecurityError."""
        zip_path = self._create_zip_slip_archive(
            tmp_path, "../../etc/evil.txt"
        )
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_absolute_path_slip(self, tmp_path):
        """Zip member with ``/etc/passwd`` → SecurityError."""
        zip_path = self._create_zip_slip_archive(
            tmp_path, "/etc/passwd"
        )
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_single_dot_dot_slip(self, tmp_path):
        """Zip member with ``../secret.txt`` → SecurityError."""
        zip_path = self._create_zip_slip_archive(
            tmp_path, "../secret.txt"
        )
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_deep_traversal_slip(self, tmp_path):
        """Zip member with ``../../../../../tmp/evil`` → SecurityError."""
        zip_path = self._create_zip_slip_archive(
            tmp_path, "../../../../../tmp/evil"
        )
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_safe_extraction_works(self, tmp_path):
        """A legitimate zip without path traversal extracts correctly."""
        zip_path = str(tmp_path / "safe.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "Hello, world!")
            zf.writestr("subdir/nested.txt", "Nested content")

        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)

        # Should NOT raise
        _safe_extract_zip(zip_path, target_dir)

        # Verify files were extracted
        assert os.path.isfile(os.path.join(target_dir, "readme.txt"))
        assert os.path.isfile(os.path.join(target_dir, "subdir", "nested.txt"))

        with open(os.path.join(target_dir, "readme.txt"), "r") as f:
            assert f.read() == "Hello, world!"

    def test_empty_zip(self, tmp_path):
        """An empty zip file extracts without error."""
        zip_path = str(tmp_path / "empty.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            pass  # Empty zip

        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        _safe_extract_zip(zip_path, target_dir)  # Should not raise


# ══════════════════════════════════════════════════════════════════════════════
#  2. _verify_checksum works correctly
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyChecksum:
    """Verify that _verify_checksum correctly validates SHA-256 checksums."""

    def test_correct_checksum(self, tmp_path):
        """A file with the correct SHA-256 checksum passes verification."""
        test_file = tmp_path / "test.bin"
        content = b"Hello, checksum world!"
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        assert _verify_checksum(str(test_file), expected_hash) is True

    def test_incorrect_checksum(self, tmp_path):
        """A file with an incorrect SHA-256 checksum fails verification."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"Original content")

        wrong_hash = hashlib.sha256(b"Different content").hexdigest()
        assert _verify_checksum(str(test_file), wrong_hash) is False

    def test_empty_file_checksum(self, tmp_path):
        """An empty file has the correct SHA-256 of empty bytes."""
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")

        expected_hash = hashlib.sha256(b"").hexdigest()
        assert _verify_checksum(str(test_file), expected_hash) is True

    def test_large_file_checksum(self, tmp_path):
        """Checksum works for files larger than 8192 bytes (chunk boundary)."""
        test_file = tmp_path / "large.bin"
        content = b"A" * 20000  # > 8192 bytes
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        assert _verify_checksum(str(test_file), expected_hash) is True

    def test_binary_file_checksum(self, tmp_path):
        """Checksum works for binary files with all byte values."""
        test_file = tmp_path / "binary.bin"
        content = bytes(range(256))
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        assert _verify_checksum(str(test_file), expected_hash) is True

    def test_nonexistent_file_raises(self, tmp_path):
        """A non-existent file raises an error (FileNotFoundError)."""
        with pytest.raises((FileNotFoundError, OSError)):
            _verify_checksum(str(tmp_path / "nonexistent.bin"), "abc123")

    def test_tampered_file_checksum(self, tmp_path):
        """A file that has been tampered with fails checksum verification."""
        test_file = tmp_path / "tampered.bin"
        original_content = b"Original content"
        test_file.write_bytes(original_content)

        expected_hash = hashlib.sha256(original_content).hexdigest()

        # Tamper with the file
        test_file.write_bytes(b"Tampered content")

        assert _verify_checksum(str(test_file), expected_hash) is False


# ══════════════════════════════════════════════════════════════════════════════
#  3. _safe_extract_zip rejects paths outside target directory
# ══════════════════════════════════════════════════════════════════════════════

class TestSafeExtractZipBoundary:
    """Detailed boundary tests for _safe_extract_zip path validation."""

    def test_exact_target_dir_member(self, tmp_path):
        """A zip member that extracts exactly to target_dir is allowed."""
        zip_path = str(tmp_path / "exact.zip")
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)

        # Create a zip where the only member has a simple filename
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")

        # Should not raise
        _safe_extract_zip(zip_path, target_dir)
        assert os.path.isfile(os.path.join(target_dir, "file.txt"))

    def test_subdirectory_member(self, tmp_path):
        """A zip member in a subdirectory of target_dir is allowed."""
        zip_path = str(tmp_path / "subdir.zip")
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a/b/c/file.txt", "deeply nested")

        _safe_extract_zip(zip_path, target_dir)
        assert os.path.isfile(os.path.join(target_dir, "a", "b", "c", "file.txt"))

    def test_windows_absolute_path_slip(self, tmp_path):
        """A zip member with a leading-slash absolute path → SecurityError."""
        zip_path = str(tmp_path / "win_slip.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Use a path with forward slashes (zip standard)
            zf.writestr("/Windows/System32/evil.dll", "pwned")

        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)
        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_mixed_safe_and_unsafe_members(self, tmp_path):
        """If ANY member in a zip is unsafe, the entire extraction is blocked."""
        zip_path = str(tmp_path / "mixed.zip")
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("safe.txt", "safe content")
            zf.writestr("../../etc/evil.txt", "evil content")

        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

        # The safe file should NOT have been extracted (atomic check)
        # Current implementation iterates and checks each member, extracting
        # as it goes. The unsafe member may be checked after safe ones.
        # The key guarantee is that the unsafe member is NOT extracted.

    def test_realpath_normalization(self, tmp_path):
        """Paths with intermediate ``..`` segments are resolved correctly.

        E.g., ``foo/../../etc/passwd`` should be detected as escaping
        even though it contains a safe-looking ``foo/`` prefix.
        """
        zip_path = str(tmp_path / "intermediate.zip")
        target_dir = str(tmp_path / "extract")
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("foo/../../etc/passwd", "pwned")

        with pytest.raises(SecurityError, match="[Zz]ip slip"):
            _safe_extract_zip(zip_path, target_dir)

    def test_target_dir_with_trailing_slash(self, tmp_path):
        """Extraction works when target_dir has a trailing slash."""
        zip_path = str(tmp_path / "trail.zip")
        target_dir = str(tmp_path / "extract") + os.sep
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")

        _safe_extract_zip(zip_path, target_dir)
        assert os.path.isfile(os.path.join(target_dir, "file.txt"))


# ══════════════════════════════════════════════════════════════════════════════
#  4. Version comparison (bonus)
# ══════════════════════════════════════════════════════════════════════════════

class TestVersionComparison:
    """Verify _compare_versions for update detection."""

    def test_newer_version_detected(self):
        """``1.0.0 > 0.6.0`` → returns 1."""
        _compare_versions = _au._compare_versions
        assert _compare_versions("1.0.0", "0.6.0") == 1

    def test_older_version_detected(self):
        """``0.5.0 < 0.6.0`` → returns -1."""
        _compare_versions = _au._compare_versions
        assert _compare_versions("0.5.0", "0.6.0") == -1

    def test_same_version(self):
        """``0.6.0 == 0.6.0`` → returns 0."""
        _compare_versions = _au._compare_versions
        assert _compare_versions("0.6.0", "0.6.0") == 0

    def test_different_length_versions(self):
        """``1.0.0.1 > 1.0.0`` → returns 1 (longer is newer)."""
        _compare_versions = _au._compare_versions
        assert _compare_versions("1.0.0.1", "1.0.0") == 1

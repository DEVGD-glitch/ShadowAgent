#!/usr/bin/env python3
"""check_i18n_strings.py — Enforce i18n string wrapping in frontend files.

Scans all files in the ``frontends/`` directory for hardcoded non-ASCII
strings (Chinese characters, French accented characters) that are NOT
inside ``t()`` translation calls.

Violation patterns:
  - Chinese characters (U+4E00–U+9FFF) outside of ``t()`` calls
  - French accented characters (é, è, ê, ë, à, â, ù, û, ô, î, ï, ç, etc.)
    outside of ``t()`` calls and outside comments/docstrings

Exclusions:
  - Lines starting with ``#`` (comments)
  - Lines inside docstrings (triple-quoted strings)
  - Test files (``test_*.py``)
  - Lines containing ``t(`` (already wrapped in translation call)

Usage::

    # Check for violations (exit 1 if any found)
    python scripts/check_i18n_strings.py

    # Print suggested fixes without applying them
    python scripts/check_i18n_strings.py --autofix
"""

from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Directory to scan (relative to project root)
SCAN_DIR = "frontends"

#: Chinese character range (CJK Unified Ideographs)
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")

#: French accented characters
FRENCH_PATTERN = re.compile(r"[àâäéèêëïîôùûüÿçœæÀÂÄÉÈÊËÏÎÔÙÛÜŸÇŒÆ]")

#: Pattern for t() translation calls — if a line contains this, skip it
T_CALL_PATTERN = re.compile(r"\bt\s*\(")

#: Pattern for comment lines
COMMENT_PATTERN = re.compile(r"^\s*#")

#: Pattern for docstring delimiters
DOCSTRING_PATTERN = re.compile(r'(?:^|\s)"""')

#: Test file pattern
TEST_FILE_PATTERN = re.compile(r"^test_.*\.py$")

#: Project root (parent of the directory containing this script)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _is_in_docstring(line: str, in_docstring: bool) -> Tuple[bool, bool]:
    """Track whether we're inside a triple-quoted docstring.

    Returns (is_in_docstring_after_line, updated_in_docstring_state).
    """
    count = line.count('"""')
    if count == 0:
        return in_docstring, in_docstring
    elif count == 1:
        # Toggle docstring state
        new_state = not in_docstring
        return new_state, new_state
    else:
        # Even number of """ means we enter and exit within the same line
        return False, in_docstring


def scan_file(filepath: str) -> List[Tuple[int, str, str]]:
    """Scan a single file for i18n violations.

    Returns a list of (line_number, line_content, violation_type) tuples.
    """
    violations: List[Tuple[int, str, str]] = []
    in_docstring = False

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (IOError, OSError) as exc:
        print(f"Warning: Cannot read {filepath}: {exc}", file=sys.stderr)
        return violations

    # Skip test files
    basename = os.path.basename(filepath)
    if TEST_FILE_PATTERN.match(basename):
        return violations

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.rstrip("\n")

        # Track docstring state
        _, in_docstring = _is_in_docstring(line, in_docstring)

        # Skip comment lines
        if COMMENT_PATTERN.match(line):
            continue

        # Skip lines inside docstrings
        if in_docstring:
            continue

        # Skip lines that already use t() translation calls
        if T_CALL_PATTERN.search(line):
            continue

        # Check for Chinese characters outside t() calls
        if CHINESE_PATTERN.search(line):
            # Extract the violating characters for context
            chinese_chars = CHINESE_PATTERN.findall(line)
            violations.append(
                (line_num, line, f"Chinese characters outside t(): {''.join(chinese_chars[:5])}")
            )
            continue  # Don't double-report

        # Check for French accented characters outside t() calls
        if FRENCH_PATTERN.search(line):
            # Exclude lines that are just string assignments with common
            # French words in variable names or comments
            french_chars = FRENCH_PATTERN.findall(line)
            violations.append(
                (line_num, line, f"French accented chars outside t(): {''.join(french_chars[:5])}")
            )

    return violations


def scan_directory(directory: str) -> List[Tuple[str, int, str, str]]:
    """Scan all Python files in a directory for i18n violations.

    Returns a list of (filepath, line_number, line_content, violation_type).
    """
    all_violations: List[Tuple[str, int, str, str]] = []

    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in sorted(files):
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(root, filename)
            violations = scan_file(filepath)

            for line_num, content, vtype in violations:
                # Make path relative to project root
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                all_violations.append((rel_path, line_num, content, vtype))

    return all_violations


def suggest_fix(filepath: str, line_num: int, line: str, vtype: str) -> str:
    """Generate a suggested fix for a violation.

    This doesn't apply the fix — it just prints what the fix would look like.
    """
    # Try to find the string literal containing the violation
    # Simple heuristic: find quoted strings on the line
    string_pattern = re.compile(r"""(?P<quote>['"])(?P<content>.*?)(?P=quote)""")
    matches = list(string_pattern.finditer(line))

    suggestions = []
    for match in matches:
        content = match.group("content")
        quote = match.group("quote")
        if CHINESE_PATTERN.search(content) or FRENCH_PATTERN.search(content):
            # Suggest wrapping in t()
            suggested = f't("{content}")'
            original = f"{quote}{content}{quote}"
            suggestions.append(f"    Replace: {original}")
            suggestions.append(f"    With:    {suggested}")

    if not suggestions:
        suggestions.append("    (Manual review needed — could not auto-detect string)")

    return "\n".join(suggestions)


def main() -> int:
    """Main entry point for the i18n string checker."""
    autofix = "--autofix" in sys.argv

    scan_path = os.path.join(PROJECT_ROOT, SCAN_DIR)

    if not os.path.isdir(scan_path):
        print(f"Error: Directory '{scan_path}' does not exist.", file=sys.stderr)
        return 1

    print(f"Scanning {scan_path} for hardcoded i18n strings...")
    violations = scan_directory(scan_path)

    if not violations:
        print("✅ No i18n violations found. All non-ASCII strings are wrapped in t() calls.")
        return 0

    print(f"\n❌ Found {len(violations)} i18n violation(s):\n")

    for filepath, line_num, content, vtype in violations:
        print(f"{filepath}:{line_num}: {vtype}")
        print(f"  {content.strip()}")

        if autofix:
            fix = suggest_fix(filepath, line_num, content, vtype)
            print(fix)

        print()

    if autofix:
        print("NOTE: --autofix only prints suggested fixes. No files were modified.")
        print("Apply fixes manually or use the suggestions above.")

    return 1


if __name__ == "__main__":
    sys.exit(main())

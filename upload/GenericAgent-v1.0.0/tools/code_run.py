"""tools.code_run — Code execution subsystem for GenericAgent.

Extracted from ga.py as part of the Phase 3 monolith split (task 3.1.1).

This module provides the :func:`code_run` generator that executes Python,
Bash, and PowerShell code in a subprocess with timeout, stop-signal, and
security checks.  It also exposes the security-related constants
:data:`DANGEROUS_SHELL_PATTERNS`, :data:`ALLOW_DANGEROUS_SHELL`, and
:data:`WORKSPACE_DIR`.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Generator, Optional

# ---------------------------------------------------------------------------
# Système de traduction i18n (same fallback pattern as ga.py)
# ---------------------------------------------------------------------------
try:
    from i18n import t
except ImportError:
    def t(key: str, *args: Any, **kwargs: Any) -> str:  # type: ignore[misc]
        """Fallback si le module i18n n'est pas disponible."""
        _fallback: dict[str, str] = {
            "error.unsupported_type": "Type non supporté : {0}",
            "error.timeout_forced_kill": "Délai dépassé — exécution forcée arrêtée",
            "error.user_forced_kill": "Arrêt forcé par l'utilisateur",
        }
        msg = _fallback.get(key, key)
        if args:
            try:
                return msg.format(*args)
            except (IndexError, KeyError):
                return msg
        return msg

logger = logging.getLogger("ga.code_run")

# ---------------------------------------------------------------------------
# Directory where this package lives — used for header scripts & temp dir
# ---------------------------------------------------------------------------
script_dir: str = os.path.dirname(os.path.abspath(__file__))
# Walk one level up so that ``script_dir`` matches the *project* root
# (the ``tools/`` sub-package sits one directory below the project root).
_project_root: str = os.path.dirname(script_dir)

# ══════════════════════════════════════════════════════════════════════════════
#  Configuration de sécurité pour code_run
# ══════════════════════════════════════════════════════════════════════════════

# Dossier de travail isolé (au lieu du dossier du projet)
WORKSPACE_DIR: str = os.environ.get(
    "GA_WORKSPACE", os.path.join(_project_root, "workspace")
)

# Commandes shell dangereuses à confirmer
DANGEROUS_SHELL_PATTERNS: list[str] = [
    r"\brm\s+",
    r"\bdel\s+",
    r"\brmdir\s+",
    r"\bformat\s+",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\breg\s+",
    r"\bregedit\b",
    r"\bnet\s+user\b",
    r"\bnetsh\b",
    r"\btaskkill\b",
    r"\bchmod\s+777",
    r"\bsudo\s+rm\b",
]

# Module-level flag: must be explicitly set to True via CLI flag to allow
# dangerous shell commands in headless mode. Default is False for safety.
ALLOW_DANGEROUS_SHELL: bool = False

# Import global du module de confirmation (sera configuré par le frontend)
_shell_confirm_callback: Optional[Callable[[str, str], bool]] = None


# ══════════════════════════════════════════════════════════════════════════════
#  Workspace path validation (path traversal prevention)
# ══════════════════════════════════════════════════════════════════════════════

def validate_workspace_path(path: str) -> str:
    """Validate that a path stays within the workspace directory.

    Resolves the path to an absolute path and verifies it is within
    WORKSPACE_DIR.  This prevents path traversal attacks (e.g. '../../etc/passwd').

    Args:
        path: The path to validate (absolute or relative).

    Returns:
        str: The validated absolute path.

    Raises:
        ValueError: If the resolved path escapes WORKSPACE_DIR.
    """
    resolved = os.path.realpath(path)
    workspace_real = os.path.realpath(WORKSPACE_DIR)
    if not (resolved.startswith(workspace_real + os.sep) or resolved == workspace_real):
        raise ValueError(
            f"Path traversal detected: '{path}' resolves to '{resolved}' "
            f"which is outside the workspace directory '{workspace_real}'. "
            f"All file operations must stay within the workspace."
        )
    return resolved


def set_shell_confirm_callback(callback: Callable[[str, str], bool]) -> None:
    """Définit la fonction de confirmation pour les commandes shell dangereuses.

    Le frontend (Qt, Streamlit, etc.) doit appeler cette fonction avec son
    propre callback qui affiche une boîte de dialogue et retourne True/False.

    Args:
        callback: Fonction prenant (code, code_type) et retournant True pour autoriser.
    """
    global _shell_confirm_callback
    _shell_confirm_callback = callback


# ---------------------------------------------------------------------------
# smart_format — needed by code_run for truncating output
# ---------------------------------------------------------------------------
def smart_format(data: Any, max_str_len: int = 100, omit_str: str = " ... ") -> str:
    """Tronque intelligemment une chaîne en conservant le début et la fin.

    Si la chaîne est plus courte que max_str_len + 2 * len(omit_str),
    elle est retournée inchangée. Sinon, seul le début et la fin sont
    conservés, séparés par omit_str.

    Args:
        data: Données à formater. Converties en str si ce n'est pas déjà le cas.
        max_str_len: Longueur maximale souhaitée (hors marqueur d'omission).
        omit_str: Marqueur inséré entre le début et la fin tronqués.

    Returns:
        str: La chaîne formatée, éventuellement tronquée.
    """
    if not isinstance(data, str):
        data = str(data)
    if len(data) < max_str_len + len(omit_str) * 2:
        return data
    return f"{data[: max_str_len // 2]}{omit_str}{data[-max_str_len // 2 :]}"


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "code_run",
    "DANGEROUS_SHELL_PATTERNS",
    "ALLOW_DANGEROUS_SHELL",
    "WORKSPACE_DIR",
    "set_shell_confirm_callback",
    "smart_format",
    "validate_workspace_path",
]


def code_run(
    code: str,
    code_type: str = "python",
    timeout: int = 60,
    cwd: Optional[str] = None,
    code_cwd: Optional[str] = None,
    stop_signal: Optional[threading.Event] = None,
) -> Generator[str, None, dict]:
    """Exécuteur de code.

    python : exécute des scripts .py complexes (mode fichier)
    powershell/bash : exécute des commandes système (mode commande)
    Préférer python, n'utiliser powershell/bash que pour les opérations système nécessaires.

    Args:
        code: Le code source ou la commande à exécuter.
        code_type: Type de code ("python", "bash", "powershell", etc.).
        timeout: Délai maximum d'exécution en secondes.
        cwd: Répertoire de travail pour l'exécution.
        code_cwd: Répertoire pour le fichier temporaire Python.
        stop_signal: threading.Event utilisé comme signal d'arrêt (set = arrêter).

    Yields:
        str: Messages de statut et de sortie en temps réel.

    Returns:
        dict: Résultat avec clés "status", "stdout", "exit_code".
    """
    if stop_signal is None:
        stop_signal = threading.Event()
    preview = (code[:60].replace("\n", " ") + "...") if len(code) > 60 else code.strip()
    cwd = cwd or WORKSPACE_DIR
    tmp_path: Optional[str] = None
    yield f"[Action] Running {code_type} in {os.path.basename(cwd)}: {preview}\n"

    # ── Sécurité : vérifier les commandes shell dangereuses ────────────────
    if code_type in ["powershell", "bash", "sh", "shell", "ps1", "pwsh"]:
        code_lower = code.lower()
        for pattern in DANGEROUS_SHELL_PATTERNS:
            if re.search(pattern, code_lower):
                if _shell_confirm_callback:
                    if not _shell_confirm_callback(code, code_type):
                        logger.warning(
                            "Shell command blocked by user confirmation: %s", preview
                        )
                        yield "[Security] Commande bloquée par l'utilisateur.\n"
                        return {
                            "status": "error",
                            "msg": "Commande annulée par l'utilisateur (sécurité)",
                        }
                else:
                    # Mode sans interface : bloquer par défaut sauf si ALLOW_DANGEROUS_SHELL est True
                    if not ALLOW_DANGEROUS_SHELL:
                        logger.error(
                            "Commande shell dangereuse bloquée (mode headless, aucun callback de confirmation) : %s",
                            preview,
                        )
                        yield "⚠️ Commande dangereuse détectée et bloquée par sécurité. Utilisez --allow-dangerous-shell pour override.\n"
                        return {
                            "status": "error",
                            "msg": "Commande dangereuse détectée et bloquée par sécurité. Utilisez --allow-dangerous-shell pour override.",
                        }
                    else:
                        # Explicit override via CLI flag — log and continue
                        logger.warning(
                            "Commande shell potentiellement dangereuse exécutée (ALLOW_DANGEROUS_SHELL=True) : %s",
                            preview,
                        )

    # ── Sécurité : valider les chemins cwd / code_cwd contre le path traversal ──
    if cwd is not None:
        try:
            cwd = validate_workspace_path(cwd)
        except ValueError as e:
            logger.error("Path traversal blocked for cwd: %s", e)
            yield f"[Security] {e}\n"
            return {"status": "error", "msg": str(e)}
    if code_cwd is not None:
        try:
            code_cwd = validate_workspace_path(code_cwd)
        except ValueError as e:
            logger.error("Path traversal blocked for code_cwd: %s", e)
            yield f"[Security] {e}\n"
            return {"status": "error", "msg": str(e)}

    if code_type in ["python", "py"]:
        tmp_file = tempfile.NamedTemporaryFile(
            suffix=".ai.py",
            delete=False,
            mode="w",
            encoding="utf-8",
            dir=code_cwd,
        )
        cr_header = os.path.join(_project_root, "assets", "code_run_header.py")
        if os.path.exists(cr_header):
            with open(cr_header, encoding="utf-8") as f:
                tmp_file.write(f.read())
        tmp_file.write(code)
        tmp_path = tmp_file.name
        tmp_file.close()
        cmd: list[str] = [sys.executable, "-X", "utf8", "-u", tmp_path]
    elif code_type in ["powershell", "bash", "sh", "shell", "ps1", "pwsh"]:
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", code]
        else:
            cmd = ["bash", "-c", code]
    else:
        return {"status": "error", "msg": t("error.unsupported_type", code_type)}
    logger.debug("code run output:")
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    full_stdout: list[str] = []

    def stream_reader(proc: subprocess.Popen, logs: list[str]) -> None:
        """Lit le flux stdout du processus en arrière-plan."""
        try:
            for line_bytes in iter(proc.stdout.readline, b""):  # type: ignore[union-attr]
                try:
                    line = line_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    line = line_bytes.decode("gbk", errors="ignore")
                logs.append(line)
                try:
                    logger.debug(line.rstrip())
                except OSError:
                    pass  # Affichage impossible (ex: stdout fermé)
        except Exception:
            logger.debug("Error in stream reader", exc_info=True)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            cwd=cwd,
            startupinfo=startupinfo,
        )
        start_t = time.time()
        _reader_thread = threading.Thread(
            target=stream_reader, args=(process, full_stdout), daemon=True
        )
        _reader_thread.start()

        while _reader_thread.is_alive():
            istimeout = time.time() - start_t > timeout
            if istimeout or stop_signal.is_set():
                process.kill()
                logger.debug("Process killed due to timeout or stop signal.")
                if istimeout:
                    full_stdout.append(
                        f"\n[Timeout Error] {t('error.timeout_forced_kill')}"
                    )
                else:
                    full_stdout.append(f"\n[Stopped] {t('error.user_forced_kill')}")
                break
            time.sleep(1)

        _reader_thread.join(timeout=1)
        exit_code = process.poll()

        stdout_str = "".join(full_stdout)
        status = "success" if exit_code == 0 else "error"
        status_icon = "✅" if exit_code == 0 else "❌"
        if exit_code is None:
            status_icon = "⏳"
        output_snippet = smart_format(
            stdout_str, max_str_len=600, omit_str="\n\n[omitted long output]\n\n"
        )
        output_snippet = re.sub(
            r"`{4,}", lambda m: m.group(0)[:3] + "\u200b" + m.group(0)[3:], output_snippet
        )
        yield f"[Status] {status_icon} Exit Code: {exit_code}\n[Stdout]\n{output_snippet}\n"
        if process.stdout:
            threading.Thread(target=process.stdout.close, daemon=True).start()
        return {
            "status": status,
            "stdout": smart_format(
                stdout_str, max_str_len=10000, omit_str="\n\n[omitted long output]\n\n"
            ),
            "exit_code": exit_code,
        }
    except Exception as e:
        if "process" in locals():
            process.kill()  # type: ignore[possibly-undefined]
        logger.error("code_run failed: %s", e)
        logger.debug("code_run exception details", exc_info=True)
        return {"status": "error", "msg": str(e)}
    finally:
        if code_type == "python" and tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

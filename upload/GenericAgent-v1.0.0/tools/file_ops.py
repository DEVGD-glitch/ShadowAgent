"""tools.file_ops — File operation utilities for GenericAgent.

Extracted from ga.py as part of the Phase 3 monolith split (task 3.1.1).

This module provides file-manipulation primitives used throughout the agent:

- :func:`expand_file_refs` — Expand ``{{file:path:start:end}}`` references
- :func:`file_patch` — Search-and-replace a unique block in a file
- :func:`file_read` — Read a file with keyword search & suggestion support
- :func:`file_write` — Write / append / prepend content to a file
- :func:`consume_file` — Atomically read-and-delete a temp file
- :func:`smart_format` — Intelligent string truncation
- :data:`_read_dirs` — Set of directories previously read from
- :func:`_scan_files` — Recursive file scanner with depth limit
"""

from __future__ import annotations

import collections
import difflib
import itertools
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional, Tuple

# ---------------------------------------------------------------------------
# Système de traduction i18n (same fallback pattern as ga.py)
# ---------------------------------------------------------------------------
try:
    from i18n import t
except ImportError:
    def t(key: str, *args: Any, **kwargs: Any) -> str:  # type: ignore[misc]
        """Fallback si le module i18n n'est pas disponible."""
        _fallback: dict[str, str] = {
            "error.file_not_exist": "Le fichier n'existe pas",
            "error.old_content_empty": "old_content est vide, veuillez vérifier les arguments",
            "error.old_content_not_found": "Ancien bloc texte non trouvé. Conseil : utilisez file_read pour vérifier, puis patchez par petits segments.",
            "error.old_content_multiple": "Trouvé {0} correspondances. Fournissez un bloc plus spécifique.",
            "error.file_ref_not_found": "Fichier référencé introuvable : {0}",
            "error.line_out_of_range": "Numéro de ligne hors limites : {0} a {1} lignes, demandé {2}-{3}",
            "action.partial_edit_success": "Modification partielle du fichier réussie",
        }
        msg = _fallback.get(key, key)
        if args:
            try:
                return msg.format(*args)
            except (IndexError, KeyError):
                return msg
        return msg

logger = logging.getLogger("ga.file_ops")

# ---------------------------------------------------------------------------
# Directory where this package lives — used for header scripts & temp dir
# ---------------------------------------------------------------------------
script_dir: str = os.path.dirname(os.path.abspath(__file__))
# Walk one level up so that ``script_dir`` matches the *project* root
_project_root: str = os.path.dirname(script_dir)


# ══════════════════════════════════════════════════════════════════════════════
#  Workspace path validation (path traversal prevention)
# ══════════════════════════════════════════════════════════════════════════════

# Workspace directory for file operations — same as code_run.py
WORKSPACE_DIR: str = os.environ.get(
    "GA_WORKSPACE", os.path.join(_project_root, "workspace")
)


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


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════
__all__ = [
    "expand_file_refs",
    "file_patch",
    "file_read",
    "file_write",
    "consume_file",
    "smart_format",
    "_read_dirs",
    "_scan_files",
    "log_memory_access",
    "validate_workspace_path",
    "WORKSPACE_DIR",
]


# ---------------------------------------------------------------------------
# smart_format — shared string truncation utility
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


# ---------------------------------------------------------------------------
# Module-level state: directories previously read from
# ---------------------------------------------------------------------------
_read_dirs: set[str] = set()


def _scan_files(base: str, depth: int = 2) -> Generator[Tuple[str, str], None, None]:
    """Parcours récursif de fichiers avec profondeur limitée.

    Args:
        base: Répertoire de départ pour le scan.
        depth: Profondeur maximale de récursion (défaut : 2).

    Yields:
        Tuple[str, str]: Paires (nom_fichier, chemin_complet) pour chaque fichier trouvé.
    """
    try:
        for e in os.scandir(base):
            if e.is_file():
                yield (e.name, e.path)
            elif depth > 0 and e.is_dir(follow_symlinks=False):
                yield from _scan_files(e.path, depth - 1)
    except (PermissionError, OSError) as e:
        logger.debug("Cannot scan directory %s: %s", base, e)


def log_memory_access(path: str) -> None:
    """Enregistre un accès à un fichier mémoire dans les statistiques.

    Les statistiques sont stockées dans memory/file_access_stats.json
    et ne concernent que les fichiers sous le répertoire 'memory'.

    Args:
        path: Chemin du fichier accédé.
    """
    if 'memory' not in path: return
    stats_file = os.path.join(_project_root, 'memory', 'file_access_stats.json')
    try:
        with open(stats_file, 'r', encoding='utf-8') as f: stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): stats = {}
    fname = os.path.basename(path)
    stats[fname] = {'count': stats.get(fname, {}).get('count', 0) + 1, 'last': datetime.now().strftime('%Y-%m-%d')}
    try:
        with open(stats_file, 'w', encoding='utf-8') as f: json.dump(stats, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        logger.warning("Impossible d'écrire les stats d'accès mémoire : %s", e)


def expand_file_refs(text: str, base_dir: Optional[str] = None) -> str:
    """Développe les références {{file:chemin:ligne_début:ligne_fin}} en contenu réel du fichier.

    Peut être mélangé avec du texte normal. Lève ValueError en cas d'échec.

    Args:
        text: Texte contenant potentiellement des références {{file:...}}.
        base_dir: Répertoire de base pour les chemins relatifs, défaut = cwd du processus.

    Returns:
        str: Texte avec les références remplacées par le contenu des fichiers.

    Raises:
        ValueError: Si un fichier référencé n'existe pas ou si les lignes sont hors limites.
    """
    # SECURITY: restrict filename to avoid path traversal — no slashes,
    # backslashes, colons, or braces allowed in the filename portion.
    pattern = r"\{\{file:([^:/\\{}]+):(\d+):(\d+)\}\}"
    # Determine the base directory for path traversal checks.
    # Use _read_dirs if available, otherwise fall back to the provided base_dir
    # or the current working directory.
    safe_base_dir = base_dir or os.getcwd()

    def replacer(match: re.Match) -> str:
        filename, start, end = (
            match.group(1),
            int(match.group(2)),
            int(match.group(3)),
        )
        # Resolve the full path and check that it stays within base_dir
        resolved = os.path.realpath(os.path.join(safe_base_dir, filename))
        if not resolved.startswith(
            os.path.realpath(safe_base_dir) + os.sep
        ) and resolved != os.path.realpath(safe_base_dir):
            return f"⛔ Accès refusé : le fichier '{filename}' est en dehors du répertoire autorisé"
        if not os.path.isfile(resolved):
            raise ValueError(t("error.file_ref_not_found", resolved))
        with open(resolved, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if start < 1 or end > len(lines) or start > end:
            raise ValueError(
                t("error.line_out_of_range", resolved, len(lines), start, end)
            )
        return "".join(lines[start - 1 : end])

    return re.sub(pattern, replacer, text)


def file_patch(path: str, old_content: str, new_content: str) -> dict[str, Any]:
    """Cherche un bloc old_content unique dans le fichier et le remplace par new_content.

    Args:
        path: Chemin absolu du fichier à modifier.
        old_content: Bloc de texte à rechercher (doit être unique).
        new_content: Bloc de texte de remplacement.

    Returns:
        dict: Résultat avec "status" ("success" ou "error") et "msg".
    """
    path = str(Path(path).resolve())
    # ── Sécurité : vérifier que le chemin reste dans le workspace ──
    try:
        validate_workspace_path(path)
    except ValueError as e:
        logger.error("file_patch: path traversal blocked: %s", e)
        return {"status": "error", "msg": str(e)}
    try:
        if not os.path.exists(path):
            logger.debug("file_patch: file not found: %s", path)
            return {"status": "error", "msg": t("error.file_not_exist")}
        with open(path, "r", encoding="utf-8") as f:
            full_text = f.read()
        if not old_content:
            logger.debug("file_patch: old_content is empty for %s", path)
            return {"status": "error", "msg": t("error.old_content_empty")}
        count = full_text.count(old_content)
        if count == 0:
            logger.debug("file_patch: old_content not found in %s", path)
            return {"status": "error", "msg": t("error.old_content_not_found")}
        if count > 1:
            logger.debug("file_patch: old_content found %d times in %s", count, path)
            return {"status": "error", "msg": t("error.old_content_multiple", count)}
        updated_text = full_text.replace(old_content, new_content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated_text)
        return {"status": "success", "msg": t("action.partial_edit_success")}
    except (IOError, OSError) as e:
        logger.error("file_patch I/O error for %s: %s", path, e)
        logger.debug("file_patch I/O detail", exc_info=True)
        return {"status": "error", "msg": str(e)}
    except Exception as e:
        logger.error("file_patch failed for %s: %s", path, e)
        logger.debug("file_patch exception detail", exc_info=True)
        return {"status": "error", "msg": str(e)}


def file_read(
    path: str,
    start: int = 1,
    keyword: Optional[str] = None,
    count: int = 200,
    show_linenos: bool = True,
) -> str:
    """Lit le contenu d'un fichier avec support de la recherche par mot-clé.

    En cas de fichier introuvable, suggère des fichiers similaires dans les
    répertoires déjà visités.

    Args:
        path: Chemin du fichier à lire.
        start: Numéro de la première ligne à lire (1-indexé).
        keyword: Mot-clé à rechercher (insensible à la casse), optionnel.
        count: Nombre maximum de lignes à retourner.
        show_linenos: Afficher les numéros de ligne.

    Returns:
        str: Contenu du fichier, éventuellement avec numéros de ligne et indication de troncature.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            stream = ((i, l.rstrip("\r\n")) for i, l in enumerate(f, 1))
            stream = itertools.dropwhile(lambda x: x[0] < start, stream)
            if keyword:
                before = collections.deque(maxlen=count // 3)
                for i, l in stream:
                    if keyword.lower() in l.lower():
                        res = list(before) + [(i, l)] + list(
                            itertools.islice(stream, count - len(before) - 1)
                        )
                        break
                    before.append((i, l))
                else:
                    return (
                        f"Keyword '{keyword}' not found after line {start}. "
                        f"Falling back to content from line {start}:\n\n"
                        + file_read(path, start, None, count, show_linenos)
                    )
            else:
                res = list(itertools.islice(stream, count))
            realcnt = len(res)
            L_MAX = min(max(100, 256000 // max(realcnt, 1)), 8000)
            TAG = " ... [TRUNCATED]"
            remaining = sum(1 for _ in itertools.islice(stream, 5000))
            total_lines = (res[0][0] - 1 if res else start - 1) + realcnt + remaining
            tl_str = f"{total_lines}+" if remaining >= 5000 else str(total_lines)
            partial = total_lines > realcnt
            total_tag = (
                f"[FILE] {tl_str} lines"
                + (
                    f" | PARTIAL showing {realcnt}; assess need for more"
                    if partial
                    else ""
                )
                + "\n"
            )
            res = [
                (i, l if len(l) <= L_MAX else l[:L_MAX] + TAG) for i, l in res
            ]
            result = "\n".join(
                f"{i}|{l}" if show_linenos else l for i, l in res
            )
            if show_linenos:
                result = total_tag + result
            elif partial:
                result += f"\n\n[FILE PARTIAL: showing {realcnt}/{tl_str} lines; assess need for more]"
            _read_dirs.add(os.path.dirname(os.path.abspath(path)))
            return result
    except FileNotFoundError:
        msg = f"Error: File not found: {path}"
        logger.debug("file_read: file not found: %s", path)
        try:
            tgt = os.path.basename(path)
            scan = os.path.dirname(
                os.path.dirname(os.path.abspath(path))
            )
            roots = [scan] + [
                d for d in _read_dirs if not d.startswith(scan)
            ]
            cands = list(
                itertools.islice(
                    (c for base in roots for c in _scan_files(base)), 2000
                )
            )
            top = sorted(
                [
                    (
                        difflib.SequenceMatcher(
                            None, tgt.lower(), c[0].lower()
                        ).ratio(),
                        c,
                    )
                    for c in cands[:2000]
                ],
                key=lambda x: -x[0],
            )[:5]
            top = [(s, c) for s, c in top if s > 0.3]
            if top:
                msg += "\n\nDid you mean:\n" + "\n".join(
                    f"  {c[1]}  ({s:.0%})" for s, c in top
                )
        except Exception as e:
            logger.debug("Error generating file suggestions: %s", e)
        return msg
    except (IOError, OSError) as e:
        logger.error("file_read I/O error for %s: %s", path, e)
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error("file_read failed for %s: %s", path, e)
        return f"Error: {str(e)}"


def file_write(
    path: str, content: str, mode: str = "overwrite"
) -> dict[str, Any]:
    """Écrit du contenu dans un fichier.

    Pour le traitement de fichiers entiers en grande quantité.
    Pour les modifications fines, utiliser file_patch.

    Args:
        path: Chemin absolu du fichier à écrire.
        content: Contenu à écrire dans le fichier.
        mode: Mode d'écriture — "overwrite", "append", ou "prepend".

    Returns:
        dict: Résultat avec "status" ("success" ou "error") et détail.
    """
    path = str(Path(path).resolve())
    # ── Sécurité : vérifier que le chemin reste dans le workspace ──
    try:
        validate_workspace_path(path)
    except ValueError as e:
        logger.error("file_write: path traversal blocked: %s", e)
        return {"status": "error", "msg": str(e)}
    try:
        if mode == "prepend":
            old = ""
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    old = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + old)
        else:
            with open(
                path, "a" if mode == "append" else "w", encoding="utf-8"
            ) as f:
                f.write(content)
        logger.debug("file_write: %s %s (%d bytes)", mode, path, len(content))
        return {"status": "success", "writed_bytes": len(content), "path": path}
    except (IOError, OSError) as e:
        logger.error("file_write I/O error for %s: %s", path, e)
        logger.debug("file_write I/O detail", exc_info=True)
        return {"status": "error", "msg": str(e)}
    except Exception as e:
        logger.error("file_write unexpected error for %s: %s", path, e)
        logger.debug("file_write exception detail", exc_info=True)
        return {"status": "error", "msg": str(e)}


def consume_file(dr: Optional[str], file: str) -> Optional[str]:
    """Lit et supprime un fichier temporaire, retourne son contenu.

    Utilisé pour consommer des fichiers de communication inter-processus
    (ex: _keyinfo, _intervene dans le répertoire de tâches).

    Args:
        dr: Répertoire contenant le fichier. Si None ou vide, retourne None.
        file: Nom du fichier à consommer.

    Returns:
        Le contenu du fichier s'il existait, None sinon.
    """
    if not dr:
        return None
    filepath = os.path.join(dr, file)
    if not os.path.exists(filepath):
        return None
    # Basic path validation: ensure the resolved path is still under dr
    resolved = os.path.abspath(filepath)
    if not resolved.startswith(os.path.abspath(dr)):
        logger.warning(
            "consume_file: path traversal detected — %s is outside %s",
            resolved,
            dr,
        )
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as f:
            content = f.read()
        os.remove(resolved)
        return content
    except (IOError, OSError) as e:
        logger.warning("consume_file: failed to read/remove %s: %s", resolved, e)
        return None

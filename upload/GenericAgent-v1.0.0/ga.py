"""ga.py — Module principal de l'agent GenericAgent.

Fournit les outils (code_run, file_patch, file_read, web_scan, etc.)
et le handler GenericAgentHandler pour la boucle agent_loop.

.. note::
   As of Phase 3 (task 3.1.1), the tool functions have been extracted into
   dedicated sub-modules under ``tools/``:

   * :mod:`tools.code_run`  — :func:`code_run` + security constants
   * :mod:`tools.file_ops`  — file I/O utilities
   * :mod:`tools.web_tools` — browser / web-scanning utilities

   This module re-exports the public API for backward compatibility so that
   existing ``from ga import code_run`` statements continue to work unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import traceback
import types
from typing import Any, Callable, Generator, Optional

# ══════════════════════════════════════════════════════════════════════════════
#  Re-exports from extracted sub-modules
# ══════════════════════════════════════════════════════════════════════════════
from tools.code_run import (
    code_run,
    DANGEROUS_SHELL_PATTERNS,
    ALLOW_DANGEROUS_SHELL,
    WORKSPACE_DIR,
    set_shell_confirm_callback,
    smart_format,
)
# NOTE: _driver and ALLOW_DANGEROUS_SHELL are mutable module-level state.
# We keep sub-module references so that attribute-setting on the ga module
# (e.g. ``ga.ALLOW_DANGEROUS_SHELL = True``) can be forwarded to the
# real location inside tools.code_run / tools.web_tools via __setattr__.
import tools.code_run as _code_run_mod
import tools.web_tools as _web_tools_mod
import tools.file_ops as _file_ops_mod
from tools.file_ops import (
    expand_file_refs,
    file_patch,
    file_read,
    file_write,
    consume_file,
    _read_dirs,
    _scan_files,
    log_memory_access,
)
from tools.web_tools import (
    web_scan,
    web_execute_js,
    first_init_driver,
    _driver,
    format_error,
)


def __getattr__(name: str) -> Any:
    """Forward attribute access for mutable module-level state to sub-modules.

    This allows ``ga.ALLOW_DANGEROUS_SHELL`` to read from
    ``tools.code_run.ALLOW_DANGEROUS_SHELL`` and ``ga._driver`` to read
    from ``tools.web_tools._driver``, ensuring that external code can
    access the current value even after it has been mutated inside the
    sub-module.
    """
    if name == "ALLOW_DANGEROUS_SHELL":
        return _code_run_mod.ALLOW_DANGEROUS_SHELL
    if name == "_driver":
        return _web_tools_mod._driver
    if name == "smart_format":
        # Prefer the code_run version (imported directly), but fall back
        return _code_run_mod.smart_format
    raise AttributeError(f"module 'ga' has no attribute {name!r}")


def __setattr__(name: str, value: Any) -> None:
    """Forward attribute-setting for mutable module-level state to sub-modules.

    This ensures that ``ga.ALLOW_DANGEROUS_SHELL = True`` propagates to
    ``tools.code_run.ALLOW_DANGEROUS_SHELL`` so the security check inside
    :func:`code_run` sees the updated value.  Both the sub-module AND the
    local module namespace are updated so that subsequent reads via
    ``ga.ALLOW_DANGEROUS_SHELL`` return the new value.
    """
    if name == "ALLOW_DANGEROUS_SHELL":
        _code_run_mod.ALLOW_DANGEROUS_SHELL = value
        # Also update the local binding so ``ga.ALLOW_DANGEROUS_SHELL`` sees it
        import builtins
        builtins.setattr(sys.modules[__name__], name, value)
    elif name == "_driver":
        _web_tools_mod._driver = value
        import builtins
        builtins.setattr(sys.modules[__name__], name, value)
    else:
        import builtins
        builtins.setattr(sys.modules[__name__], name, value)

# Guard against None stdout/stderr in headless/embedded environments
# (e.g. PyInstaller frozen apps, subprocess contexts)
# NOTE: These are moved into an explicit initialize() function to avoid
# side effects at import time.  Callers MUST call initialize() before
# using the module if they need stdout/stderr protection or sys.path setup.

_initialized: bool = False


def initialize() -> None:
    """Perform one-time environment setup for the ga module.

    This function **must** be called explicitly before using the module
    in environments where ``sys.stdout`` / ``sys.stderr`` may be ``None``
    (e.g. PyInstaller frozen apps).  It also ensures that the project
    root is on ``sys.path`` so that sibling packages are importable.

    The function is idempotent — calling it more than once is safe.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    if sys.stdout is None:  # type: ignore[comparison-overlap]
        import os as _os
        sys.stdout = open(_os.devnull, "w")  # type: ignore[assignment]
    if sys.stderr is None:  # type: ignore[comparison-overlap]
        import os as _os2
        sys.stderr = open(_os2.devnull, "w")  # type: ignore[assignment]

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)

from agent_loop import BaseHandler, StepOutcome, json_default

# Security: import SecurityError for disabling inline_eval mode
try:
    from agentmain.safe_eval import SecurityError
except ImportError:
    class SecurityError(Exception):
        """Fallback SecurityError when agentmain.safe_eval is not available."""

# Custom exceptions — imported lazily so that missing module never crashes startup
try:
    from exceptions import (
        FileOperationError,
        FilePatchError,
        FileReadError,
        FileWriteError,
        ShellSecurityError,
        BrowserNotAvailableError,
        WebError,
        ToolExecutionError,
        CodeExecutionError,
    )
except ImportError:
    # Graceful fallback: define lightweight stubs so that ``isinstance`` and
    # ``raise`` still work even if the exceptions package is absent.
    class _StubError(Exception):
        """Lightweight stand-in used when the real exceptions module is unavailable."""
        def __init__(self, message: str = "", **_: Any) -> None:
            super().__init__(message)
    FileOperationError = _StubError      # type: ignore[assignment,misc]
    FilePatchError = _StubError          # type: ignore[assignment,misc]
    FileReadError = _StubError           # type: ignore[assignment,misc]
    FileWriteError = _StubError          # type: ignore[assignment,misc]
    ShellSecurityError = _StubError      # type: ignore[assignment,misc]
    BrowserNotAvailableError = _StubError  # type: ignore[assignment,misc]
    WebError = _StubError                # type: ignore[assignment,misc]
    ToolExecutionError = _StubError      # type: ignore[assignment,misc]
    CodeExecutionError = _StubError      # type: ignore[assignment,misc]

script_dir: str = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════
__all__ = [
    "initialize",
    "code_run",
    "ask_user",
    "web_scan",
    "web_execute_js",
    "file_patch",
    "file_read",
    "file_write",
    "expand_file_refs",
    "smart_format",
    "format_error",
    "consume_file",
    "set_shell_confirm_callback",
    "GenericAgentHandler",
    "log_memory_access",
    "DANGEROUS_SHELL_PATTERNS",
    "ALLOW_DANGEROUS_SHELL",
    "WORKSPACE_DIR",
    "get_global_memory",
]

# ══════════════════════════════════════════════════════════════════════════════
#  Système de traduction i18n
# ══════════════════════════════════════════════════════════════════════════════
try:
    from i18n import t
except ImportError:
    def t(key: str, *args: Any, **kwargs: Any) -> str:
        """Fallback si le module i18n n'est pas disponible."""
        _fallback = {
            "error.unsupported_type": "Type non supporté : {0}",
            "error.timeout_forced_kill": "Délai dépassé — exécution forcée arrêtée",
            "error.user_forced_kill": "Arrêt forcé par l'utilisateur",
            "error.no_browser_tab": "Aucun onglet navigateur disponible. Consultez la mémoire L3 pour la cause.",
            "error.file_not_exist": "Le fichier n'existe pas",
            "error.old_content_empty": "old_content est vide, veuillez vérifier les arguments",
            "error.old_content_not_found": "Ancien bloc texte non trouvé. Conseil : utilisez file_read pour vérifier, puis patchez par petits segments.",
            "error.old_content_multiple": "Trouvé {0} correspondances. Fournissez un bloc plus spécifique.",
            "error.file_ref_not_found": "Fichier référencé introuvable : {0}",
            "error.line_out_of_range": "Numéro de ligne hors limites : {0} a {1} lignes, demandé {2}-{3}",
            "error.please_provide_input": "Veuillez fournir une entrée :",
            "error.ref_expand_failed": "Échec de l'expansion de la référence : {0}",
            "error.save_failed": "Échec de l'enregistrement, impossible d'écrire le fichier {0}",
            "error.no_content_found": "Aucun contenu trouvé. Placez-le dans des balises <file_content>...",
            "error.write_error": "Erreur d'écriture : {0}",
            "error.code_missing": "Code manquant. Utilisez un bloc de code ou l'argument 'script'.",
            "error.script_missing": "Script manquant. Utilisez un bloc ```javascript ou l'argument 'script'.",
            "error.key_missing": "Clé API manquante. Configurez mykey.py.",
            "action.partial_edit_success": "Modification partielle du fichier réussie",
            "action.file_saved_to": "Contenu complet sauvegardé dans {0}",
            "action.write_success": "{0} réussi ({1} octets)",
            "action.js_result": "Résultat JS",
        }
        msg = _fallback.get(key, key)
        if args:
            try: return msg.format(*args)
            except (IndexError, KeyError): return msg
        return msg

logger = logging.getLogger("ga")


def ask_user(question: str, candidates: Optional[list[str]] = None) -> dict[str, Any]:
    """Pose une question à l'utilisateur.

    Args:
        question: La question à poser.
        candidates: Liste d'options facultative.

    Returns:
        dict: Dictionnaire avec statut INTERRUPT et données de la question.
    """
    return {"status": "INTERRUPT", "intent": "HUMAN_INTERVENTION",
        "data": {"question": question, "candidates": candidates or []}}


class GenericAgentHandler(BaseHandler):
    """Bibliothèque d'outils Generic Agent.

    Les fonctions outils ont le préfixe do_ automatique.
    Le nom réel de l'outil n'a pas de préfixe.
    """

    def __init__(self, parent: Any, last_history: Optional[list] = None, cwd: str = './temp') -> None:
        """Initialise le handler d'agent.

        Args:
            parent: Objet parent (ex: agent principal) pour l'accès aux propriétés partagées.
            last_history: Historique des tours précédents à restaurer.
            cwd: Répertoire de travail courant pour les opérations de fichiers.
        """
        self.parent = parent
        self.working: dict[str, Any] = {}
        self.cwd = cwd;  self.current_turn: int = 0
        self.history_info: list[str] = last_history if last_history else []
        self.code_stop_signal: threading.Event = threading.Event()
        self._done_hooks: list[Any] = []

    def _get_abs_path(self, path: str) -> str:
        """Résout un chemin relatif en chemin absolu par rapport au cwd du handler.

        Args:
            path: Chemin relatif ou absolu à résoudre.

        Returns:
            str: Chemin absolu, ou chaîne vide si path est vide.
        """
        if not path: return ""
        return os.path.abspath(os.path.join(self.cwd, path))

    def _extract_code_block(self, response: Any, code_type: str) -> Optional[str]:
        """Extrait le dernier bloc de code d'un type donné depuis la réponse du LLM.

        Args:
            response: Réponse du LLM contenant potentiellement des blocs de code.
            code_type: Type de code à extraire ("python", "bash", "powershell", etc.).

        Returns:
            Le contenu du dernier bloc de code trouvé, ou None si aucun bloc ne correspond.
        """
        code_type = {'python':'python|py', 'powershell':'powershell|ps1|pwsh', 'bash':'bash|sh|shell'}.get(code_type, re.escape(code_type))
        matches = re.findall(rf"```(?:{code_type})\n(.*?)\n```", response.content, re.DOTALL)
        return matches[-1].strip() if matches else None

    def do_code_run(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Exécute un extrait de code.

        Limité en longueur, pas de données volumineuses dans le code.
        Utiliser file_read pour les grandes données.

        Args:
            args: Dictionnaire avec "type", "code"/"script", "timeout", "cwd", "inline_eval".
            response: Réponse du LLM (pour extraction de bloc de code).

        Yields:
            str: Messages de statut et sortie en temps réel.

        Returns:
            StepOutcome: Résultat de l'exécution.
        """
        code_type = args.get("type", "python")
        code = args.get("code") or args.get("script")
        if not code:
            code = self._extract_code_block(response, code_type)
            if not code: return StepOutcome("[Error] Code missing. Must use reply code block or 'script' arg.", next_prompt="\n")
        timeout = args.get("timeout", 60)
        raw_path = os.path.join(self.cwd, args.get("cwd", './'))
        cwd = os.path.normpath(os.path.abspath(raw_path))
        code_cwd = os.path.normpath(self.cwd)
        if code_type == 'python' and args.get("inline_eval"):
            # SECURITY: inline_eval mode is DISABLED — eval()/exec() on arbitrary
            # LLM-generated code is a critical RCE vector (CVE-class vulnerability).
            # If you need safe expression evaluation, use SafeExpressionEvaluator
            # from agentmain.safe_eval.py. For template rendering, use Jinja2
            # sandboxed templates.
            import warnings
            warnings.warn(
                "inline_eval is deprecated and disabled for security reasons. "
                "Use SafeExpressionEvaluator from agentmain.safe_eval for "
                "safe expression evaluation, or Jinja2 sandboxed templates.",
                DeprecationWarning,
                stacklevel=2,
            )
            raise SecurityError(
                "inline_eval mode is disabled for security reasons. "
                "Arbitrary eval()/exec() on LLM-generated code is a critical RCE vector. "
                "Use SafeExpressionEvaluator from agentmain.safe_eval for safe "
                "expression evaluation, or Jinja2 sandboxed templates. "
                "For full code execution, omit inline_eval and use the subprocess-based "
                "code_run path instead."
            )
        else: result = yield from code_run(code, code_type, timeout, cwd, code_cwd=code_cwd, stop_signal=self.code_stop_signal)
        next_prompt = self._get_anchor_prompt(skip=args.get('_index', 0) > 0)
        return StepOutcome(result, next_prompt=next_prompt)

    def do_ask_user(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Pose une question à l'utilisateur et attend sa réponse.

        Args:
            args: Dictionnaire avec "question" et "candidates" optionnel.
            response: Réponse du LLM (non utilisé ici).

        Yields:
            str: Message d'attente.

        Returns:
            StepOutcome: Avec les données de la question et should_exit=True.
        """
        question = args.get("question", t("error.please_provide_input"))
        candidates = args.get("candidates", [])
        result = ask_user(question, candidates)
        yield f"Waiting for your answer ...\n"
        return StepOutcome(result, next_prompt="", should_exit=True)

    def do_web_scan(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Récupère le contenu de la page courante et la liste des onglets.

        Peut aussi basculer d'onglet. Le HTML est simplifié, les barres
        latérales/éléments flottants peuvent être filtrés. Utiliser execute_js
        pour voir le contenu filtré.

        Args:
            args: Dictionnaire avec "tabs_only", "switch_tab_id", "text_only".
            response: Réponse du LLM (non utilisé ici).

        Yields:
            str: Informations sur les onglets et contenu HTML.

        Returns:
            StepOutcome: Résultat du scan web.
        """
        tabs_only = args.get("tabs_only", False)
        switch_tab_id = args.get("switch_tab_id", None)
        text_only = args.get("text_only", False)
        result = web_scan(tabs_only=tabs_only, switch_tab_id=switch_tab_id, text_only=text_only)
        content = result.pop("content", None)
        yield f'[Info] {str(result)}\n'
        if content: result = json.dumps(result, ensure_ascii=False, default=json_default) + f"\n```html\n{content}\n```"
        next_prompt = "\n"
        return StepOutcome(result, next_prompt=next_prompt)

    def do_web_execute_js(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Outil prioritaire pour le web.

        Exécute n'importe quel JS pour un contrôle *complet* du navigateur.
        Supporte la sauvegarde des résultats dans un fichier.

        Args:
            args: Dictionnaire avec "script", "switch_tab_id"/"tab_id",
                  "no_monitor", "save_to_file".
            response: Réponse du LLM (pour extraction de bloc JavaScript).

        Yields:
            str: Résultat formaté de l'exécution JS.

        Returns:
            StepOutcome: Résultat de l'exécution JavaScript.
        """
        script = args.get("script", "") or self._extract_code_block(response, "javascript")
        if not script: return StepOutcome("[Error] Script missing. Use ```javascript block or 'script' arg.", next_prompt="\n")
        abs_path = self._get_abs_path(script.strip())
        if os.path.isfile(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f: script = f.read()
        save_to_file = args.get("save_to_file", "")
        switch_tab_id = args.get("switch_tab_id") or args.get("tab_id")
        no_monitor = args.get("no_monitor", False)
        result = web_execute_js(script, switch_tab_id=switch_tab_id, no_monitor=no_monitor)
        if save_to_file and "js_return" in result:
            js_content = str(result["js_return"] or '')
            abs_path = self._get_abs_path(save_to_file)
            result["js_return"] = smart_format(js_content, max_str_len=170)
            try:
                with open(abs_path, 'w', encoding='utf-8') as f: f.write(str(js_content))
                result["js_return"] += f"\n\n[{t('action.file_saved_to', abs_path)}]"
            except (IOError, OSError):
                result['js_return'] += f"\n\n[{t('error.save_failed', abs_path)}]"
        show = smart_format(json.dumps(result, ensure_ascii=False, indent=2, default=json_default), max_str_len=300)
        logger.debug("Web Execute JS Result: %s", show)
        yield f"{t('action.js_result')}\n{show}\n"
        next_prompt = self._get_anchor_prompt(skip=args.get('_index', 0) > 0)
        result_str = json.dumps(result, ensure_ascii=False, default=json_default)
        return StepOutcome(smart_format(result_str, max_str_len=8000), next_prompt=next_prompt)

    def do_file_patch(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Applique un patch à un fichier en remplaçant un bloc de texte unique.

        Args:
            args: Dictionnaire avec "path", "old_content", "new_content".
            response: Réponse du LLM (non utilisé directement).

        Yields:
            str: Messages de statut pendant l'opération.

        Returns:
            StepOutcome: Résultat du patch.
        """
        path = self._get_abs_path(args.get("path", ""))
        yield f"[Action] Patching file: {path}\n"
        old_content = args.get("old_content", "")
        new_content = args.get("new_content", "")
        try: new_content = expand_file_refs(new_content, base_dir=self.cwd)
        except ValueError as e:
            yield f"[Status] ❌ {t('error.ref_expand_failed', e)}\n"
            return StepOutcome({"status": "error", "msg": str(e)}, next_prompt="\n")
        result = file_patch(path, old_content, new_content)
        yield f"\n{str(result)}\n"

        # Auto-observe memory writes for L1 sync + RAG indexing
        try:
            from memory.crystallization import MemoryWriteObserver
            _mem_observer = getattr(self.__class__, '_mem_observer', None)
            if _mem_observer is None:
                _mem_observer = MemoryWriteObserver()
                self.__class__._mem_observer = _mem_observer
            if '/memory/' in path or '\\memory\\' in path:
                obs_result = _mem_observer.on_memory_write(path)
                if obs_result.get("l1_synced") or obs_result.get("rag_indexed", 0) > 0:
                    yield f"[Auto] L1 synced={obs_result.get('l1_synced')}, RAG indexed={obs_result.get('rag_indexed', 0)} chunks\n"
        except Exception:
            logger.debug("Non-critical memory observation failed in file_patch", exc_info=True)

    def do_file_write(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Écrit du contenu dans un fichier.

        Pour le traitement de fichiers entiers en grande quantité.
        Pour les modifications fines, utiliser file_patch.
        Placer le contenu à écrire dans des balises <file_content> ou dans un bloc de code.

        Args:
            args: Dictionnaire avec "path", "mode" (overwrite/append/prepend).
            response: Réponse du LLM contenant le contenu à écrire.

        Yields:
            str: Messages de statut pendant l'opération.

        Returns:
            StepOutcome: Résultat de l'écriture.
        """
        path = self._get_abs_path(args.get("path", ""))
        mode = args.get("mode", "overwrite")  # overwrite/append/prepend
        action_str = {"prepend": "Prepending to", "append": "Appending to"}.get(mode, "Overwriting")
        yield f"[Action] {action_str} file: {os.path.basename(path)}\n"

        def extract_robust_content(text: str) -> Optional[str]:
            """Extrait le contenu des balises <file_content> ou d'un bloc de code."""
            tag = re.search(r"<file_content[^>]*>(.*)</file_content>", text, re.DOTALL)
            if tag: return tag.group(1).strip()
            s, e = text.find("```"), text.rfind("```")
            if -1 < s < e: return text[text.find("\n", s)+1 : e].strip()
            return None

        blocks = extract_robust_content(response.content)
        if not blocks:
            yield f"[Status] ❌ {t('error.no_content_found')}\n"
            return StepOutcome({"status": "error", "msg": "No content found. Put content inside <file_content>...</file_content> tags in your reply body before call file_write."}, next_prompt="\n")
        try:
            new_content = expand_file_refs(blocks, base_dir=self.cwd)
            if mode == "prepend":
                old = ""
                if os.path.exists(path):
                    with open(path, 'r', encoding="utf-8") as f: old = f.read()
                with open(path, 'w', encoding="utf-8") as f: f.write(new_content + old)
            else:
                with open(path, 'a' if mode == "append" else 'w', encoding="utf-8") as f: f.write(new_content)
            yield f"[Status] ✅ {t('action.write_success', mode.capitalize(), len(new_content))}\n"

            # Auto-observe memory writes for L1 sync + RAG indexing
            try:
                from memory.crystallization import MemoryWriteObserver
                _mem_observer = getattr(self.__class__, '_mem_observer', None)
                if _mem_observer is None:
                    _mem_observer = MemoryWriteObserver()
                    self.__class__._mem_observer = _mem_observer
                if '/memory/' in path or '\\memory\\' in path:
                    obs_result = _mem_observer.on_memory_write(path)
                    if obs_result.get("l1_synced") or obs_result.get("rag_indexed", 0) > 0:
                        yield f"[Auto] L1 synced={obs_result.get('l1_synced')}, RAG indexed={obs_result.get('rag_indexed', 0)} chunks\n"
            except Exception:
                logger.debug("Non-critical memory observation failed in file_write", exc_info=True)

            next_prompt = self._get_anchor_prompt(skip=args.get('_index', 0) > 0)
            return StepOutcome({"status": "success", 'writed_bytes': len(new_content)}, next_prompt=next_prompt)
        except (IOError, OSError) as e:
            logger.error("file_write I/O error for %s: %s", path, e)
            yield f"[Status] ❌ {t('error.write_error', str(e))}\n"
            return StepOutcome({"status": "error", "msg": str(e)}, next_prompt="\n")
        except Exception as e:
            logger.error("file_write unexpected error for %s: %s", path, e)
            yield f"[Status] ❌ {t('error.write_error', str(e))}\n"
            return StepOutcome({"status": "error", "msg": str(e)}, next_prompt="\n")

    def do_file_read(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Lit le contenu d'un fichier.

        Commence à la ligne `start`. Si `keyword` est fourni, retourne le
        contenu autour du premier mot-clé (insensible à la casse).

        Args:
            args: Dictionnaire avec "path", "start", "count", "keyword", "show_linenos".
            response: Réponse du LLM (non utilisé ici).

        Yields:
            str: Action de lecture en cours.

        Returns:
            StepOutcome: Contenu du fichier.
        """
        path = self._get_abs_path(args.get("path", ""))
        yield f"\n[Action] Reading file: {path}\n"
        start = args.get("start", 1)
        count = args.get("count", 200)
        keyword = args.get("keyword")
        show_linenos = args.get("show_linenos", True)
        result = file_read(path, start=start, keyword=keyword,
                           count=count, show_linenos=show_linenos)
        if show_linenos and not result.startswith("Error:"): result = '[Format : (numéro_ligne|)contenu]\n' + result
        if ' ... [TRUNCATED]' in result: result += '\n\n(Certaines lignes sont tronquées. Utilisez code_run pour le contenu complet)'
        result = smart_format(result, max_str_len=20000, omit_str='\n\n[omitted long content]\n\n')
        next_prompt = self._get_anchor_prompt(skip=args.get('_index', 0) > 0)
        log_memory_access(path)
        if 'memory' in path or 'sop' in path:
            next_prompt += "\n[SYSTEM TIPS] Lecture d'un fichier mémoire ou SOP. Si vous décidez de suivre le SOP, extrayez les points clés et mettez à jour la mémoire de travail."
        return StepOutcome(result, next_prompt=next_prompt)

    def _in_plan_mode(self) -> Optional[str]:
        """Vérifie si le handler est en mode plan et retourne le chemin du plan.

        Returns:
            Le chemin du fichier plan si en mode plan, None sinon.
        """
        return self.working.get('in_plan_mode')

    def _exit_plan_mode(self) -> None:
        """Sort du mode plan en supprimant la clé du dictionnaire de travail."""
        self.working.pop('in_plan_mode', None)

    def enter_plan_mode(self, plan_path: str) -> str:
        """Entre en mode plan avec un fichier plan spécifié.

        Augmente max_turns à 100 pour permettre des séquences longues.

        Args:
            plan_path: Chemin du fichier plan à suivre.

        Returns:
            str: Le chemin du fichier plan.
        """
        self.working['in_plan_mode'] = plan_path; self.max_turns = 100
        logger.info("Entered plan mode with plan file: %s", plan_path)
        return plan_path

    def _check_plan_completion(self) -> Optional[int]:
        """Vérifie le nombre de tâches restantes dans le fichier plan.

        Returns:
            Nombre de cases à cocher [ ] restantes, ou None si le plan n'est pas accessible.
        """
        if not os.path.isfile(p:=self._in_plan_mode() or ''): return None
        try: return len(re.findall(r'\[ \]', open(p, encoding='utf-8', errors='replace').read()))
        except (IOError, OSError): return None

    def do_update_working_checkpoint(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Définit les points clés à mémoriser temporairement pour la suite de la tâche.

        Also persists the checkpoint to disk so it survives crashes.

        Args:
            args: Dictionnaire avec "key_info" et "related_sop" optionnels.
            response: Réponse du LLM (non utilisé ici).

        Yields:
            str: Message de confirmation.

        Returns:
            StepOutcome: Confirmation de mise à jour.
        """
        key_info = args.get("key_info", "")
        related_sop = args.get("related_sop", "")
        if "key_info" in args: self.working['key_info'] = key_info
        if "related_sop" in args: self.working['related_sop'] = related_sop
        self.working['passed_sessions'] = 0

        # Auto-persist checkpoint to disk
        try:
            from memory.crystallization import save_working_checkpoint
            save_working_checkpoint(
                key_info=self.working.get('key_info', ''),
                related_sop=self.working.get('related_sop', ''),
            )
        except Exception:
            logger.debug("Failed to persist working checkpoint to disk", exc_info=True)

        yield f"[Info] Updated key_info and related_sop (checkpoint saved).\n"
        next_prompt = self._get_anchor_prompt(skip=args.get('_index', 0) > 0)
        return StepOutcome({"result": "working key_info updated"}, next_prompt=next_prompt)

    def do_no_tool(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Outil spécial, appelé automatiquement par le moteur.

        Ne pas inclure dans TOOLS_SCHEMA.
        Déclenché automatiquement quand le modèle n'appelle aucun outil dans un tour.
        La double confirmation est déclenchée uniquement quand la réponse contient
        presque uniquement <thinking>/<summary> et un gros bloc de code.

        Args:
            args: Dictionnaire vide (pas d'arguments).
            response: Réponse du LLM sans appel d'outil.

        Yields:
            str: Messages d'information ou d'avertissement.

        Returns:
            StepOutcome: La réponse du LLM ou un prompt de correction.
        """
        content = getattr(response, 'content', '') or ""
        thinking = getattr(response, 'thinking', '') or ""
        if not response or (not content.strip() and not thinking.strip()):
            yield "[Warn] LLM returned an empty response. Retrying...\n"
            return StepOutcome({}, next_prompt="[System] Blank response, regenerate and tooluse")
        if len(content) > 50 and ('!!!Error:' in content[-100:] or 'stream abnormally interrupted' in content[-100:].lower() or 'abnormally interrupted' in content[-100:]):
            return StepOutcome({}, next_prompt="[System] Incomplete response. Regenerate and tooluse.")
        if 'max_tokens !!!]' in content[-100:]:
            return StepOutcome({}, next_prompt="[System] max_tokens limit reached. Use multi small steps to do it.")

        if self._in_plan_mode() and any(kw in content for kw in ['task completed', 'all tasks completed', 'tâche terminée', 'toutes les tâches', '🏁', '任务完成']):
            if 'VERDICT' not in content and '[VERIFY]' not in content and 'verification agent' not in content and 'agent de vérification' not in content:
                yield "[Warn] Plan mode completion declaration intercepted.\n"
                return StepOutcome({}, next_prompt="⛔ [Verification required] You claimed completion in plan mode without executing [VERIFY]. Launch verification agent per plan_sop §4 first.")

        # 2. Détection d'un gros bloc de code sans appel d'outil
        # Caractéristique clé : exactement 1 gros bloc de code + le bloc se termine directement (rien après sauf des espaces)
        code_block_pattern = r"```[a-zA-Z0-9_]*\n[\s\S]{50,}?```"
        blocks = re.findall(code_block_pattern, content)
        if len(blocks) == 1:
            m = re.search(code_block_pattern, content)
            after_block = content[m.end():]
            if not after_block.strip():
                residual = content.replace(m.group(0), "")
                residual = re.sub(r"<thinking>[\s\S]*?</thinking>", "", residual, flags=re.IGNORECASE)
                residual = re.sub(r"<summary>[\s\S]*?</summary>", "", residual, flags=re.IGNORECASE)
                clean_residual = re.sub(r"\s+", "", residual)
                if len(clean_residual) <= 30:
                    yield "[Info] Detected large code block without tool call and no extra natural language. Requesting clarification.\n"
                    next_prompt = (
                        "[System] Large code block detected without tool call and no natural language explanation.\n"
                        "If this code needs to be executed, written to a file, or further analyzed, "
                        "reorganize your response and explicitly call the appropriate tool "
                        "(e.g., code_run, file_write, file_patch, etc.);\n"
                        "If you are just showing or explaining code, add a natural language description "
                        "and clarify whether additional actions are needed."
                    )
                    return StepOutcome({}, next_prompt=next_prompt)

        if self._in_plan_mode():
            remaining = self._check_plan_completion()
            if remaining == 0:
                self._exit_plan_mode(); yield "[Info] Plan completed: 0 remaining tasks in plan.md, exiting plan mode.\n"

        yield "[Info] Final response to user.\n"
        return StepOutcome(response, next_prompt=None)

    def do_start_long_term_update(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Déclenche la consolidation de mémoire à long terme après une tâche importante.

        Called when the agent thinks important information should be memorized
        after task completion.

        Args:
            args: Dictionnaire vide (pas d'arguments).
            response: Réponse du LLM.

        Yields:
            str: Message de démarrage de la consolidation.

        Returns:
            StepOutcome: Prompt de distillation et contenu du SOP mémoire.
        """
        prompt = '''### [Distill Experience] Since you think this task has important information to memorize, extract [factually verified and long-term valid] environment facts, user preferences, and important steps from the most recent task to update memory.
This tool marks the start of the consolidation process. If already updating memory or nothing worth memorizing, ignore this call.
**If there is no verified, future-useful information, ignore this call!**
**Only extract action-verified information**:
- **Environment facts** (paths/credentials/config) → `file_patch` update L2, sync L1
- **Complex task experience** (key pitfalls/prerequisites/important steps) → L3 concise SOP (only note core points from multiple retries)
**Forbidden**: temporary variables, specific reasoning process, unverified info, common knowledge, easily reproducible details, done-but-unverified information
**Operation**: strictly follow the L0 memory update SOP. `file_read` current → judge type → minimal update → skip if nothing new, ensure minimal local modification to memory.\n
''' + get_global_memory()
        yield "[Info] Start distilling good memory for long-term storage.\n"
        path = './memory/memory_management_sop.md'
        if os.path.exists(path): result = '[Auto-reading L0 content:]\n' + file_read(path, show_linenos=False)
        else: result = "Memory Management SOP not found. Do not update memory."
        return StepOutcome(result, next_prompt=prompt)

    def do_skill_search(self, args: dict[str, Any], response: Any) -> Generator[str, None, StepOutcome]:
        """Search 105K+ skill cards for relevant procedures and SOPs.

        Queries the skill search API for skills matching the query,
        optionally filtered by category. Returns formatted results
        that the LLM can use to find relevant approaches for the
        current task.

        Args:
            args: Dictionnaire avec "query", optional "category", "top_k".
            response: Réponse du LLM.

        Yields:
            str: Action message.

        Returns:
            StepOutcome: Formatted search results.
        """
        query = args.get("query", "")
        category = args.get("category")
        top_k = args.get("top_k", 5)

        if not query:
            return StepOutcome(
                {"status": "error", "msg": "query parameter is required"},
                next_prompt="\n",
            )

        yield f"[Action] Searching skills: {query[:80]}\n"

        try:
            import sys
            skill_search_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "skill_search")
            if skill_search_dir not in sys.path:
                sys.path.insert(0, skill_search_dir)
            from skill_search import search, detect_environment, SkillSearchError

            env = detect_environment()
            results = search(query, env=env, category=category, top_k=top_k)

            if not results:
                yield "[Status] No skills found matching query.\n"
                return StepOutcome(
                    {"status": "no_results", "count": 0},
                    next_prompt="\nNo matching skills found. Try a different query or proceed without skill reference.\n",
                )

            # Format results for LLM consumption
            formatted_lines = [f"Found {len(results)} relevant skills:\n"]
            for i, r in enumerate(results, 1):
                s = r.skill
                score_str = f"score={r.final_score:.2f}" if r.final_score else ""
                formatted_lines.append(
                    f"{i}. **{s.name}** ({s.category}) {score_str}\n"
                    f"   {s.one_line_summary or s.description[:120]}\n"
                    f"   Quality: {s.quality_score:.0f}/10 | Tags: {', '.join(s.tags[:5])}"
                )
                if s.github_url:
                    formatted_lines.append(f"   GitHub: {s.github_url}")
                if r.warnings:
                    formatted_lines.append(f"   Warnings: {', '.join(r.warnings[:3])}")

            formatted = "\n".join(formatted_lines)
            yield f"[Status] Found {len(results)} skills\n"
            return StepOutcome(
                {"status": "success", "count": len(results)},
                next_prompt=f"\n[Skill Search Results]\n{formatted}\n\nConsider using relevant skills for the current task.\n",
            )

        except SkillSearchError as exc:
            yield f"[Status] Skill search API error: {exc}\n"
            return StepOutcome(
                {"status": "error", "msg": str(exc)},
                next_prompt="\nSkill search failed. Proceed without skill reference.\n",
            )
        except ImportError:
            yield "[Status] Skill search module not available\n"
            return StepOutcome(
                {"status": "unavailable", "msg": "skill_search module not installed"},
                next_prompt="\nSkill search not available. Proceed without.\n",
            )
        except Exception as exc:
            yield f"[Status] Skill search error: {exc}\n"
            return StepOutcome(
                {"status": "error", "msg": str(exc)},
                next_prompt="\n",
            )

    def _get_anchor_prompt(self, skip: bool = False) -> str:
        """Construit le prompt d'ancrage avec la mémoire de travail et l'historique.

        Args:
            skip: Si True, retourne un prompt minimal (saut d'ancrage).

        Returns:
            str: Le prompt d'ancrage pour le LLM.
        """
        if skip: return "\n"
        h_str = "\n".join(self.history_info[-40:])
        prompt = f"\n### [WORKING MEMORY]\n<history>\n{h_str}\n</history>"
        prompt += f"\nCurrent turn: {self.current_turn}\n"
        if self.working.get('key_info'): prompt += f"\n<key_info>{self.working.get('key_info')}</key_info>"
        if self.working.get('related_sop'): prompt += f"\nIf unclear, re-read {self.working.get('related_sop')}"
        if getattr(self.parent, 'verbose', False):
            logger.debug("Anchor prompt: %s", prompt[:500])
        return prompt

    def turn_end_callback(self, response: Any, tool_calls: list, tool_results: list,
                          turn: int, next_prompt: str, exit_reason: dict) -> str:
        """Callback appelé à la fin de chaque tour de conversation.

        Gère la détection des résumés, les avertissements de tours consécutifs,
        l'injection de messages maîtres et les hooks de fin de tour.

        Args:
            response: Réponse du LLM pour ce tour.
            tool_calls: Liste des appels d'outils effectués.
            tool_results: Liste des résultats d'outils.
            turn: Numéro du tour actuel.
            next_prompt: Prompt pour le tour suivant.
            exit_reason: Raison de sortie éventuelle.

        Returns:
            str: Le prompt modifié pour le tour suivant.
        """
        _c = re.sub(r'```.*?```|<thinking>.*?</thinking>', '', response.content, flags=re.DOTALL)
        rsumm = re.search(r"<summary>(.*?)</summary>", _c, re.DOTALL)
        if rsumm: summary = rsumm.group(1).strip()
        else:
            tc = tool_calls[0]; tool_name, tool_args = tc['tool_name'], tc['args']   # at least one because no_tool
            clean_args = {k: v for k, v in tool_args.items() if not k.startswith('_')}
            summary = f"Called tool {tool_name}, args: {clean_args}"
            if tool_name == 'no_tool': summary = "Answered user question directly"
            next_prompt += "\n[DANGER] Missing <summary>. You must always include a <summary> with a concise single-line summary in each response!"
        summary = smart_format(summary, max_str_len=100)
        self.history_info.append(f'[Agent] {summary}')
        if turn % 65 == 0 and 'plan' not in str(self.working.get('related_sop')):
            next_prompt += f"\n\n[DANGER] Running for {turn} consecutive turns. You must summarize and ask_user, no more retries allowed."
        elif turn % 7 == 0:
            next_prompt += f"\n\n[DANGER] {turn} consecutive turns. No ineffective retries. Without progress, switch strategy: 1. Explore physical boundaries 2. Ask user for help. Use update_working_checkpoint if needed."
        elif turn % 10 == 0: next_prompt += get_global_memory()

        if (_plan := self._in_plan_mode()) and turn >= 10 and turn % 5 == 0:
            next_prompt = f"[Plan Hint] You are in plan mode. Must file_read({_plan}) to confirm current step.\n\n" + next_prompt
        if _plan and turn >= 90: next_prompt += f"\n\n[DANGER] Plan mode running for {turn} turns, limit reached. Must ask_user to report progress and confirm continuation."

        injkeyinfo = consume_file(self.parent.task_dir, '_keyinfo')
        injprompt = consume_file(self.parent.task_dir, '_intervene')
        if injkeyinfo: self.working['key_info'] = self.working.get('key_info', '') + f"\n[MASTER] {injkeyinfo}"
        if injprompt: next_prompt += f"\n\n[MASTER] {injprompt}\n"
        for hook in getattr(self.parent, '_turn_end_hooks', {}).values(): hook(locals())  # current readonly
        return next_prompt


def get_global_memory() -> str:
    """Construit le prompt de mémoire globale avec les insights et la structure.

    Lit les fichiers de mémoire globale (global_mem_insight.txt et
    insight_fixed_structure.txt) et les formate en prompt pour le LLM.

    Returns:
        str: Prompt formaté avec la mémoire globale, ou chaîne vide si les fichiers n'existent pas.
    """
    prompt = "\n"
    try:
        _lang = os.environ.get('GA_LANG', '').strip().lower()
        if _lang not in ('fr', 'en', 'zh'):
            try:
                import mykey
                _lang = getattr(mykey, 'GA_LANG', 'fr').strip().lower()
            except ImportError:
                _lang = 'fr'
        suffix = '_en' if _lang == 'en' else ('_fr' if _lang == 'fr' else '')
        with open(os.path.join(script_dir, 'memory/global_mem_insight.txt'), 'r', encoding='utf-8', errors='replace') as f: insight = f.read()
        with open(os.path.join(script_dir, f'assets/insight_fixed_structure{suffix}.txt'), 'r', encoding='utf-8') as f: structure = f.read()
        prompt += f'cwd = {os.path.join(script_dir, "temp")} (./)\n'
        prompt += f"\n[Memory] (../memory)\n"
        prompt += structure + '\n../memory/global_mem_insight.txt:\n'
        prompt += insight + "\n"
    except FileNotFoundError:
        logger.debug("Global memory files not found, skipping")
    return prompt

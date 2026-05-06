"""Core Shadow Agent class — thin orchestrator for the agent runtime.

This module defines :class:`GenericAgent`, the primary orchestrator that
delegates to extracted sub-modules:

- :mod:`agentmain.agent.llm_manager` — LLM session management
- :mod:`agentmain.agent.task_queue` — Task queue and run loop

Backward compatibility: the legacy name :data:`GeneraticAgent` is retained
as an alias so that existing ``from agentmain import GeneraticAgent``
imports continue to work unchanged.
"""

from __future__ import annotations

import os
import queue
import signal
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("agentmain")

# ---------------------------------------------------------------------------
# Project-level imports
# ---------------------------------------------------------------------------

from llmcore import reload_mykeys
from ga import GenericAgentHandler, smart_format, get_global_memory, format_error, consume_file, initialize as _ga_initialize

from exceptions import AgentError, MaxTurnsExceededError, SessionConfigError
from config import get_agent_config

# ---------------------------------------------------------------------------
# Internal package imports
# ---------------------------------------------------------------------------

from agentmain.prompts import script_dir, TOOLS_SCHEMA, load_tool_schema, get_system_prompt, get_merged_tool_schemas
from agentmain.slash import handle_slash_cmd, _get_resume_prompt
from agentmain.agent.llm_manager import LLMManager
from agentmain.agent.task_queue import TaskQueue


# ---------------------------------------------------------------------------
# GenericAgent
# ---------------------------------------------------------------------------


class GenericAgent:
    """Core agent runtime — thin orchestrator delegating to sub-modules.

    A :class:`GenericAgent` instance owns an :class:`LLMManager`, a
    :class:`TaskQueue`, and the shared history list.  Call :meth:`put_task`
    to enqueue a user query and receive a :class:`queue.Queue` on which
    incremental and final results will be published.

    Attributes
    ----------
    lock : threading.Lock
        Guard for thread-sensitive state.
    task_dir : str | None
        Working directory for file-based I/O (task mode).
    history : list[str]
        Running conversation history.
    is_running : bool
        Whether the agent loop is currently processing a task.
    stop_sig : bool
        Flag to signal the agent loop to abort.
    _shutdown_event : threading.Event
        Event that, when set, signals the main loop to exit gracefully.
    llm_no : int
        Index of the currently selected LLM client.
    inc_out : bool
        Whether to emit incremental output (``True`` in interactive mode).
    handler : GenericAgentHandler | None
        The handler for the current / most recent agent run.
    verbose : bool
        Enable verbose debug output.
    """

    def __init__(self) -> None:
        # First-launch consent check (Task 8.2.1)
        self._check_consent()

        # Ensure ga module is initialized (stdout/stderr guards, sys.path)
        _ga_initialize()
        os.makedirs(os.path.join(script_dir, "temp"), exist_ok=True)
        self.lock: threading.Lock = threading.Lock()
        self.task_dir: Optional[str] = None
        self.history: List[str] = []
        self._shutdown_event: threading.Event = threading.Event()
        self.inc_out: bool = False
        self.handler: Optional[GenericAgentHandler] = None
        self.verbose: bool = True

        # ── Sub-modules (extracted from the monolith) ──────────────────
        self._llm_mgr = LLMManager()
        self._task_queue = TaskQueue(self)

        # Initialise LLM sessions
        self._llm_mgr.load_llm_sessions()
        self._load_plugins()
        self._connect_mcp_servers()

        # v0.6.0 "Big Tech Monster" module initializations
        self._chroma_store = None           # memory.chroma_store
        self._guardrail_manager = None      # agentmain.guardrails
        self._extension_manager = None      # agentmain.extensions
        # ContextEngine is eagerly initialized (B4: auto-activation + compaction)
        try:
            from agentmain.extensions import ContextEngine
            self._context_engine = ContextEngine()
            logger.info("ContextEngine eagerly initialized")
        except Exception as exc:
            logger.debug("ContextEngine eager init skipped: %s", exc)
            self._context_engine = None
        self._closed_learning = None        # agentmain.closed_learning
        self._agent_handoff = None          # agentmain.handoffs
        self._fastmcp_server = None         # mcp.fastmcp
        self._browser_session = None        # agentmain.browser_intel
        self._voice_pipeline = None         # agentmain.voice_avatar
        self._avatar_controller = None      # agentmain.voice_avatar

    # ── Convenience properties delegating to LLMManager ────────────────

    @property
    def llmclients(self) -> List[Any]:
        return self._llm_mgr.llmclients

    @llmclients.setter
    def llmclients(self, value: List[Any]) -> None:
        self._llm_mgr.llmclients = value

    @property
    def llmclient(self) -> Any:
        return self._llm_mgr.llmclient

    @llmclient.setter
    def llmclient(self, value: Any) -> None:
        self._llm_mgr.llmclient = value

    @property
    def llm_no(self) -> int:
        return self._llm_mgr.llm_no

    @llm_no.setter
    def llm_no(self, value: int) -> None:
        self._llm_mgr.llm_no = value

    @property
    def task_queue(self) -> queue.Queue:
        return self._task_queue.task_queue

    @task_queue.setter
    def task_queue(self, value: queue.Queue) -> None:
        self._task_queue.task_queue = value

    @property
    def is_running(self) -> bool:
        return self._task_queue.is_running

    @is_running.setter
    def is_running(self, value: bool) -> None:
        self._task_queue.is_running = value

    @property
    def stop_sig(self) -> bool:
        return self._task_queue.stop_sig

    @stop_sig.setter
    def stop_sig(self, value: bool) -> None:
        self._task_queue.stop_sig = value

    # ── Plugin loading ────────────────────────────────────────────────

    def _load_plugins(self) -> None:
        """Auto-discover and load tool plugins from the plugins directory."""
        try:
            from tools.registry import get_registry
            registry = get_registry()
            plugin_dir = os.path.join(script_dir, "plugins", "tools")
            count = registry.load_plugins(plugin_dir)
            if count > 0:
                logger.info("Loaded %d tool plugins", count)
        except Exception as exc:
            logger.debug("Plugin loading skipped: %s", exc)

    def _connect_mcp_servers(self) -> None:
        """Auto-connect to MCP servers defined in mcp_config.json."""
        try:
            from mcp.client import load_mcp_config, connect_mcp_server
            config_path = os.path.join(script_dir, "mcp_config.json")
            if os.path.exists(config_path):
                servers = load_mcp_config(config_path)
                connected = 0
                for server_config in servers:
                    try:
                        conn = connect_mcp_server(server_config)
                        if conn and conn.status.value == "connected":
                            connected += 1
                            logger.info(
                                "MCP server '%s' connected (%d tools)",
                                server_config.name,
                                len(conn.tools),
                            )
                    except Exception as exc:
                        logger.warning(
                            "MCP server '%s' connection failed: %s",
                            server_config.name, exc,
                        )
                if connected > 0:
                    logger.info("Connected %d/%d MCP servers", connected, len(servers))
        except Exception as exc:
            logger.debug("MCP auto-connect skipped: %s", exc)

    # ── LLM session management (delegates to LLMManager) ───────────────

    MAX_HISTORY_EXCHANGES: int = 50

    def load_llm_sessions(self) -> None:
        """Reload LLM sessions — delegates to :class:`LLMManager`."""
        self._llm_mgr.load_llm_sessions()

    def next_llm(self, n: int = -1) -> None:
        """Switch to the next (or specified) LLM client — delegates to :class:`LLMManager`."""
        self._llm_mgr.next_llm(n)

    def list_llms(self) -> List[Tuple[int, str, bool]]:
        """Return a summary of available LLM backends — delegates to :class:`LLMManager`."""
        return self._llm_mgr.list_llms()

    def get_llm_name(self, b: Any = None, model: bool = False) -> str:
        """Return a human-readable name for an LLM client — delegates to :class:`LLMManager`."""
        return self._llm_mgr.get_llm_name(b, model)

    # ── Task lifecycle (delegates to TaskQueue) ────────────────────────

    def abort(self) -> None:
        """Signal the running agent loop to stop — delegates to :class:`TaskQueue`."""
        self._task_queue.abort()

    def shutdown(self, timeout: float = 30.0) -> None:
        """Request a graceful shutdown — delegates to :class:`TaskQueue`."""
        self._task_queue.shutdown(timeout)

    def install_signal_handlers(self) -> None:
        """Install SIGINT/SIGTERM handlers that trigger graceful shutdown."""
        agent = self

        def _handle_signal(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received %s — initiating graceful shutdown", sig_name)
            agent.shutdown()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def put_task(
        self,
        query: str,
        source: str = "user",
        images: Optional[List[str]] = None,
    ) -> queue.Queue:
        """Enqueue a task — delegates to :class:`TaskQueue`."""
        return self._task_queue.put_task(query, source, images)

    # ── Slash command handling ────────────────────────────────────────

    @staticmethod
    def _build_resume_prompt() -> str:
        """Return the prompt text used by the ``/resume`` command."""
        return _get_resume_prompt()

    def _handle_slash_cmd(
        self, raw_query: str, display_queue: queue.Queue
    ) -> Optional[str]:
        """Process slash commands before they reach the LLM."""
        return handle_slash_cmd(self, raw_query, display_queue)

    # ── Main run loop (delegates to TaskQueue) ────────────────────────

    def run(self) -> None:
        """Consume tasks and execute them — delegates to :class:`TaskQueue`."""
        self._task_queue.run()

    # ── v0.6.0 Lazy-initialization properties ───────────────────────────

    @property
    def chroma_store(self):
        """ChromaDB-backed memory store (lazy init)."""
        if self._chroma_store is None:
            from memory.chroma_store import ChromaMemoryStore
            self._chroma_store = ChromaMemoryStore()
        return self._chroma_store

    @property
    def guardrail_manager(self):
        """Centralized input/output guardrail manager."""
        if self._guardrail_manager is None:
            from agentmain.guardrails import GuardrailManager
            self._guardrail_manager = GuardrailManager()
            self._guardrail_manager.setup_defaults()
        return self._guardrail_manager

    @property
    def extension_manager(self):
        """Extension lifecycle manager."""
        if self._extension_manager is None:
            from agentmain.extensions import ExtensionManager
            self._extension_manager = ExtensionManager()
        return self._extension_manager

    @property
    def context_engine(self):
        """Context window manager with compaction (eagerly initialized in __init__)."""
        if self._context_engine is None:
            try:
                from agentmain.extensions import ContextEngine
                self._context_engine = ContextEngine()
                logger.info("ContextEngine lazy-initialized (fallback)")
            except Exception as exc:
                logger.debug("ContextEngine lazy-init failed: %s", exc)
        return self._context_engine

    @property
    def closed_learning(self):
        """Closed Learning Loop (Discover→Execute→Reflect→Codify→Improve)."""
        if self._closed_learning is None:
            from agentmain.closed_learning import ClosedLearningLoop
            self._closed_learning = ClosedLearningLoop(agent=self)
        return self._closed_learning

    @property
    def agent_handoff(self):
        """Multi-agent handoff manager."""
        if self._agent_handoff is None:
            from agentmain.handoffs import AgentHandoff
            self._agent_handoff = AgentHandoff()
        return self._agent_handoff

    @property
    def fastmcp_server(self):
        """FastMCP server for exposing agent capabilities via MCP protocol."""
        if self._fastmcp_server is None:
            from mcp.fastmcp import FastMCP
            self._fastmcp_server = FastMCP("genericagent", version="0.6.0")
        return self._fastmcp_server

    @property
    def browser_session(self):
        """Persistent browser session (lazy init)."""
        if self._browser_session is None:
            from agentmain.browser_intel import BrowserSession
            self._browser_session = BrowserSession()
        return self._browser_session

    @property
    def voice_pipeline(self):
        """Voice STT/TTS pipeline (lazy init)."""
        return self._voice_pipeline

    @property
    def avatar_controller(self):
        """VRM/VRoid avatar controller (lazy init)."""
        return self._avatar_controller

    # ── v0.6.0 Helper methods ─────────────────────────────────────────────

    def enable_voice(self, stt_provider="google", tts_provider="google", api_key=""):
        """Enable the voice pipeline with specified providers."""
        from agentmain.voice_avatar import VoicePipeline, STTProvider, TTSProvider
        self._voice_pipeline = VoicePipeline(
            stt_provider=STTProvider(stt_provider),
            tts_provider=TTSProvider(tts_provider),
            api_key=api_key,
        )
        return self._voice_pipeline

    def enable_avatar(self, avatar_path=""):
        """Enable the avatar controller with a VRM file."""
        from agentmain.voice_avatar import AvatarController
        self._avatar_controller = AvatarController(avatar_path=avatar_path)
        return self._avatar_controller

    def build_state_graph(self, state_schema=None, reducers=None):
        """Build a new StateGraph for structured agent execution."""
        from engine.state_graph import StateGraph, last_value
        if state_schema is None:
            from typing import TypedDict
            class AgentState(TypedDict):
                messages: list
                next_action: str
            state_schema = AgentState
            reducers = reducers or {"messages": last_value, "next_action": last_value}
        return StateGraph(state_schema=state_schema, reducers=reducers)

    def validate_input(self, text):
        """Validate user input through all guardrails."""
        return self.guardrail_manager.validate_input(text)

    def validate_output(self, text):
        """Validate agent output through all guardrails."""
        return self.guardrail_manager.validate_output(text)

    def search_memory(self, query, domain=None, n_results=5):
        """Search agent memory with input sanitization."""
        if not query or not isinstance(query, str):
            return []
        # Strip whitespace first, then limit query length to 500 chars
        sanitized = query.strip()[:500]
        if not sanitized:
            return []
        if domain:
            coll = self.chroma_store.collection_for_domain(domain)
        else:
            coll = self.chroma_store.get_or_create_collection("general")
        return coll.query(query_texts=[sanitized], n_results=n_results)

    def register_mcp_tool(self, name=None, description=None):
        """Decorator to register a function as an MCP tool."""
        return self.fastmcp_server.tool(name=name, description=description)

    def create_flow(self, name="untitled", description=""):
        """Create a new agent flow (Langflow-inspired)."""
        from agentmain.flow import Flow
        return Flow(name=name, description=description)

    # ── Context compaction (B4) ────────────────────────────────────────────

    def _check_context_compaction(self) -> None:
        """Check if context usage exceeds 70% of context window and trigger compaction.

        This method should be called after each agent turn. If the current
        context exceeds the threshold, it summarizes old exchanges into a
        compact block while preserving the most recent tool_results intact.
        """
        if self._context_engine is None:
            return
        try:
            # Build message list from history for token estimation
            messages = [{"role": "user" if line.startswith("[USER]") else "assistant",
                         "content": line}
                        for line in self.history if line.strip()]
            total_tokens = self._context_engine.estimate_tokens(
                "\n".join(line for line in self.history if line.strip())
            )
            # Check against 70% threshold (context_win = max_context_tokens)
            threshold = int(self._context_engine.max_context_tokens * 0.70)
            if self._context_engine.should_compact(total_tokens):
                logger.info(
                    "Context compaction triggered: %d tokens >= %d threshold",
                    total_tokens, threshold,
                )
                compacted = self._context_engine.compact(
                    messages, strategy="summarize_old"
                )
                # Rebuild history from compacted messages
                self.history = [
                    f"[USER]: {m['content']}" if m['role'] == 'user'
                    else f"[Agent] {m['content']}"
                    for m in compacted if m.get('content', '').strip()
                ]
                logger.info(
                    "Context compacted: %d messages remaining",
                    len(self.history),
                )
        except Exception as exc:
            logger.debug("Context compaction check failed: %s", exc)

    # ── First-launch consent (Task 8.2.1) ──────────────────────────────────

    _CONSENT_DIR = os.path.join(os.path.expanduser("~"), ".genericagent")
    _CONSENT_FILE = os.path.join(_CONSENT_DIR, "consent_given")
    _CONSENT_TEXT = (
        "=== GenericAgent — Data & Privacy Consent ===\n"
        "\n"
        "GenericAgent processes your messages through LLM providers (Anthropic, "
        "OpenAI, etc.) to generate responses. Here is what happens with your data:\n"
        "\n"
        "1. MESSAGES: Your chat messages are sent to the configured LLM provider "
        "for processing. They are subject to the provider's data policy.\n"
        "2. LOCAL STORAGE: Conversation history, working memory, and settings are "
        "stored locally on your device in ~/.genericagent/.\n"
        "3. CREDENTIALS: API keys are stored securely in your OS keyring (or "
        "encrypted locally as fallback).\n"
        "4. NO TELEMETRY: GenericAgent does NOT send usage data, crash reports, "
        "or analytics to any third party by default.\n"
        "5. LOGS: Local log files may contain truncated message previews. API keys "
        "are automatically redacted from all log output.\n"
        "\n"
        "By proceeding, you acknowledge the above and consent to the processing "
        "of your data as described.\n"
        "===============================================\n"
    )

    @classmethod
    def _check_consent(cls) -> None:
        """Check if the user has given first-launch consent.

        If ``~/.genericagent/consent_given`` does not exist, display the
        consent text and require the user to accept before proceeding.
        The consent timestamp is stored in the file.

        Raises:
            SystemExit: If the user declines consent (in non-interactive mode)
                or if consent cannot be obtained.
        """
        if os.path.isfile(cls._CONSENT_FILE):
            return

        # Ensure the directory exists
        os.makedirs(cls._CONSENT_DIR, exist_ok=True)

        # Non-interactive (headless / CI): auto-accept with a warning
        if not os.isatty(0):
            logger.warning(
                "First launch in non-interactive mode — auto-accepting consent. "
                "Create %s manually to suppress this warning.",
                cls._CONSENT_FILE,
            )
            cls._write_consent()
            return

        # Interactive: display consent and ask for acceptance
        print(cls._CONSENT_TEXT)
        try:
            response = input("Do you accept? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nConsent declined. Exiting.")
            raise SystemExit(1)

        if response in ("yes", "y", "oui", "o"):
            cls._write_consent()
            logger.info("User consent recorded at %s", cls._CONSENT_FILE)
        else:
            print("Consent declined. GenericAgent cannot proceed without consent.")
            raise SystemExit(1)

    @classmethod
    def _write_consent(cls) -> None:
        """Write the consent timestamp to the consent file."""
        import datetime
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with open(cls._CONSENT_FILE, "w", encoding="utf-8") as f:
                f.write(f"consent_given={timestamp}\n")
            os.chmod(cls._CONSENT_FILE, 0o600)
        except OSError as exc:
            logger.warning("Could not write consent file: %s", exc)


# Backward-compatible alias — other modules import ``GeneraticAgent``
# DEPRECATED: This alias will be removed in v1.0. Use GenericAgent instead.
import warnings as _warnings


class _DeprecatedAlias:
    """Descriptor that emits a DeprecationWarning when accessed."""

    def __init__(self, real_class):
        self._real_class = real_class

    def __getattr__(self, name):
        # Skip dunder methods to avoid warning spam
        if name.startswith('__') and name.endswith('__'):
            return getattr(self._real_class, name)
        _warnings.warn(
            f"'{name}' is accessed via deprecated alias. Use 'GenericAgent' directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self._real_class, name)

    def __call__(self, *args, **kwargs):
        _warnings.warn(
            "GeneraticAgent is deprecated and will be removed in v1.0. "
            "Use GenericAgent instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._real_class(*args, **kwargs)

    def __instancecheck__(self, instance):
        return isinstance(instance, self._real_class)

    def __subclasscheck__(self, subclass):
        return issubclass(subclass, self._real_class)


GeneraticAgent = _DeprecatedAlias(GenericAgent)

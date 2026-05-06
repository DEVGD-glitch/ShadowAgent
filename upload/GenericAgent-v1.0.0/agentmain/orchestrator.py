"""agentmain/orchestrator.py — Multi-Agent Orchestration for GenericAgent.

Provides the :class:`AgentOrchestrator` that manages multiple specialized
sub-agents, routes tasks to the appropriate specialist, and coordinates
their interactions.  Inspired by OpenAI Agents SDK (handoffs) and CrewAI
(role-based collaboration).

Architecture
------------
The orchestrator uses a **specialist handoff** pattern:

1. A **coordinator** agent receives the user's request.
2. The coordinator analyzes the task and decides which specialist(s) to invoke.
3. Each specialist executes its portion using a restricted tool set.
4. Results are collected and synthesized by the coordinator.

Specialist Types
----------------
- **CoderAgent** — Code generation, debugging, refactoring
- **ResearchAgent** — Web search, documentation lookup, knowledge retrieval
- **AnalystAgent** — Data analysis, charting, statistics
- **WriterAgent** — Content creation, editing, summarization
- **SystemAgent** — File operations, shell commands, system management

Usage
-----
::

    from agentmain.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    result = orchestrator.delegate("Analyze the sales data and create a chart")
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("agentmain.orchestrator")


# ══════════════════════════════════════════════════════════════════════════════
#  Specialist profiles
# ══════════════════════════════════════════════════════════════════════════════


class SpecialistType(Enum):
    """Types of specialist agents."""

    CODER = "coder"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    SYSTEM = "system"
    COORDINATOR = "coordinator"


@dataclass
class SpecialistProfile:
    """Profile for a specialist sub-agent.

    Attributes
    ----------
    name : str
        Unique name for this specialist.
    role : SpecialistType
        The specialist's role type.
    system_prompt : str
        System prompt that defines the specialist's behavior.
    allowed_tools : list[str]
        Tools this specialist is allowed to use.  Empty means all tools.
    description : str
        Human-readable description of the specialist's capabilities.
    max_turns : int
        Maximum turns for this specialist.
    """

    name: str
    role: SpecialistType
    system_prompt: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    description: str = ""
    max_turns: int = 20


# ── Predefined specialist profiles ─────────────────────────────────────────

DEFAULT_PROFILES: Dict[str, SpecialistProfile] = {
    "coder": SpecialistProfile(
        name="CoderAgent",
        role=SpecialistType.CODER,
        description="Expert at writing, debugging, and refactoring code in any language",
        system_prompt=(
            "You are a coding specialist. Write clean, well-documented code. "
            "Always test your code before reporting completion. "
            "Use file operations to save your work. "
            "If you encounter an error, debug it systematically."
        ),
        allowed_tools=["code_run", "file_read", "file_write", "file_patch"],
        max_turns=20,
    ),
    "researcher": SpecialistProfile(
        name="ResearchAgent",
        role=SpecialistType.RESEARCHER,
        description="Expert at searching the web, finding information, and synthesizing research",
        system_prompt=(
            "You are a research specialist. Find accurate, up-to-date information. "
            "Cross-reference multiple sources. Present findings clearly with citations. "
            "Always verify facts before reporting them."
        ),
        allowed_tools=["web_scan", "web_execute_js", "web_search"],
        max_turns=15,
    ),
    "analyst": SpecialistProfile(
        name="AnalystAgent",
        role=SpecialistType.ANALYST,
        description="Expert at data analysis, statistics, visualization, and interpretation",
        system_prompt=(
            "You are a data analysis specialist. Analyze data rigorously using Python. "
            "Create clear visualizations. Interpret results in plain language. "
            "Always validate your assumptions with the data."
        ),
        allowed_tools=["code_run", "file_read", "file_write"],
        max_turns=20,
    ),
    "writer": SpecialistProfile(
        name="WriterAgent",
        role=SpecialistType.WRITER,
        description="Expert at creating, editing, and improving written content",
        system_prompt=(
            "You are a writing specialist. Create clear, engaging, well-structured content. "
            "Adapt your tone to the audience. Proofread carefully. "
            "Use file operations to save documents."
        ),
        allowed_tools=["file_read", "file_write", "file_patch"],
        max_turns=15,
    ),
    "system": SpecialistProfile(
        name="SystemAgent",
        role=SpecialistType.SYSTEM,
        description="Expert at file management, system operations, and environment setup",
        system_prompt=(
            "You are a system operations specialist. Manage files, run shell commands, "
            "and configure environments safely. Always verify operations completed "
            "successfully. Be cautious with destructive operations."
        ),
        allowed_tools=["code_run", "file_read", "file_write", "file_patch"],
        max_turns=15,
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
#  Delegation result
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class DelegationResult:
    """Result of delegating a task to a specialist.

    Attributes
    ----------
    specialist : str
        Name of the specialist that handled the task.
    task : str
        The delegated task description.
    result : str
        The specialist's response.
    success : bool
        Whether the task was completed successfully.
    turns_used : int
        Number of turns used.
    duration_seconds : float
        Wall-clock time for the delegation.
    """

    specialist: str
    task: str
    result: str
    success: bool = True
    turns_used: int = 0
    duration_seconds: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  AgentOrchestrator
# ══════════════════════════════════════════════════════════════════════════════


class AgentOrchestrator:
    """Manages multiple specialist sub-agents for complex task decomposition.

    The orchestrator provides:

    * **Delegation** — Route tasks to the best specialist
    * **Pipeline** — Chain multiple specialists sequentially
    * **Collaboration** — Multiple specialists work in parallel
    * **Handoff** — Transfer context between specialists mid-task

    Usage
    -----
    ::

        orchestrator = AgentOrchestrator(agent=my_agent)

        # Simple delegation
        result = orchestrator.delegate("Fix the bug in main.py")

        # Pipeline (research → analyze → write)
        results = orchestrator.pipeline(
            "Write a market analysis report on AI agents",
            specialists=["researcher", "analyst", "writer"],
        )
    """

    def __init__(self, agent: Any = None) -> None:
        self._agent = agent
        self._specialists: Dict[str, SpecialistProfile] = dict(DEFAULT_PROFILES)
        self._delegation_history: list[DelegationResult] = []
        self._filtered_schemas: Optional[list[dict]] = None
        self._lock = threading.Lock()
        # Tracks which builtin tools are enabled/disabled for the current specialist
        self._builtin_tool_enabled: Dict[str, bool] = {}

    # ── Specialist management ─────────────────────────────────────────────

    def register_specialist(self, profile: SpecialistProfile) -> None:
        """Register a new specialist profile."""
        with self._lock:
            self._specialists[profile.name] = profile

    def remove_specialist(self, name: str) -> None:
        """Remove a specialist profile."""
        with self._lock:
            self._specialists.pop(name, None)

    def list_specialists(self) -> list[dict[str, Any]]:
        """List all registered specialists."""
        with self._lock:
            return [
                {
                    "name": p.name,
                    "role": p.role.value,
                    "description": p.description,
                    "allowed_tools": p.allowed_tools,
                    "max_turns": p.max_turns,
                }
                for p in self._specialists.values()
            ]

    # ── Task routing ──────────────────────────────────────────────────────

    def suggest_specialist(
        self,
        task: str,
        use_llm: bool = True,  # B5: Default changed — LLM routing is more accurate than fragile keyword matching
        llm_client: Any = None,
    ) -> str:
        """Suggest the best specialist for a task.

        By default (since B5), uses LLM-based routing when an ``llm_client``
        is provided, as keyword matching is fragile and error-prone.  Falls back
        gracefully to keyword-based heuristic routing when no ``llm_client`` is
        available (with a warning log).

        Parameters
        ----------
        task : str
            The task description.
        use_llm : bool
            If ``True``, use LLM-based routing (requires llm_client).
        llm_client : Any
            LLM client with a ``chat()`` method.  Required when use_llm=True.

        Returns
        -------
        str
            The specialist name.
        """
        # Try LLM-based routing first if requested and client available
        if use_llm and llm_client is not None:
            llm_result = self._suggest_specialist_llm(task, llm_client)
            if llm_result:
                return llm_result

        # B5: Graceful fallback when use_llm=True but no llm_client provided
        if use_llm and llm_client is None:
            logger.warning(
                "suggest_specialist: use_llm=True but no llm_client provided; "
                "falling back to keyword-based matching"
            )

        # Fall back to keyword-based heuristic routing
        task_lower = task.lower()

        # Keyword-based routing with weighted scoring
        keyword_map: Dict[str, list[tuple[str, int]]] = {
            "CoderAgent": [
                ("code", 3), ("program", 3), ("function", 2), ("class", 2),
                ("debug", 3), ("refactor", 3), ("implement", 2), ("script", 2),
                ("python", 2), ("javascript", 2), ("bug", 3), ("fix", 2),
                ("compile", 2), ("error", 1), ("exception", 1), ("build", 1),
            ],
            "ResearchAgent": [
                ("search", 3), ("find", 2), ("lookup", 2), ("research", 3),
                ("look up", 2), ("investigate", 3), ("what is", 2), ("who is", 2),
                ("how does", 2), ("latest", 2), ("current", 1), ("news", 2),
                ("documentation", 2), ("docs", 2), ("api reference", 3),
            ],
            "AnalystAgent": [
                ("analyze", 3), ("analysis", 3), ("chart", 3), ("graph", 3),
                ("plot", 3), ("statistics", 3), ("data", 2), ("csv", 3),
                ("excel", 3), ("spreadsheet", 2), ("calculate", 1), ("metric", 2),
                ("dashboard", 3), ("visualization", 3), ("trend", 2),
            ],
            "WriterAgent": [
                ("write", 2), ("draft", 3), ("compose", 3), ("essay", 3),
                ("article", 3), ("report", 2), ("email", 2), ("letter", 3),
                ("document", 1), ("blog", 3), ("summary", 2), ("rewrite", 3),
                ("edit", 2), ("proofread", 3), ("translate", 3),
            ],
            "SystemAgent": [
                ("file", 1), ("directory", 2), ("folder", 2), ("move", 2),
                ("copy", 2), ("rename", 3), ("delete", 2), ("install", 3),
                ("setup", 3), ("configure", 3), ("deploy", 3),
                ("backup", 3), ("archive", 2), ("permission", 3),
            ],
        }

        scores: Dict[str, int] = {}
        for specialist, keywords in keyword_map.items():
            for kw, weight in keywords:
                if kw in task_lower:
                    scores[specialist] = scores.get(specialist, 0) + weight

        if not scores:
            return "CoderAgent"  # Default

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def _suggest_specialist_llm(self, task: str, llm_client: Any) -> Optional[str]:
        """Use an LLM call to classify the task into a specialist type.

        This sends a short classification prompt to the LLM and parses
        the response.  Returns ``None`` if classification fails.

        Parameters
        ----------
        task : str
            The task description.
        llm_client : Any
            LLM client with a ``chat()`` method.

        Returns
        -------
        str | None
            Specialist name, or ``None`` on failure.
        """
        specialist_names = [p.name for p in self._specialists.values()]
        specialist_descriptions = "\n".join(
            f"- {p.name}: {p.description}"
            for p in self._specialists.values()
        )

        prompt = (
            "Classify the following task into exactly ONE of these specialist types:\n"
            f"{specialist_descriptions}\n\n"
            f"Task: {task[:500]}\n\n"
            "Respond with ONLY the specialist name, nothing else."
        )

        try:
            messages = [
                {"role": "system", "content": "You are a task classifier. Respond with ONLY the specialist name."},
                {"role": "user", "content": prompt},
            ]
            # Use a simple non-tool call to get classification
            from agent_loop import exhaust
            gen = llm_client.chat(messages=messages, tools=[])
            response = exhaust(gen)

            # Extract the specialist name from the response
            result = response.content.strip() if hasattr(response, "content") else str(response).strip()

            # Match against known specialist names
            for name in specialist_names:
                if name.lower() in result.lower():
                    return name

            logger.debug("LLM routing returned unrecognized specialist: %s", result)
            return None

        except Exception as exc:
            logger.debug("LLM-based specialist routing failed: %s", exc)
            return None

    # ── Delegation ────────────────────────────────────────────────────────

    def delegate(
        self,
        task: str,
        specialist_name: Optional[str] = None,
        context: Optional[str] = None,
    ) -> DelegationResult:
        """Delegate a task to a specialist agent.

        Parameters
        ----------
        task : str
            The task to delegate.
        specialist_name : str | None
            Specialist to use.  If ``None``, auto-selected.
        context : str | None
            Additional context to pass to the specialist.

        Returns
        -------
        DelegationResult
            The result of the delegation.
        """
        if specialist_name is None:
            specialist_name = self.suggest_specialist(task)

        with self._lock:
            profile = self._specialists.get(specialist_name)

        if profile is None:
            return DelegationResult(
                specialist=specialist_name,
                task=task,
                result=f"Specialist '{specialist_name}' not found",
                success=False,
            )

        logger.info("Delegating to %s: %s", specialist_name, task[:80])

        start_time = time.time()

        # Build the prompt with context
        full_task = task
        if context:
            full_task = f"[Context]\n{context}\n\n[Task]\n{task}"

        if profile.system_prompt:
            full_task = f"[System Instruction]\n{profile.system_prompt}\n\n[Task]\n{full_task}"

        # Execute via the main agent (with filtered tool schemas)
        result_text = self._execute_specialist(profile, full_task)

        duration = time.time() - start_time

        delegation_result = DelegationResult(
            specialist=specialist_name,
            task=task,
            result=result_text,
            success=True,
            duration_seconds=duration,
        )

        with self._lock:
            self._delegation_history.append(delegation_result)

        return delegation_result

    def pipeline(
        self,
        task: str,
        specialists: list[str],
    ) -> list[DelegationResult]:
        """Execute a pipeline of specialists sequentially.

        Each specialist receives the output of the previous one as context.

        Parameters
        ----------
        task : str
            The initial task.
        specialists : list[str]
            Ordered list of specialist names.

        Returns
        -------
        list[DelegationResult]
            Results from each specialist in the pipeline.
        """
        results: list[DelegationResult] = []
        context = ""

        for i, specialist in enumerate(specialists):
            if i == 0:
                sub_task = task
            else:
                sub_task = (
                    f"Based on the following previous work, continue the task:\n\n"
                    f"--- Previous Output ---\n{context}\n--- End Previous Output ---\n\n"
                    f"Original task: {task}\n\nYour contribution:"
                )

            result = self.delegate(sub_task, specialist_name=specialist)
            results.append(result)

            if result.success:
                context = result.result
            else:
                logger.warning(
                    "Pipeline specialist '%s' failed, stopping pipeline",
                    specialist,
                )
                break

        return results

    # ── Internal execution ────────────────────────────────────────────────

    def _execute_specialist(
        self, profile: SpecialistProfile, task: str
    ) -> str:
        """Execute a task using a specialist profile via the main agent.

        This creates a task with the specialist's system prompt injected
        and **enforces** the tool restrictions defined by ``allowed_tools``.
        Tools not in the specialist's allowed list are temporarily disabled
        during execution and re-enabled afterwards.  The handler's
        ``_active_specialist`` attribute is set so that dispatch-level
        enforcement also applies.
        """
        if self._agent is None:
            return "[Error] No agent instance available for delegation"

        # ── Enforce tool restrictions ──────────────────────────────────────
        disabled_tools = self._restrict_tools(profile)

        try:
            # Set the active specialist on the current handler for dispatch-level enforcement
            handler = getattr(self._agent, "handler", None)
            if handler is not None:
                handler._active_specialist = profile

            # Use the main agent's put_task and collect the response
            display_queue = self._agent.put_task(
                query=task,
                source="orchestrator",
            )

            # Collect response
            full_response = ""
            timeout = 300  # 5 minutes max
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    item = display_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if "done" in item:
                    full_response = item["done"]
                    break
                elif "next" in item:
                    full_response += item["next"]

            return full_response or "[No response from specialist]"

        finally:
            # ── Restore previously disabled tools ────────────────────────
            # Clear the active specialist first
            handler = getattr(self._agent, "handler", None)
            if handler is not None:
                handler._active_specialist = None
            self._restore_tools(disabled_tools)

    def _restrict_tools(self, profile: SpecialistProfile) -> list[str]:
        """Disable tools not in the specialist's allowed list.

        If ``allowed_tools`` is empty, no restrictions are applied
        (all tools remain available).

        The specialist's ``allowed_tools`` list is **intersection-based**:
        only the tools explicitly listed (plus any from the plugin registry
        that match) are made available.  Builtin tools are NOT automatically
        added — they must be explicitly included in ``allowed_tools`` if the
        specialist needs them.

        This method enforces restrictions on both:
        1. Registry-based tools (via ToolRegistry.disable)
        2. Builtin tools tracked in ``_builtin_tool_enabled``

        Returns
        -------
        list[str]
            Names of tools that were disabled, for later restoration.
        """
        if not profile.allowed_tools:
            return []

        allowed_set = set(profile.allowed_tools)

        disabled = []

        # ── Registry-based tool restriction ──────────────────────────────
        try:
            from tools.registry import get_registry
            registry = get_registry()

            for tool_name in registry.tool_names:
                if tool_name not in allowed_set:
                    registry.disable(tool_name)
                    disabled.append(tool_name)

            if disabled:
                logger.info(
                    "Specialist '%s': disabled %d registry tools (%s)",
                    profile.name, len(disabled), ", ".join(disabled[:5]),
                )

        except ImportError:
            logger.debug("Tool registry not available for restriction")

        # ── Builtin tool restriction (handler-level enforcement) ──────────
        try:
            from tools.registry import BUILTIN_TOOL_NAMES
            self._builtin_tool_enabled = {}
            for builtin_name in BUILTIN_TOOL_NAMES:
                is_allowed = builtin_name in allowed_set
                self._builtin_tool_enabled[builtin_name] = is_allowed
                if not is_allowed:
                    disabled.append(builtin_name)
                    logger.debug(
                        "Specialist '%s': builtin tool '%s' DISABLED",
                        profile.name, builtin_name,
                    )
        except ImportError:
            logger.debug("BUILTIN_TOOL_NAMES not available for specialist enforcement")

        # Filter the tool schema so the LLM doesn't see unavailable tools
        self._filtered_schemas = self._filter_tool_schemas(allowed_set)

        return disabled

    def _restore_tools(self, disabled_tools: list[str]) -> None:
        """Re-enable tools that were disabled for specialist execution.

        Restores both registry-based tools and builtin tool tracking.
        """
        if not disabled_tools:
            return

        # ── Restore registry-based tools ──────────────────────────────────
        try:
            from tools.registry import get_registry
            registry = get_registry()

            for tool_name in disabled_tools:
                registry.enable(tool_name)

            logger.debug("Restored %d previously disabled registry tools", len(disabled_tools))

        except ImportError:
            pass

        # ── Restore builtin tool tracking ─────────────────────────────────
        self._builtin_tool_enabled = {}  # Clear restrictions

        # Restore unfiltered tool schemas
        self._filtered_schemas = None

    def _filter_tool_schemas(self, allowed_set: set[str]) -> Optional[list[dict]]:
        """Return filtered tool schemas that only include allowed tools.

        This prevents the LLM from even seeing tools the specialist
        shouldn't use.
        """
        try:
            from agentmain.prompts import get_merged_tool_schemas
            all_schemas = get_merged_tool_schemas()
            filtered = []
            for schema in all_schemas:
                func = schema.get("function", {})
                name = func.get("name", "")
                if name in allowed_set:
                    filtered.append(schema)
            return filtered
        except ImportError:
            return None

    # ── History ───────────────────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent delegation history."""
        with self._lock:
            recent = self._delegation_history[-limit:]
        return [
            {
                "specialist": r.specialist,
                "task": r.task[:100],
                "success": r.success,
                "duration": round(r.duration_seconds, 2),
            }
            for r in recent
        ]

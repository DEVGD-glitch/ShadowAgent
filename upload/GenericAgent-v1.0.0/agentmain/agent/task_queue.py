"""Task Queue — Input queue and run loop for the agent.

Extracted from :mod:`agentmain.core` (task 3.1.2) so that queue management
and the main execution loop can be tested independently.
"""
from __future__ import annotations

import logging
import os
import queue
import re
import signal
import time
from typing import Any, List, Optional

from agent_loop import agent_runner_loop
from ga import GenericAgentHandler, smart_format, format_error, consume_file
from agentmain.prompts import script_dir, get_system_prompt, get_merged_tool_schemas
from config import get_agent_config
from exceptions import SessionConfigError

logger = logging.getLogger("agentmain.agent.task_queue")


class TaskQueue:
    """Manages the incoming task queue and the agent execution loop.

    Responsibilities:
      - Accept tasks via :meth:`put_task`
      - Process them sequentially in :meth:`run`
      - Support abort / graceful shutdown
    """

    def __init__(self, agent: Any) -> None:
        """Initialize the task queue.

        Parameters
        ----------
        agent : GenericAgent
            The owning agent instance (used to access llmclient, history, etc.).
        """
        self._agent = agent
        self.task_queue: queue.Queue = queue.Queue()
        self.is_running: bool = False
        self.stop_sig: bool = False
        self._shutdown_event = agent._shutdown_event  # shared with agent

    # ── Task submission ──────────────────────────────────────────────────

    def put_task(
        self,
        query: str,
        source: str = "user",
        images: Optional[List[str]] = None,
    ) -> queue.Queue:
        """Enqueue a task for the agent and return a result queue.

        Parameters
        ----------
        query : str
            The user's input text (may be a slash command).
        source : str
            Origin of the query — ``"user"``, ``"task"``, or ``"reflect"``.
        images : list[str] | None
            Optional list of image paths or URLs.

        Returns
        -------
        queue.Queue
            A queue on which dicts with keys ``"next"`` (incremental) and
            ``"done"`` (final) will be placed.
        """
        display_queue: queue.Queue = queue.Queue()
        self.task_queue.put(
            {
                "query": query,
                "source": source,
                "images": images or [],
                "output": display_queue,
            }
        )
        return display_queue

    # ── Abort & shutdown ─────────────────────────────────────────────────

    def abort(self) -> None:
        """Signal the running agent loop to stop."""
        if not self.is_running:
            return
        logger.info("Abort current task...")
        self.stop_sig = True
        if self._agent.handler is not None:
            self._agent.handler.code_stop_signal.set()

    def shutdown(self, timeout: float = 30.0) -> None:
        """Request a graceful shutdown of the run loop.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait for the current turn to finish.
        """
        logger.info("Shutdown requested — setting shutdown event")
        self._shutdown_event.set()
        self.abort()
        deadline = time.monotonic() + timeout
        while self.is_running and time.monotonic() < deadline:
            time.sleep(0.1)
        if self.is_running:
            logger.warning("Shutdown: agent still running after %.1fs timeout", timeout)
        else:
            logger.info("Shutdown complete")

    # ── Main run loop ────────────────────────────────────────────────────

    def run(self) -> None:
        """Consume tasks from :attr:`task_queue` and execute them sequentially.

        This method blocks indefinitely and is intended to be run in a
        dedicated thread.
        """
        while not self._shutdown_event.is_set():
            try:
                task = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            raw_query: str = task["query"]
            source: str = task["source"]
            images: List[str] = task.get("images") or []
            display_queue: queue.Queue = task["output"]

            raw_query = self._agent._handle_slash_cmd(raw_query, display_queue)
            if raw_query is None:
                self.task_queue.task_done()
                continue

            # v0.6.0: Input guardrail validation
            guardrail_result = self._agent.validate_input(raw_query)
            if not guardrail_result.passed:
                display_queue.put({"done": f"[GUARDRAIL] Input blocked: {guardrail_result.reason}", "source": "system"})
                self.task_queue.task_done()
                continue

            self.is_running = True
            rquery = smart_format(raw_query.replace("\n", " "), max_str_len=200)
            self._agent.history.append(f"[USER]: {rquery}")

            sys_prompt = get_system_prompt() + getattr(
                self._agent.llmclient.backend, "extra_sys_prompt", ""
            )
            handler = GenericAgentHandler(
                self._agent, self._agent.history, os.path.join(script_dir, "temp")
            )

            # Use merged tool schemas (builtin + plugins)
            tools_schema = get_merged_tool_schemas()

            # Carry over working memory from the previous handler
            if self._agent.handler and "key_info" in self._agent.handler.working:
                ki = re.sub(
                    r"\n\[(?:SYSTEM|SYSTÈME)\] (?:此为|Ceci est|This is).*?(?:工作记忆|mémoire de travail|working memory)[。\n]*",
                    "",
                    self._agent.handler.working["key_info"],
                )
                handler.working["key_info"] = ki
                handler.working["passed_sessions"] = ps = (
                    self._agent.handler.working.get("passed_sessions", 0) + 1
                )
                if ps > 0:
                    lang = os.environ.get('GA_LANG', '')
                    if lang == 'zh':
                        msg = f"\n[SYSTEM] 此为 {ps} 个对话前设置的key_info，若已在新任务，先更新或清除工作记忆。\n"
                    elif lang == 'en':
                        msg = f"\n[SYSTEM] This is key_info set {ps} session(s) ago. If starting a new task, update or clear working memory first.\n"
                    else:
                        msg = f"\n[SYSTÈME] Ceci est le key_info défini il y a {ps} session(s). Si nouvelle tâche, mettre à jour ou effacer la mémoire de travail.\n"
                    handler.working["key_info"] += msg
            else:
                # Try to load persisted working checkpoint from disk
                try:
                    from memory.crystallization import load_working_checkpoint
                    checkpoint = load_working_checkpoint()
                    if checkpoint and checkpoint.get("key_info"):
                        handler.working["key_info"] = checkpoint["key_info"]
                        handler.working["related_sop"] = checkpoint.get("related_sop", "")
                        handler.working["passed_sessions"] = 0
                        logger.info("Restored working checkpoint from disk (saved at %s)", checkpoint.get("saved_at", "unknown"))
                except Exception:
                    logger.debug("Failed to restore working checkpoint from disk", exc_info=True)

            # ── Auto-activate ReasoningEngine
            try:
                from agentmain.reasoning import ReasoningEngine, ReasoningMode
                suggested_mode = ReasoningEngine.suggest_mode(raw_query)
                if suggested_mode != ReasoningMode.DEFAULT:
                    handler.reasoning_engine = ReasoningEngine(mode=suggested_mode)
                    logger.info(
                        "ReasoningEngine auto-activated: mode=%s",
                        suggested_mode.value,
                    )
            except Exception as exc:
                logger.debug("ReasoningEngine auto-activation skipped: %s", exc)

            self._agent.handler = handler

            # Wire the handler's event_queue to the display_queue
            handler.event_queue = display_queue

            agent_config = get_agent_config()
            gen = agent_runner_loop(
                self._agent.llmclient,
                sys_prompt,
                raw_query,
                handler,
                tools_schema,
                max_turns=agent_config.max_turns,
                verbose=self._agent.verbose,
            )
            try:
                full_resp: str = ""
                last_pos: int = 0
                for chunk in gen:
                    if consume_file(self._agent.task_dir, "_stop"):
                        self.abort()
                    if self.stop_sig:
                        break
                    full_resp += chunk
                    if len(full_resp) - last_pos > 50 or "LLM Running" in chunk:
                        display_queue.put(
                            {
                                "next": full_resp[last_pos:] if self._agent.inc_out else full_resp,
                                "source": source,
                            }
                        )
                        last_pos = len(full_resp)

                # Flush any remaining incremental output
                if self._agent.inc_out and last_pos < len(full_resp):
                    display_queue.put(
                        {"next": full_resp[last_pos:], "source": source}
                    )

                # Post-processing formatting
                if "</summary>" in full_resp:
                    full_resp = full_resp.replace("</summary>", "</summary>\n\n")
                if "</file_content>" in full_resp:
                    full_resp = re.sub(
                        r"<file_content>\s*(.*?)\s*</file_content>",
                        r"\n````\n<file_content>\n\1\n</file_content>\n````",
                        full_resp,
                        flags=re.DOTALL,
                    )

                # v0.6.0: Output guardrail validation
                output_result = self._agent.validate_output(full_resp)
                if not output_result.passed:
                    full_resp += f"\n\n[GUARDRAIL] Output warning: {output_result.reason}"

                display_queue.put({"done": full_resp, "source": source})
                self._agent.history = handler.history_info

                # B4: Check context compaction after each turn
                self._agent._check_context_compaction()

            except Exception as exc:
                logger.error("Backend Error: %s", format_error(exc))
                display_queue.put(
                    {"done": full_resp + f"\n```\n{format_error(exc)}\n```", "source": source}
                )
            finally:
                if self.stop_sig:
                    logger.info("User aborted the task.")
                self.is_running = self.stop_sig = False
                self.task_queue.task_done()
                if self._agent.handler is not None:
                    self._agent.handler.code_stop_signal.set()

        # Exited main loop due to shutdown event
        logger.info("Agent run loop exited (shutdown event was set)")

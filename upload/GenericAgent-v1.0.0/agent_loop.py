"""Core agent loop and handler infrastructure for GenericAgent.

This module implements the main agent execution loop that orchestrates
multi-turn LLM conversations with tool dispatching. It provides:

- :class:`StepOutcome` — structured result from each tool/handler step
- :class:`BaseHandler` — base class for tool dispatch with lifecycle hooks
- :func:`agent_runner_loop` — the main multi-turn generator loop
- Utility helpers: :func:`json_default`, :func:`exhaust`, :func:`get_pretty_json`

The agent loop is a generator that yields progress text and returns a
result dict describing how the loop terminated.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Generator, Optional

from exceptions import AgentError, AgentInterruptError, MaxTurnsExceededError
from i18n import t
from logging_config import get_logger

logger = get_logger("agent_loop")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "StepOutcome",
    "BaseHandler",
    "agent_runner_loop",
    "json_default",
    "exhaust",
    "get_pretty_json",
]


# ---------------------------------------------------------------------------
# StepOutcome
# ---------------------------------------------------------------------------

@dataclass
class StepOutcome:
    """Structured result returned by each tool or handler step.

    Attributes
    ----------
    data : Any
        The payload produced by the step.  May be a dict, list, string, or
        ``None`` when the step produced no useful data.
    next_prompt : str | None
        The prompt to feed back to the LLM for the next turn.  ``None``
        signals that the current task is done and the loop should exit with
        ``CURRENT_TASK_DONE``.
    should_exit : bool
        When ``True`` the agent loop should stop immediately with an
        ``EXITED`` result.
    """

    data: Any
    next_prompt: Optional[str] = None
    should_exit: bool = False

    # -- Derived helpers -----------------------------------------------------

    @property
    def is_error(self) -> bool:
        """Return ``True`` if *data* looks like an error result.

        An outcome is considered erroneous when *data* is a dict containing
        a ``"status"`` key whose value is ``"error"``, or when *data* is a
        string that starts with the ``"[Error]"`` sentinel.
        """
        if isinstance(self.data, dict):
            return self.data.get("status") == "error"
        if isinstance(self.data, str):
            return self.data.startswith("[Error]")
        return False

    # -- Constructor from dict -----------------------------------------------

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StepOutcome:
        """Create a :class:`StepOutcome` from a plain dictionary.

        Parameters
        ----------
        d : dict
            A mapping that must contain a ``"data"`` key and may contain
            optional ``"next_prompt"`` and ``"should_exit"`` keys.

        Returns
        -------
        StepOutcome
            The constructed instance.

        Raises
        ------
        KeyError
            If the required ``"data"`` key is missing.
        """
        return cls(
            data=d["data"],
            next_prompt=d.get("next_prompt"),
            should_exit=d.get("should_exit", False),
        )


# ---------------------------------------------------------------------------
# Generator helper
# ---------------------------------------------------------------------------

def try_call_generator(func: Any, *args: Any, **kwargs: Any) -> Generator:
    """Call *func* and, if it returns a generator, yield from it.

    This transparently handles both plain functions and generator functions,
    so callers don't need to distinguish between the two.

    Parameters
    ----------
    func : callable
        The function to invoke.
    *args, **kwargs
        Positional and keyword arguments forwarded to *func*.

    Yields
    ------
    str
        Any values yielded by *func* when it is a generator.

    Returns
    -------
    Any
        The return value of *func* (or the generator's final value).
    """
    ret = func(*args, **kwargs)
    if hasattr(ret, "__iter__") and not isinstance(ret, (str, bytes, dict, list)):
        ret = yield from ret
    return ret


# ---------------------------------------------------------------------------
# BaseHandler
# ---------------------------------------------------------------------------

class BaseHandler:
    """Base class for agent tool handlers with lifecycle hooks.

    Subclasses implement tool methods following the ``do_<tool_name>``
    convention.  The :meth:`dispatch` method routes tool calls to the
    appropriate ``do_`` method and wraps each call with
    :meth:`tool_before_callback` / :meth:`tool_after_callback` hooks.

    Attributes
    ----------
    parent : Any
        Reference to the parent agent/session object.  Accessed by the
        agent loop for properties like ``task_dir``.
    max_turns : int
        Maximum number of turns allowed; set by the agent loop.
    current_turn : int
        The current turn index; updated by the agent loop each iteration.
    _done_hooks : list[str]
        Queue of prompts to inject after the current task finishes.
    """

    def __init__(
        self,
        parent: Any = None,
        *,
        max_turns: int = 40,
        current_turn: int = 0,
        done_hooks: Optional[list[str]] = None,
    ) -> None:
        """Initialise the base handler.

        Parameters
        ----------
        parent : Any, optional
            Reference to the parent agent/session object.
        max_turns : int
            Initial maximum turns limit (will be overwritten by the loop).
        current_turn : int
            Starting turn index.
        done_hooks : list[str] | None
            Initial list of done-hook prompts.
        """
        self.parent: Any = parent
        self.max_turns: int = max_turns
        self.current_turn: int = current_turn
        self._done_hooks: list[str] = list(done_hooks) if done_hooks else []

        # Phase 7: Optional event queue for UI notifications
        # When set, tool_call/tool_result/thinking events are put here
        self.event_queue: Optional[Any] = None  # queue.Queue or None

        # ReasoningEngine auto-integration: when set, the turn_end_callback
        # automatically extracts thoughts/reflections/plans and generates
        # reasoning-specific next prompts.  Set this from agentmain.core
        # or ga.py after creating the handler.
        self.reasoning_engine: Any = None  # ReasoningEngine or None

        # Current task goal — used by the reasoning engine for ReAct prompts
        self._current_task_goal: str = ""

    # -- Lifecycle hooks (override in subclasses) ----------------------------

    def tool_before_callback(
        self,
        tool_name: str,
        args: dict[str, Any],
        response: Any,
    ) -> Any:
        """Hook called *before* a tool is executed.

        Parameters
        ----------
        tool_name : str
            Name of the tool about to be called.
        args : dict
            The arguments that will be passed to the tool.
        response : Any
            The LLM response object that triggered this tool call.

        Returns
        -------
        Any
            Ignored by default; useful for generator-based overrides.
        """

    def tool_after_callback(
        self,
        tool_name: str,
        args: dict[str, Any],
        response: Any,
        ret: Any,
    ) -> Any:
        """Hook called *after* a tool has been executed.

        Parameters
        ----------
        tool_name : str
            Name of the tool that was called.
        args : dict
            The arguments that were passed to the tool.
        response : Any
            The LLM response object that triggered this tool call.
        ret : Any
            The return value from the tool.

        Returns
        -------
        Any
            Ignored by default; useful for generator-based overrides.
        """

    def turn_end_callback(
        self,
        response: Any,
        tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        turn: int,
        next_prompt: str,
        exit_reason: dict[str, Any],
    ) -> str:
        """Hook called at the end of each agent turn.

        When a :class:`~agentmain.reasoning.ReasoningEngine` is attached
        (via :attr:`reasoning_engine`), this hook automatically:

        * Appends the reasoning system prompt on the first turn.
        * Generates next-step prompts (ReAct observation, Plan step, etc.).
        * Extracts thoughts, reflections, and plan steps from LLM output.

        Parameters
        ----------
        response : Any
            The LLM response for this turn.
        tool_calls : list[dict]
            The tool calls made during this turn.
        tool_results : list[dict]
            The results from executing those tools.
        turn : int
            The current turn number (1-based).
        next_prompt : str
            The concatenated next-prompt text.
        exit_reason : dict
            Exit reason dict (non-empty when the loop is about to stop).

        Returns
        -------
        str
            The (possibly modified) next prompt to send to the LLM.
        """
        # ── ReasoningEngine auto-integration ──────────────────────────────
        if self.reasoning_engine is not None:
            engine = self.reasoning_engine

            # Extract structured content from the LLM response
            response_text = ""
            if hasattr(response, "content") and response.content:
                response_text = response.content

            # Extract and store thoughts / reflections / plan steps
            thought = engine.extract_thought(response_text)
            if thought:
                engine.thought_history.append(thought)

            reflection = engine.extract_reflection(response_text)
            if reflection:
                engine.reflection_history.append(reflection)

            # Auto-parse plan from first response in PLAN_EXECUTE mode
            if (
                engine.mode.value == "plan_execute"
                and not engine.plan
                and turn == 1
            ):
                steps = engine.extract_plan(response_text)
                if steps:
                    engine.create_plan(steps)

            # Advance plan step if a tool was successfully called
            if engine.plan and tool_results and not exit_reason:
                current = engine.get_current_step()
                if current and not current.completed:
                    last_result = tool_results[-1].get("content", "") if tool_results else ""
                    engine.advance_step(result=last_result[:200])

            # Generate reasoning-specific next prompt
            if not exit_reason and tool_results:
                last_result_data = tool_results[-1] if tool_results else {}
                reasoning_prompt = engine.get_next_prompt(
                    tool_result=last_result_data,
                    goal=getattr(self, "_current_task_goal", ""),
                )
                if reasoning_prompt.strip() and reasoning_prompt.strip() != "\n":
                    next_prompt = reasoning_prompt + next_prompt

        return next_prompt

    # -- Dispatch ------------------------------------------------------------

    def dispatch(
        self,
        tool_name: str,
        args: dict[str, Any],
        response: Any,
        index: int = 0,
    ) -> Generator[str, None, StepOutcome]:
        """Route a tool call to the matching ``do_<tool_name>`` method.

        The dispatch priority is:

        1. ``do_<tool_name>`` method on the handler (builtin tools)
        2. Tool registered in the global :class:`ToolRegistry` (plugins)
        3. ``bad_json`` special case
        4. Unknown tool — yields a warning

        Before dispatching, arguments are validated against the tool's
        JSON Schema if the :mod:`tools.validation` module is available.

        Parameters
        ----------
        tool_name : str
            The name of the tool to invoke.
        args : dict
            Arguments for the tool.  An ``_index`` key is injected with
            *index* before the tool is called.
        response : Any
            The LLM response object that triggered this tool call.
        index : int
            The positional index of this tool call within the batch.

        Yields
        ------
        str
            Text produced by the tool (or callbacks) for streaming output.

        Returns
        -------
        StepOutcome
            The result of the tool execution.
        """
        # Validate arguments before dispatch
        args, validation_errors = self._validate_args(tool_name, args)
        if validation_errors:
            error_msg = "[Validation Error] " + "; ".join(validation_errors)
            yield f"{error_msg}\n"
            return StepOutcome(
                {"status": "error", "msg": error_msg},
                next_prompt=f"\nFix the parameter errors and try again:\n{error_msg}\n",
            )

        # Enforce specialist tool restrictions at dispatch level
        active_specialist = getattr(self, "_active_specialist", None)
        if active_specialist and hasattr(active_specialist, "allowed_tools") and active_specialist.allowed_tools:
            if tool_name not in active_specialist.allowed_tools:
                error_msg = (
                    f"[Tool Restriction] Tool '{tool_name}' is not available "
                    f"for specialist '{active_specialist.name}'. "
                    f"Allowed tools: {', '.join(active_specialist.allowed_tools)}"
                )
                yield f"{error_msg}\n"
                return StepOutcome(
                    {"status": "error", "msg": error_msg},
                    next_prompt=f"\nYou cannot use '{tool_name}'. Use only the allowed tools: {', '.join(active_specialist.allowed_tools)}\n",
                )

        method_name = f"do_{tool_name}"
        if hasattr(self, method_name):
            args["_index"] = index
            prer = yield from try_call_generator(self.tool_before_callback, tool_name, args, response)
            ret = yield from try_call_generator(getattr(self, method_name), args, response)
            _ = yield from try_call_generator(self.tool_after_callback, tool_name, args, response, ret)
            return ret
        elif tool_name == "bad_json":
            return StepOutcome(None, next_prompt=args.get("msg", "bad_json"), should_exit=False)
        else:
            # Try the dynamic tool registry
            registry_result = self._dispatch_registry(tool_name, args, response)
            if registry_result is not None:
                return registry_result

            # Unknown tool — use i18n with ZH fallback for backward compat
            _unknown = t("agent.unknown_tool")
            yield f"{_unknown}: {tool_name}\n"
            return StepOutcome(None, next_prompt=f"{_unknown} {tool_name}", should_exit=False)

    def _validate_args(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        """Validate tool arguments against the schema.

        Returns (coerced_args, error_messages).  If the tools.validation
        module is not available, returns args unchanged with no errors.
        """
        try:
            from tools.validation import validate_and_coerce
            from agentmain.prompts import TOOLS_SCHEMA
            return validate_and_coerce(tool_name, args, TOOLS_SCHEMA)
        except ImportError:
            return args, []

    def _dispatch_registry(
        self, tool_name: str, args: dict[str, Any], response: Any
    ) -> Optional[StepOutcome]:
        """Try to dispatch a tool call via the global tool registry.

        Returns a StepOutcome if the tool is found, or None if not.
        This method is called from ``dispatch()`` which is a generator,
        so we cannot use ``yield from`` here.  Generator-returning
        plugin handlers are driven to completion via ``exhaust()``.
        """
        try:
            from tools.registry import get_registry
            registry = get_registry()
            tool = registry.get(tool_name)
            if tool is not None:
                result = tool.handler(args, response)
                # Handle generator results from plugin handlers
                if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict, list)):
                    result = exhaust(result)
                return StepOutcome(result, next_prompt="\n")
        except ImportError:
            pass
        except Exception as exc:
            logger.error("Registry dispatch failed for %s: %s", tool_name, exc)
            return StepOutcome(
                {"status": "error", "msg": str(exc)},
                next_prompt=f"\n[Error] Tool '{tool_name}' failed: {exc}\n",
            )
        return None


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def json_default(o: Any) -> Any:
    """Serialize objects that :func:`json.dumps` cannot handle by default.

    Currently supports:
    * :class:`set` → converted to :class:`list`
    * Everything else → :class:`str`

    Parameters
    ----------
    o : Any
        The object to serialize.

    Returns
    -------
    Any
        A JSON-compatible representation.
    """
    return list(o) if isinstance(o, set) else str(o)


def exhaust(g: Generator) -> Any:
    """Drive a generator to completion and return its final value.

    This is useful for consuming a generator whose side-effects are
    important but whose yielded values are not needed.

    Parameters
    ----------
    g : Generator
        The generator to exhaust.

    Returns
    -------
    Any
        The value returned by the generator (via ``StopIteration.value``).
    """
    try:
        while True:
            next(g)
    except StopIteration as e:
        return e.value


def get_pretty_json(data: Any) -> str:
    """Return a human-readable JSON string with minor formatting tweaks.

    If *data* is a dict containing a ``"script"`` key, semicolons inside
    the script value are broken onto separate lines for readability.

    Parameters
    ----------
    data : Any
        The data to serialize.

    Returns
    -------
    str
        Pretty-printed JSON with literal newlines (``\\n`` sequences are
        replaced with actual newline characters).
    """
    if isinstance(data, dict) and "script" in data:
        data = data.copy()
        data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace("\\n", "\n")


# ---------------------------------------------------------------------------
# Agent runner loop
# ---------------------------------------------------------------------------

def agent_runner_loop(
    client: Any,
    system_prompt: str,
    user_input: str,
    handler: BaseHandler,
    tools_schema: list[dict[str, Any]],
    max_turns: int = 40,
    verbose: bool = True,
    initial_user_content: Optional[str] = None,
) -> Generator[str, None, dict[str, Any]]:
    """Execute the multi-turn agent loop.

    This generator yields progress text for streaming display and returns
    a dict describing the exit reason:

    * ``{"result": "EXITED", "data": ...}`` — a tool explicitly requested
      exit via :attr:`StepOutcome.should_exit`.
    * ``{"result": "CURRENT_TASK_DONE", "data": ...}`` — a tool returned
      a ``None`` *next_prompt*, signalling task completion.
    * :class:`MaxTurnsExceededError` is **raised** when the loop exceeds
      *max_turns* without reaching a conclusion.

    Parameters
    ----------
    client : Any
        The LLM client with a ``chat()`` method that returns a generator.
    system_prompt : str
        The system-level prompt injected at the start of every conversation.
    user_input : str
        The user's input text.
    handler : BaseHandler
        The tool handler that dispatches tool calls.
    tools_schema : list[dict]
        The tools schema passed to the LLM client.
    max_turns : int
        Maximum number of turns before raising :class:`MaxTurnsExceededError`.
    verbose : bool
        When ``True``, yield detailed streaming output; when ``False``,
        yield compact progress text.
    initial_user_content : str | None
        Optional override for the first user message content.  When
        ``None``, *user_input* is used as the first message.

    Yields
    ------
    str
        Streaming text for display.

    Returns
    -------
    dict[str, Any]
        Exit reason dict (only on normal exits).

    Raises
    ------
    MaxTurnsExceededError
        When the loop exceeds *max_turns* without a tool signalling
        completion or exit.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": initial_user_content if initial_user_content is not None else user_input},
    ]
    turn: int = 0
    handler.max_turns = max_turns
    exit_reason: dict[str, Any] = {}

    # ── Auto-activate ReasoningEngine if attached ─────────────────────────
    # When handler.reasoning_engine is set, inject the reasoning system
    # prompt addition and store the task goal for ReAct prompts.
    if handler.reasoning_engine is not None:
        reasoning_addition = handler.reasoning_engine.get_system_prompt_addition()
        if reasoning_addition:
            messages[0]["content"] += reasoning_addition
        handler._current_task_goal = user_input

    while turn < handler.max_turns:
        turn += 1
        turnstr = f"LLM Running (Turn {turn}) ..."
        if handler.parent and getattr(handler.parent, "task_dir", None):
            turnstr = f"Turn {turn} ..."
        if verbose:
            turnstr = f"**{turnstr}**"
        yield f"\n\n{turnstr}\n\n"

        # 每10轮重置工具描述 / Reset tool descriptions every 10 turns
        # to prevent context bloat from degrading model performance
        if turn % 10 == 0:
            client.last_tools = ""

        response_gen = client.chat(messages=messages, tools=tools_schema)
        if verbose:
            response = yield from response_gen
            yield "\n\n"
        else:
            response = exhaust(response_gen)
            cleaned = _clean_content(response.content)
            if cleaned:
                yield cleaned + "\n"

        if not response.tool_calls:
            tool_calls: list[dict[str, Any]] = [{"tool_name": "no_tool", "args": {}}]
        else:
            tool_calls = [
                {
                    "tool_name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "id": tc.id,
                }
                for tc in response.tool_calls
            ]

        tool_results: list[dict[str, Any]] = []
        next_prompts: set[str] = set()

        for ii, tc in enumerate(tool_calls):
            tool_name, args, tid = tc["tool_name"], tc["args"], tc.get("id", "")

            if tool_name == "no_tool":
                pass
            else:
                # Phase 7: Emit tool_call event for UI
                if handler.event_queue is not None:
                    try:
                        handler.event_queue.put({
                            "tool_call": {
                                "name": tool_name,
                                "args": args,
                                "id": tid,
                            }
                        })
                    except Exception:
                        logger.debug("Failed to emit tool_call event for %s", tool_name, exc_info=True)

                if verbose:
                    yield f"🛠️ Tool: `{tool_name}`  📥 args:\n````text\n{get_pretty_json(args)}\n````\n"
                else:
                    yield f"🛠️ {tool_name}({_compact_tool_args(tool_name, args)})\n\n\n"

            handler.current_turn = turn
            gen = handler.dispatch(tool_name, args, response, index=ii)
            try:
                v = next(gen)

                def proxy() -> Generator:
                    yield v
                    return (yield from gen)

                if verbose:
                    yield "`````\n"
                    outcome: StepOutcome = yield from proxy()
                    yield "`````\n"
                else:
                    outcome = exhaust(proxy())
            except StopIteration as e:
                outcome = e.value

            # Phase 7: Emit tool_result event for UI
            if tool_name != "no_tool" and handler.event_queue is not None:
                try:
                    result_status = "error" if outcome.is_error else "success"
                    result_data = None
                    if outcome.data is not None:
                        result_data = (
                            json.dumps(outcome.data, ensure_ascii=False, default=json_default)
                            if isinstance(outcome.data, (dict, list))
                            else str(outcome.data)
                        )
                    handler.event_queue.put({
                        "tool_result": {
                            "id": tid,
                            "name": tool_name,
                            "status": result_status,
                            "data": result_data,
                        }
                    })
                except Exception:
                    logger.debug("Failed to emit tool_result event for %s", tool_name, exc_info=True)

            if outcome.should_exit:
                exit_reason = {"result": "EXITED", "data": outcome.data}
                break

            if not outcome.next_prompt:
                exit_reason = {"result": "CURRENT_TASK_DONE", "data": outcome.data}
                break

            # Unknown tool — force tool list refresh
            # Match both FR ("Outil inconnu") and ZH ("未知工具") for backward compat
            if outcome.next_prompt.startswith((t("agent.unknown_tool"), "未知工具")):
                client.last_tools = ""

            if outcome.data is not None and tool_name != "no_tool":
                datastr = (
                    json.dumps(outcome.data, ensure_ascii=False, default=json_default)
                    if isinstance(outcome.data, (dict, list))
                    else str(outcome.data)
                )
                tool_results.append({"tool_use_id": tid, "content": datastr})

            next_prompts.add(outcome.next_prompt)

        # Handle done-hooks or break when no prompts remain
        if len(next_prompts) == 0 or exit_reason:
            if len(handler._done_hooks) == 0 or exit_reason.get("result", "") == "EXITED":
                break
            next_prompts.add(handler._done_hooks.pop(0))

        next_prompt = handler.turn_end_callback(
            response, tool_calls, tool_results, turn, "\n".join(next_prompts), exit_reason
        )
        # just new message, history is kept in *Session
        messages = [{"role": "user", "content": next_prompt, "tool_results": tool_results}]

    # Final callback on exit
    if exit_reason:
        handler.turn_end_callback(response, tool_calls, tool_results, turn, "", exit_reason)

        # Auto-crystallization: if task ran 15+ turns and completed normally,
        # inject a start_long_term_update prompt as a done-hook
        try:
            from memory.crystallization import should_crystallize, get_crystallization_prompt
            if should_crystallize(turn, exit_reason):
                crystallization_prompt = get_crystallization_prompt()
                # Inject into done-hooks so the agent performs memory distillation
                handler._done_hooks.append(crystallization_prompt)
                logger.info(
                    "Auto-crystallization triggered after %d turns (exit: %s)",
                    turn, exit_reason.get("result", ""),
                )
        except ImportError:
            logger.debug("Crystallization module not available, skipping auto-trigger")

        # Process remaining done-hooks by auto-submitting a continuation task
        # if the agent has a parent with put_task capability
        if handler._done_hooks:
            logger.info(
                "Processing %d remaining done-hooks after loop exit",
                len(handler._done_hooks),
            )
            try:
                parent = getattr(handler, "parent", None)
                if parent and hasattr(parent, "put_task"):
                    # Submit all pending done-hooks as a single continuation task
                    combined = "\n".join(handler._done_hooks)
                    handler._done_hooks.clear()
                    # Fire-and-forget: the parent agent will run this in its task loop
                    parent.put_task(combined, source="crystallization")
                    logger.info("Auto-submitted crystallization continuation task")
            except Exception as exc:
                logger.debug("Could not auto-submit done-hooks: %s", exc)

        return exit_reason

    # Max turns exceeded — raise a proper exception instead of returning a
    # plain dict so callers can catch and handle it idiomatically.
    logger.warning("Agent loop exceeded max_turns=%d", max_turns)
    raise MaxTurnsExceededError(
        f"Agent loop exceeded maximum of {max_turns} turns",
        details={"max_turns": max_turns, "actual_turns": turn},
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# Regex that matches a fenced code block, including its opening fence
# (with optional language tag) and closing fence.  We use a dedicated
# pattern instead of the naïve `````[\s\S]*?``` ``` to avoid catastrophic
# back-tracking and to handle edge cases such as:
#
# * Nested backtick runs inside a code block (e.g. ```` ``` ```` inside)
# * Unclosed code blocks at the end of the text
# * Consecutive code blocks without a blank line separator
#
# Strategy: greedily consume everything between the opening ``` and the
# *last* ```, then walk backwards to find the nearest closing fence.
# If no valid closing fence exists (unclosed block), we leave the text
# untouched.

_CODE_BLOCK_RE = re.compile(
    r"```"            # opening fence
    r"[^\n]*\n"       # optional language tag + newline
    r"([\s\S]*?)"     # body (non-greedy)
    r"\n```",         # closing fence on its own line
)

# Fallback: handle code blocks where the closing fence may be at EOF
# without a trailing newline.
_CODE_BLOCK_EOF_RE = re.compile(
    r"```"
    r"[^\n]*\n"
    r"([\s\S]*?)"
    r"```",
)


def _clean_content(text: Optional[str]) -> str:
    """Shrink verbose LLM output for compact (non-verbose) display.

    Long fenced code blocks are collapsed to a 5-line preview with a
    line-count summary.  XML-style tags (``<file_content>``, ``<tool_use>``,
    ``<tool_call``) and excessive blank lines are stripped.

    Parameters
    ----------
    text : str | None
        The raw LLM response content.

    Returns
    -------
    str
        The cleaned, compacted text.
    """
    if not text:
        return ""

    def _shrink_code(m: re.Match) -> str:
        """Collapse a matched code block if it exceeds 6 non-blank lines."""
        full_match = m.group(0)
        lines = full_match.split("\n")
        lang = lines[0].replace("```", "").strip()
        body = [l for l in lines[1:-1] if l.strip()]
        if len(body) <= 6:
            return full_match
        preview = "\n".join(body[:5])
        return f"```{lang}\n{preview}\n  ... ({len(body)} lines)\n```"

    # Try the stricter pattern first; fall back to the EOF-tolerant one.
    text = _CODE_BLOCK_RE.sub(_shrink_code, text)
    text = _CODE_BLOCK_EOF_RE.sub(_shrink_code, text)

    # Strip XML-style tags and collapse excessive blank lines
    for pattern in [
        r"<file_content>[\s\S]*?</file_content>",
        r"<tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>",
        r"(\r?\n){3,}",
    ]:
        replacement = "\n\n" if "\n" in pattern else ""
        text = re.sub(pattern, replacement, text)

    return text.strip()


def _compact_tool_args(name: str, args: dict[str, Any]) -> str:
    """Produce a one-line summary of tool arguments for compact display.

    Parameters
    ----------
    name : str
        The tool name (used for tool-specific formatting).
    args : dict
        The tool arguments.

    Returns
    -------
    str
        A compact string representation of the arguments.
    """
    a = {k: v for k, v in args.items() if k != "_index"}
    for k in ("path",):
        if k in a:
            a[k] = os.path.basename(a[k])
    if name == "update_working_checkpoint":
        s = a.get("key_info", "")
        return (s[:60] + "...") if len(s) > 60 else s
    if name == "ask_user":
        q = str(a.get("question", ""))
        cs = a.get("candidates") or []
        if cs:
            q += "\ncandidates:\n" + "\n".join(f"- {c}" for c in cs)
        return q
    s = json.dumps(a, ensure_ascii=False)
    return (s[:120] + "...") if len(s) > 120 else s

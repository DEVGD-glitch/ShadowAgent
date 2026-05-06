"""agentmain/reasoning.py — Enhanced reasoning patterns for GenericAgent.

Implements advanced reasoning strategies that can be layered on top of the
base agent loop:

- **ReAct** (Reason+Act) — Interleave thinking and tool calls explicitly
- **Plan-and-Execute** — Decompose complex tasks into a plan, then execute
- **Self-Reflection** — Evaluate and correct the agent's own outputs
- **Chain-of-Thought** — Structured reasoning chains with verification

These patterns are injected into the system prompt and handled by the
agent loop's turn_end_callback mechanism.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentmain.reasoning")


# ══════════════════════════════════════════════════════════════════════════════
#  Reasoning mode
# ══════════════════════════════════════════════════════════════════════════════


class ReasoningMode(Enum):
    """Available reasoning strategies."""

    DEFAULT = "default"         # Standard tool-calling loop
    REACT = "react"             # Reason + Act interleaved
    PLAN_EXECUTE = "plan_execute"  # Plan first, then execute
    REFLECT = "reflect"         # Self-reflection and correction


# ══════════════════════════════════════════════════════════════════════════════
#  ReAct prompt fragments
# ══════════════════════════════════════════════════════════════════════════════


REACT_SYSTEM_PROMPT = """
## ReAct Reasoning Mode

You are operating in ReAct (Reason + Act) mode.  For each step, you MUST:

1. **Thought** — Think about what you know, what you need to find out, and
   what action to take next.  Write your reasoning in a `<thought>` block.
2. **Action** — Call the appropriate tool with the correct arguments.
3. **Observation** — Review the tool result and update your understanding.

Continue this Thought → Action → Observation cycle until the task is complete.

Format:
```
<thought>
[Your reasoning about the current state and what to do next]
</thought>
```
Then call a tool or provide a final answer.

When you have enough information to answer the user's question, provide a
final answer in a `<final_answer>` block.
"""

REACT_NEXT_PROMPT_TEMPLATE = """
<observation>
{observation}
</observation>

Continue with your next thought. Remember the overall goal: {goal}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Plan-and-Execute prompt fragments
# ══════════════════════════════════════════════════════════════════════════════


PLAN_SYSTEM_PROMPT = """
## Plan-and-Execute Mode

You are operating in Plan-and-Execute mode.  For complex tasks, you should:

1. **Create a Plan** — Break the task into clear, ordered steps. Write the
   plan in a `<plan>` block with numbered steps.
2. **Execute Step by Step** — Work through each step of the plan, using
   tools as needed.  Mark completed steps with ✅.
3. **Verify** — After completing all steps, verify the results meet the
   original requirements.

Format for the plan:
```
<plan>
1. [Step description]
2. [Step description]
3. [Step description]
</plan>
```

After creating the plan, execute each step. After completing a step, update
the plan with ✅ to mark it done:
```
<plan>
1. ✅ [Completed step]
2. [Current step] ← working on this
3. [Pending step]
</plan>
```
"""

PLAN_TEMPLATE = """
<plan>
{plan_steps}
</plan>

Current step: Step {current_step}
Execute this step now.
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Self-Reflection prompt fragments
# ══════════════════════════════════════════════════════════════════════════════


REFLECT_SYSTEM_PROMPT = """
## Self-Reflection Mode

You are operating in Self-Reflection mode.  After completing each major
action, you should:

1. **Evaluate** — Check if the action achieved its intended goal.
2. **Identify Issues** — Look for errors, inconsistencies, or improvements.
3. **Correct** — If issues are found, fix them before proceeding.

Use `<reflection>` blocks to document your self-evaluation:
```
<reflection>
- Did this step achieve its goal? [Yes/No]
- Issues found: [description or "None"]
- Correction needed: [description or "None"]
</reflection>
```

Only proceed to the next step when the current step passes self-evaluation.
"""


# ══════════════════════════════════════════════════════════════════════════════
#  ReasoningEngine — manages reasoning state and prompt injection
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class PlanStep:
    """A single step in a plan."""

    description: str
    completed: bool = False
    result: str = ""


MAX_PLAN_STEPS = 20


class ReasoningEngine:
    """Manages reasoning state and injects appropriate prompts.

    The engine tracks the current reasoning mode, plan state, and
    reflection history.  It provides methods to:

    * Get the appropriate system prompt additions for the current mode
    * Generate next-step prompts based on the reasoning state
    * Track plan progress
    * Extract thoughts, reflections, and plan steps from LLM output

    Usage
    -----
    ::

        engine = ReasoningEngine(mode=ReasoningMode.REACT)
        system_prompt += engine.get_system_prompt_addition()
        next_prompt = engine.get_next_prompt(tool_result, goal=user_query)
    """

    def __init__(self, mode: ReasoningMode = ReasoningMode.DEFAULT) -> None:
        self.mode = mode
        self.plan: list[PlanStep] = []
        self.current_step: int = 0
        self.thought_history: list[str] = []
        self.reflection_history: list[str] = []

    # ── Prompt generation ─────────────────────────────────────────────────

    def get_system_prompt_addition(self) -> str:
        """Return the system prompt addition for the current reasoning mode."""
        additions = {
            ReasoningMode.REACT: REACT_SYSTEM_PROMPT,
            ReasoningMode.PLAN_EXECUTE: PLAN_SYSTEM_PROMPT,
            ReasoningMode.REFLECT: REFLECT_SYSTEM_PROMPT,
            ReasoningMode.DEFAULT: "",
        }
        return additions.get(self.mode, "")

    def get_next_prompt(
        self,
        tool_result: Any,
        goal: str = "",
    ) -> str:
        """Generate the next prompt based on the current reasoning mode.

        Parameters
        ----------
        tool_result : Any
            The result from the last tool call.
        goal : str
            The overall task goal (for ReAct mode).

        Returns
        -------
        str
            The next prompt to send to the LLM.
        """
        if self.mode == ReasoningMode.REACT:
            obs_str = str(tool_result)
            if isinstance(tool_result, dict):
                obs_str = json.dumps(tool_result, ensure_ascii=False, indent=2)[:2000]
            return REACT_NEXT_PROMPT_TEMPLATE.format(
                observation=obs_str,
                goal=goal,
            )

        if self.mode == ReasoningMode.PLAN_EXECUTE and self.plan:
            return PLAN_TEMPLATE.format(
                plan_steps=self._format_plan(),
                current_step=self.current_step + 1,
            )

        return "\n"

    # ── Plan management ───────────────────────────────────────────────────

    def create_plan(self, steps: list[str]) -> None:
        """Create a plan from a list of step descriptions."""
        self.plan = [PlanStep(description=s) for s in steps]
        self.current_step = 0

    def advance_step(self, result: str = "") -> None:
        """Mark the current step as completed and advance to the next."""
        if self.current_step < len(self.plan):
            self.plan[self.current_step].completed = True
            self.plan[self.current_step].result = result
            self.current_step += 1

    def get_current_step(self) -> Optional[PlanStep]:
        """Return the current plan step, or None if the plan is complete."""
        if self.current_step < len(self.plan):
            return self.plan[self.current_step]
        return None

    def is_plan_complete(self) -> bool:
        """Check if all plan steps are completed."""
        return all(step.completed for step in self.plan)

    def _format_plan(self) -> str:
        """Format the plan as a markdown checklist."""
        lines = []
        for i, step in enumerate(self.plan, 1):
            marker = "✅" if step.completed else "⬜"
            lines.append(f"{i}. {marker} {step.description}")
        return "\n".join(lines)

    # ── Output parsing ────────────────────────────────────────────────────

    @staticmethod
    def extract_thought(text: str) -> Optional[str]:
        """Extract the content of a <thought> block from LLM output."""
        match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def extract_reflection(text: str) -> Optional[str]:
        """Extract the content of a <reflection> block from LLM output."""
        match = re.search(r"<reflection>(.*?)</reflection>", text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def extract_plan(text: str) -> list[str]:
        """Extract plan steps from a <plan> block in LLM output."""
        match = re.search(r"<plan>(.*?)</plan>", text, re.DOTALL)
        if not match:
            return []
        plan_text = match.group(1)
        # Parse numbered steps
        steps = []
        for line in plan_text.strip().split("\n"):
            line = line.strip()
            # Remove step numbers and checkmarks
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
            cleaned = re.sub(r"^[✅⬜⬛]\s*", "", cleaned)
            if cleaned:
                steps.append(cleaned)
        # Truncate plans that exceed MAX_PLAN_STEPS
        if len(steps) > MAX_PLAN_STEPS:
            logger.info(
                "Plan has %d steps, truncating to MAX_PLAN_STEPS=%d",
                len(steps), MAX_PLAN_STEPS,
            )
            steps = steps[:MAX_PLAN_STEPS]
        return steps

    @staticmethod
    def extract_final_answer(text: str) -> Optional[str]:
        """Extract the content of a <final_answer> block from LLM output."""
        match = re.search(r"<final_answer>(.*?)</final_answer>", text, re.DOTALL)
        return match.group(1).strip() if match else None

    # ── Mode selection heuristic ──────────────────────────────────────────

    @staticmethod
    def suggest_mode(task: str) -> ReasoningMode:
        """Suggest a reasoning mode based on the task description.

        Uses weighted keyword heuristics for fast, local classification.
        For production, this can be replaced with an LLM-based classifier
        using :meth:`suggest_mode_llm`.

        Parameters
        ----------
        task : str
            The task description.

        Returns
        -------
        ReasoningMode
            The suggested reasoning mode.
        """
        task_lower = task.lower()

        # Weighted keyword scoring for each mode
        mode_scores: Dict[ReasoningMode, int] = {
            ReasoningMode.PLAN_EXECUTE: 0,
            ReasoningMode.REACT: 0,
            ReasoningMode.REFLECT: 0,
        }

        # Plan-and-Execute keywords (weight: strong signal)
        plan_keywords = [
            ("plan", 3), ("step by step", 3), ("break down", 3), ("decompose", 2),
            ("multiple steps", 2), ("first...then", 2), ("comprehensive", 2),
            ("from scratch", 2), ("end to end", 3), ("roadmap", 2),
            ("milestone", 2), ("phased", 2),
        ]
        for kw, weight in plan_keywords:
            if kw in task_lower:
                mode_scores[ReasoningMode.PLAN_EXECUTE] += weight

        # ReAct keywords (weight: moderate signal)
        react_keywords = [
            ("find", 2), ("search", 2), ("investigate", 3), ("explore", 3),
            ("research", 2), ("analyze", 1), ("understand", 2), ("figure out", 3),
            ("determine", 2), ("what is", 1), ("how does", 1), ("why", 1),
            ("diagnose", 3), ("troubleshoot", 3),
        ]
        for kw, weight in react_keywords:
            if kw in task_lower:
                mode_scores[ReasoningMode.REACT] += weight

        # Self-Reflection keywords (weight: quality signal)
        reflect_keywords = [
            ("carefully", 2), ("verify", 3), ("ensure", 2), ("double check", 3),
            ("accurate", 2), ("precise", 2), ("no errors", 3), ("production", 2),
            ("review", 2), ("audit", 3), ("validate", 3), ("correctness", 3),
        ]
        for kw, weight in reflect_keywords:
            if kw in task_lower:
                mode_scores[ReasoningMode.REFLECT] += weight

        # Return the highest-scoring mode, or DEFAULT if no keywords matched
        best_mode = max(mode_scores, key=mode_scores.get)  # type: ignore[arg-type]
        if mode_scores[best_mode] == 0:
            return ReasoningMode.DEFAULT

        return best_mode

    @staticmethod
    def suggest_mode_llm(task: str, llm_client: Any) -> ReasoningMode:
        """Use an LLM call to classify the best reasoning mode.

        This sends a short classification prompt and parses the response.
        Falls back to :meth:`suggest_mode` on failure.

        Parameters
        ----------
        task : str
            The task description.
        llm_client : Any
            LLM client with a ``chat()`` method.

        Returns
        -------
        ReasoningMode
            The suggested reasoning mode.
        """
        mode_descriptions = "\n".join(
            f"- {m.value}: {desc}"
            for m, desc in [
                (ReasoningMode.REACT, "Best for research, investigation, exploration tasks"),
                (ReasoningMode.PLAN_EXECUTE, "Best for complex multi-step tasks requiring a plan"),
                (ReasoningMode.REFLECT, "Best for quality-sensitive tasks requiring verification"),
                (ReasoningMode.DEFAULT, "Standard tool-calling loop without special reasoning"),
            ]
        )

        prompt = (
            "Classify the following task into exactly ONE reasoning mode:\n"
            f"{mode_descriptions}\n\n"
            f"Task: {task[:500]}\n\n"
            "Respond with ONLY the mode name (react, plan_execute, reflect, or default)."
        )

        try:
            from agent_loop import exhaust
        except ImportError:
            logger.debug("agent_loop not available for LLM mode classification, using keyword heuristic")
            return ReasoningEngine.suggest_mode(task)

        try:
            messages = [
                {"role": "system", "content": "You are a task classifier. Respond with ONLY the mode name."},
                {"role": "user", "content": prompt},
            ]
            gen = llm_client.chat(messages=messages, tools=[])
            response = exhaust(gen)
            result = response.content.strip().lower() if hasattr(response, "content") else str(response).strip().lower()

            # Match against known mode values
            mode_map = {
                "react": ReasoningMode.REACT,
                "plan_execute": ReasoningMode.PLAN_EXECUTE,
                "plan": ReasoningMode.PLAN_EXECUTE,
                "reflect": ReasoningMode.REFLECT,
                "default": ReasoningMode.DEFAULT,
            }
            for key, mode in mode_map.items():
                if key in result:
                    return mode

            return ReasoningMode.DEFAULT

        except Exception as exc:
            logger.debug("LLM-based reasoning mode classification failed: %s", exc)
            return ReasoningEngine.suggest_mode(task)

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the engine state."""
        return {
            "mode": self.mode.value,
            "plan": [
                {
                    "description": s.description,
                    "completed": s.completed,
                    "result": s.result,
                }
                for s in self.plan
            ],
            "current_step": self.current_step,
            "thoughts_count": len(self.thought_history),
            "reflections_count": len(self.reflection_history),
        }

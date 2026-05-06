"""
CLI entry-point for GenericAgent.

Provides :func:`main_cli`, the function referenced by the ``genericagent``
console-script entry-point in ``pyproject.toml``.  Supports three
operational modes:

* **Interactive** — REPL-style chat with incremental output.
* **Task mode** (``--task IODIR``) — file-based I/O for headless / batch runs.
* **Reflect mode** (``--reflect SCRIPT``) — watchdog-style automation triggered
  by an external monitoring script.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Union

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("agentmain")

# ---------------------------------------------------------------------------
# Internal package imports
# ---------------------------------------------------------------------------

from agentmain.prompts import script_dir
from agentmain.core import GenericAgent

# ---------------------------------------------------------------------------
# Intermediate-save configuration (task mode)
# ---------------------------------------------------------------------------

_INTERMEDIATE_SAVE_INTERVAL_CHUNKS: int = 5
"""Save intermediate results every N streamed chunks in task mode."""

_INTERMEDIATE_SAVE_INTERVAL_SECS: float = 15.0
"""Minimum seconds between intermediate saves in task mode."""


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main_cli() -> None:
    """Main CLI entry-point for GenericAgent.

    Parses command-line arguments and starts the agent in the selected
    mode (interactive, task, or reflect).
    """
    parser = argparse.ArgumentParser(description="GenericAgent CLI")
    parser.add_argument("--task", metavar="IODIR", help="Mode tâche unique (E/S fichiers)")
    parser.add_argument(
        "--reflect", metavar="SCRIPT", help="Mode réflexion : charge un script de monitoring, check() déclenche une tâche"
    )
    parser.add_argument("--input", help="prompt")
    parser.add_argument("--llm_no", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--bg", action="store_true", help="popen, print PID, exit")
    args = parser.parse_args()

    if args.bg:
        cmd = [sys.executable, "-m", "agentmain"] + [
            a for a in sys.argv[1:] if a != "--bg"
        ]
        d = os.path.join(script_dir, "temp", args.task)
        os.makedirs(d, exist_ok=True)
        stdout_fh = open(os.path.join(d, "stdout.log"), "w", encoding="utf-8")
        stderr_fh = open(os.path.join(d, "stderr.log"), "w", encoding="utf-8")
        p = subprocess.Popen(
            cmd,
            cwd=script_dir,
            creationflags=0x08000000 if platform.system() == "Windows" else 0,
            stdout=stdout_fh,
            stderr=stderr_fh,
        )
        # Close file handles in parent; child has inherited them
        stdout_fh.close()
        stderr_fh.close()
        print(p.pid)
        sys.exit(0)

    agent = GenericAgent()
    agent.next_llm(args.llm_no)
    agent.verbose = args.verbose
    threading.Thread(target=agent.run, daemon=True).start()

    if args.task:
        agent.task_dir = d = os.path.join(script_dir, "temp", args.task)
        nround: int = 0
        infile = os.path.join(d, "input.txt")

        if args.input:
            os.makedirs(d, exist_ok=True)
            for f in glob.glob(os.path.join(d, "output*.txt")):
                try:
                    os.remove(f)
                except OSError:
                    pass
            with open(infile, "w", encoding="utf-8") as fh:
                fh.write(args.input)

        with open(infile, encoding="utf-8") as fh:
            raw = fh.read()

        # Intermediate-save state: track chunk count and last save timestamp
        chunk_counter: int = 0
        last_intermediate_save: float = 0.0

        while True:
            dq = agent.put_task(raw, source="task")
            chunk_counter = 0
            last_intermediate_save = time.monotonic()
            while "done" not in (item := dq.get(timeout=120)):
                if "next" in item:
                    chunk_counter += 1
                    now = time.monotonic()
                    # Save every N chunks OR every N seconds (whichever comes first)
                    if (
                        chunk_counter % _INTERMEDIATE_SAVE_INTERVAL_CHUNKS == 0
                        or (now - last_intermediate_save) >= _INTERMEDIATE_SAVE_INTERVAL_SECS
                    ):
                        with open(
                            os.path.join(d, f"output{nround}.txt"), "w", encoding="utf-8"
                        ) as fh:
                            fh.write(item.get("next", ""))
                        last_intermediate_save = now

            with open(os.path.join(d, f"output{nround}.txt"), "w", encoding="utf-8") as fh:
                fh.write(item["done"] + "\n\n[ROUND END]\n")

            from ga import consume_file

            consume_file(d, "_stop")  # already stopped; avoid interrupting next reply

            for _ in range(300):  # wait for reply.txt, 10-minute timeout
                time.sleep(2)
                reply_content = consume_file(d, "reply.txt")
                if reply_content:
                    raw = reply_content
                    break
            else:
                break
            nround += 1

    elif args.reflect:
        spec = importlib.util.spec_from_file_location("reflect_script", args.reflect)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _mt = os.path.getmtime(args.reflect)
        logger.info("[Reflect] loaded %s", args.reflect)

        while True:
            if os.path.getmtime(args.reflect) != _mt:
                try:
                    spec.loader.exec_module(mod)
                    _mt = os.path.getmtime(args.reflect)
                    logger.info("[Reflect] reloaded")
                except Exception as exc:
                    logger.error("[Reflect] reload error: %s", exc)
            time.sleep(getattr(mod, "INTERVAL", 5))
            try:
                task = mod.check()
            except Exception as exc:
                logger.warning("[Reflect] check() error: %s", exc)
                continue
            if task is None:
                continue
            logger.info("[Reflect] triggered: %s", task[:80])
            dq = agent.put_task(task, source="reflect")
            try:
                while "done" not in (item := dq.get(timeout=120)):
                    pass
                result = item["done"]
                logger.info("[Reflect] result: %s", result[:200])
            except Exception as exc:
                if getattr(mod, "ONCE", False):
                    raise
                logger.error("[Reflect] drain error: %s", exc)
                result = f"[ERROR] {exc}"

            log_dir = os.path.join(script_dir, "temp/reflect_logs")
            os.makedirs(log_dir, exist_ok=True)
            script_name = os.path.splitext(os.path.basename(args.reflect))[0]
            with open(
                os.path.join(log_dir, f"{script_name}_{datetime.now():%Y-%m-%d}.log"),
                "a",
                encoding="utf-8",
            ) as fh:
                fh.write(f"[{datetime.now():%m-%d %H:%M}]\n{result}\n\n")

            if (on_done := getattr(mod, "on_done", None)):
                try:
                    on_done(result)
                except Exception as exc:
                    logger.error("[Reflect] on_done error: %s", exc)

            if getattr(mod, "ONCE", False):
                logger.info("[Reflect] ONCE=True, exiting.")
                break

    else:
        try:
            import readline  # noqa: F401
        except Exception:
            logger.debug("readline module not available")
        agent.inc_out = True
        while True:
            q = input("> ").strip()
            if not q:
                continue
            try:
                dq = agent.put_task(q, source="user")
                while True:
                    item = dq.get()
                    if "next" in item:
                        print(item["next"], end="", flush=True)
                    if "done" in item:
                        print()
                        break
            except KeyboardInterrupt:
                agent.abort()
                print("\n[Interrupted]")


if __name__ == "__main__":
    main_cli()

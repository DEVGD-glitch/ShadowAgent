import ast, asyncio, glob, json, logging, os, queue as Q, re, socket, sys, time

try:
    from i18n import t
except ImportError:
    def t(key, *args, **kwargs):
        return key

logger = logging.getLogger("frontends.chatapp_common")

HELP_COMMANDS = (
    ("/help", lambda: t("chat.cmd.help")),
    ("/status", lambda: t("chat.cmd.status")),
    ("/stop", lambda: t("chat.cmd.stop")),
    ("/new", lambda: t("chat.cmd.new")),
    ("/restore", lambda: t("chat.cmd.restore")),
    ("/continue", lambda: t("chat.cmd.continue_list")),
    ("/continue [n]", lambda: t("chat.cmd.continue_n")),
    ("/llm", lambda: t("chat.cmd.llm_list")),
    ("/llm [n]", lambda: t("chat.cmd.llm_switch")),
)
TELEGRAM_MENU_COMMANDS = (
    ("help", lambda: t("chat.cmd.help")),
    ("status", lambda: t("chat.cmd.status")),
    ("stop", lambda: t("chat.cmd.stop")),
    ("new", lambda: t("chat.cmd.new")),
    ("restore", lambda: t("chat.cmd.restore")),
    ("continue", lambda: t("chat.cmd.continue_tg")),
    ("llm", lambda: t("chat.cmd.llm_tg")),
)


def build_help_text(commands=HELP_COMMANDS):
    return t("chat.help_header") + "\n" + "\n".join(f"{cmd} - {desc()}" for cmd, desc in commands)


HELP_TEXT = build_help_text()
FILE_HINT = "If you need to show files to user, use [FILE:filepath] in your response."
TAG_PATS = [r"<" + t + r">.*?</" + t + r">" for t in ("thinking", "summary", "tool_use", "file_content")]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTORE_GLOBS = (
    os.path.join(PROJECT_ROOT, "temp", "model_responses", "model_responses_*.txt"),
    os.path.join(PROJECT_ROOT, "temp", "model_responses_*.txt"),
)
RESTORE_BLOCK_RE = re.compile(
    r"^=== (Prompt|Response) ===.*?\n(.*?)(?=^=== (?:Prompt|Response) ===|\Z)",
    re.DOTALL | re.MULTILINE,
)
HISTORY_RE = re.compile(r"<history>\s*(.*?)\s*</history>", re.DOTALL)
SUMMARY_RE = re.compile(r"<summary>\s*(.*?)\s*</summary>", re.DOTALL)


def clean_reply(text):
    for pat in TAG_PATS:
        text = re.sub(pat, "", text or "", flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip() or "..."


def extract_files(text):
    return re.findall(r"\[FILE:([^\]]+)\]", text or "")


def strip_files(text):
    return re.sub(r"\[FILE:[^\]]+\]", "", text or "").strip()


def split_text(text, limit):
    text, parts = (text or "").strip() or "...", []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit * 0.6:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts + ([text] if text else []) or ["..."]


def _restore_log_files():
    files = []
    for pattern in RESTORE_GLOBS:
        files.extend(glob.glob(pattern))
    return sorted(set(files))


def _restore_text_pairs(content):
    users = re.findall(r"=== USER ===\n(.+?)(?==== |$)", content, re.DOTALL)
    resps = re.findall(r"=== Response ===.*?\n(.+?)(?==== Prompt|$)", content, re.DOTALL)
    restored = []
    for u, r in zip(users, resps):
        u, r = u.strip(), r.strip()[:500]
        if u and r:
            restored.extend([f"[USER]: {u}", f"[Agent] {r}"])
    return restored


def _native_prompt_obj(prompt_body):
    try:
        prompt = json.loads(prompt_body)
    except Exception:
        return None
    if not isinstance(prompt, dict) or prompt.get("role") != "user":
        return None
    if not isinstance(prompt.get("content"), list):
        return None
    return prompt


def _native_prompt_text(prompt):
    texts = []
    for block in prompt.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return "\n".join(texts).strip()


def _native_history_lines(prompt_text):
    match = HISTORY_RE.search(prompt_text or "")
    if not match:
        return []
    restored = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("[USER]: ") or line.startswith("[Agent] "):
            restored.append(line)
    return restored


def _native_first_user_line(prompt_text):
    text = (prompt_text or "").strip()
    if not text or "<history>" in text or text.startswith("### [WORKING MEMORY]"):
        return ""
    if text.startswith(FILE_HINT):
        text = text[len(FILE_HINT):].lstrip()
    if "### 用户当前消息" in text:
        text = text.split("### 用户当前消息", 1)[-1].strip()
    return text


def _native_response_summary(response_body):
    try:
        blocks = ast.literal_eval((response_body or "").strip())
    except Exception:
        return ""
    if not isinstance(blocks, list):
        return ""
    text_parts = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str) and text:
                text_parts.append(text)
    match = SUMMARY_RE.search("\n".join(text_parts))
    return (match.group(1).strip() if match else "")[:500]


def _restore_native_history(content):
    blocks = RESTORE_BLOCK_RE.findall(content or "")
    if not blocks:
        return []
    pairs = []
    pending_prompt = None
    for label, body in blocks:
        if label == "Prompt":
            pending_prompt = body
        elif pending_prompt is not None:
            pairs.append((pending_prompt, body))
            pending_prompt = None
    for prompt_body, response_body in reversed(pairs):
        prompt = _native_prompt_obj(prompt_body)
        if prompt is None:
            continue
        prompt_text = _native_prompt_text(prompt)
        restored = list(_native_history_lines(prompt_text))
        if restored:
            summary = _native_response_summary(response_body)
            summary_line = f"[Agent] {summary}" if summary else ""
            if summary_line and (not restored or restored[-1] != summary_line):
                restored.append(summary_line)
            return restored
        user_text = _native_first_user_line(prompt_text)
        summary = _native_response_summary(response_body)
        if user_text and summary:
            return [f"[USER]: {user_text}", f"[Agent] {summary}"]
    return []


def format_restore():
    files = _restore_log_files()
    if not files:
        return None, t("chat.history.not_found")
    latest = max(files, key=os.path.getmtime)
    with open(latest, "r", encoding="utf-8") as f:
        content = f.read()
    restored = _restore_text_pairs(content) or _restore_native_history(content)
    if not restored:
        return None, t("chat.history.no_content")
    count = sum(1 for line in restored if line.startswith("[USER]: "))
    return (restored, os.path.basename(latest), count), None


def build_done_text(raw_text):
    files = [p for p in extract_files(raw_text) if os.path.exists(p)]
    body = strip_files(clean_reply(raw_text))
    if files:
        body = (body + "\n\n" if body else "") + "\n".join(t("chat.generated_file", p) for p in files)
    return body or "..."


def public_access(allowed):
    return not allowed or "*" in allowed


def to_allowed_set(value):
    if value is None:
        return set()
    if isinstance(value, str):
        value = [value]
    return {str(x).strip() for x in value if str(x).strip()}


def allowed_label(allowed):
    return "public" if public_access(allowed) else sorted(allowed)


def ensure_single_instance(port, label):
    try:
        lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_sock.bind(("127.0.0.1", port))
        return lock_sock
    except OSError:
        raise RuntimeError(f"[{label}] Another instance is already running on port {port}")


def require_runtime(agent, label, **required):
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"[{label}] Missing required configuration: {', '.join(missing)}. Please set in mykey.py or mykey.json")
    if agent.llmclient is None:
        raise RuntimeError(f"[{label}] No usable LLM backend found in mykey.py or mykey.json")


def redirect_log(script_file, log_name, label, allowed):
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(script_file))), "temp")
    os.makedirs(log_dir, exist_ok=True)
    logf = open(os.path.join(log_dir, log_name), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = logf
    logger.info("[%s] process starting, redirecting logs", label)
    logger.info("[%s] allow list: %s", label, allowed_label(allowed))


class AgentChatMixin:
    label = "Chat"
    source = "chat"
    split_limit = 1500
    ping_interval = 20

    def __init__(self, agent, user_tasks):
        self.agent, self.user_tasks = agent, user_tasks

    async def send_text(self, chat_id, content, **ctx):
        raise NotImplementedError

    async def send_done(self, chat_id, raw_text, **ctx):
        await self.send_text(chat_id, build_done_text(raw_text), **ctx)

    async def handle_command(self, chat_id, cmd, **ctx):
        parts = (cmd or "").split()
        op = (parts[0] if parts else "").lower()
        if op == "/help":
            return await self.send_text(chat_id, HELP_TEXT, **ctx)
        if op == "/stop":
            state = self.user_tasks.get(chat_id)
            if state:
                state["running"] = False
            self.agent.abort()
            return await self.send_text(chat_id, t("chat.status.stopping"), **ctx)
        if op == "/status":
            llm = self.agent.get_llm_name() if self.agent.llmclient else t("chat.status.not_configured")
            status = t("chat.status.running") if self.agent.is_running else t("chat.status.idle")
            return await self.send_text(chat_id, f"{t('chat.status.label')}: {status}\nLLM: [{self.agent.llm_no}] {llm}", **ctx)
        if op == "/llm":
            if not self.agent.llmclient:
                return await self.send_text(chat_id, t("chat.error.no_llm"), **ctx)
            if len(parts) > 1:
                try:
                    self.agent.next_llm(int(parts[1]))
                    return await self.send_text(chat_id, t("chat.status.switched", self.agent.llm_no, self.agent.get_llm_name()), **ctx)
                except Exception:
                    return await self.send_text(chat_id, t("chat.cmd.llm_usage", len(self.agent.list_llms()) - 1), **ctx)
            lines = [f"{'→' if cur else '  '} [{i}] {name}" for i, name, cur in self.agent.list_llms()]
            return await self.send_text(chat_id, "LLMs:\n" + "\n".join(lines), **ctx)
        if op == "/restore":
            try:
                restored_info, err = format_restore()
                if err:
                    return await self.send_text(chat_id, err, **ctx)
                restored, fname, count = restored_info
                self.agent.abort()
                self.agent.history.extend(restored)
                return await self.send_text(chat_id, t("chat.history.restored", count, fname), **ctx)
            except Exception as e:
                return await self.send_text(chat_id, t("chat.history.restore_failed", e), **ctx)
        if op == "/continue":
            return await self.send_text(chat_id, _handle_continue_frontend(self.agent, cmd), **ctx)
        if op == "/new":
            return await self.send_text(chat_id, _reset_conversation(self.agent), **ctx)
        return await self.send_text(chat_id, HELP_TEXT, **ctx)

    async def run_agent(self, chat_id, text, **ctx):
        state = {"running": True}
        self.user_tasks[chat_id] = state
        try:
            await self.send_text(chat_id, t("chat.status.thinking"), **ctx)
            dq = self.agent.put_task(f"{FILE_HINT}\n\n{text}", source=self.source)
            # Create asyncio.Queue bridge to avoid blocking thread pool
            loop = asyncio.get_running_loop()
            async_queue = asyncio.Queue()
            bridge_stop = threading.Event()

            def _bridge_thread():
                """Background thread: read from threading.Queue, put into asyncio.Queue."""
                while not bridge_stop.is_set():
                    try:
                        item = dq.get(True, 1)
                        loop.call_soon_threadsafe(async_queue.put_nowait, item)
                    except Q.Empty:
                        continue
                    except Exception as exc:
                        loop.call_soon_threadsafe(async_queue.put_nowait, {"error": exc})
                        break
                # Drain remaining items after stop signal
                while True:
                    try:
                        item = dq.get(False)
                        loop.call_soon_threadsafe(async_queue.put_nowait, item)
                    except Q.Empty:
                        break

            import threading
            bridge = threading.Thread(target=_bridge_thread, daemon=True)
            bridge.start()

            last_ping = time.time()
            try:
                while state["running"]:
                    try:
                        item = await asyncio.wait_for(async_queue.get(), timeout=3.0)
                    except asyncio.TimeoutError:
                        if self.agent.is_running and time.time() - last_ping > self.ping_interval:
                            await self.send_text(chat_id, t("chat.status.processing"), **ctx)
                            last_ping = time.time()
                        continue
                    if "error" in item:
                        raise item["error"]
                    if "done" in item:
                        await self.send_done(chat_id, item.get("done", ""), **ctx)
                        break
            finally:
                bridge_stop.set()
                bridge.join(timeout=2.0)

            if not state["running"]:
                await self.send_text(chat_id, t("chat.status.stopped"), **ctx)
        except Exception as e:
            import traceback
            logger.error("[%s] run_agent error: %s", self.label, e, exc_info=True)
            await self.send_text(chat_id, t("chat.error.generic", e), **ctx)
        finally:
            self.user_tasks.pop(chat_id, None)


from agentmain import GeneraticAgent as _GA
from continue_cmd import handle_frontend_command as _handle_continue_frontend, install as _install_continue, reset_conversation as _reset_conversation
_install_continue(_GA)

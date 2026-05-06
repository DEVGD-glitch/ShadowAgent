<div align="center">
<img src="assets/images/bar.jpg" width="880"/>

<a href="https://trendshift.io/repositories/25944" target="_blank"><img src="https://trendshift.io/api/badge/repositories/25944" alt="lsdefine%2FGenericAgent | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

<p align="center">
  <a href="#english">English</a> | <a href="#chinese">中文</a> | <a href="#french">Français</a> | 📄 Technical Report:&nbsp;<a href="https://arxiv.org/abs/2604.17091"><img src="https://img.shields.io/badge/arXiv-2604.17091-b31b1b?logo=arxiv&logoColor=white" alt="arXiv" height="18"/></a>&nbsp;<a href="assets/GenericAgent_Technical_Report.pdf"><img src="https://img.shields.io/badge/-PDF-EA4335?logo=adobeacrobatreader&logoColor=white" alt="Technical Report PDF" height="18"/></a>&nbsp;<a href="https://github.com/JinyiHan99/GA-Technical-Report"><img src="https://img.shields.io/badge/-Code%20%26%20Data-181717?logo=github&logoColor=white" alt="Experiments & Reproduction Repo" height="18"/></a> | 📘 <a href="https://datawhalechina.github.io/hello-generic-agent/">教程</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version 1.0.0"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---
<a name="english"></a>

## What is GenericAgent?

**GenericAgent** is a self-evolving AI agent that controls your computer. You give it a task in plain language — it figures out how to do it, executes it, and remembers how for next time.

Unlike chatbots that just talk, GenericAgent **acts**: it can browse the web, run code, read and write files, and interact with desktop applications. And unlike most agent frameworks that require extensive setup and programming, GenericAgent is designed to **grow its own capabilities** over time — the more you use it, the more skilled it becomes.

### How is it different?

| | GenericAgent | ChatGPT / Claude | AutoGPT / CrewAI |
|---|---|---|---|
| **Can act on your computer** | Yes — browser, terminal, files | No — text only | Varies |
| **Remembers across sessions** | Yes — layered memory + auto-crystallization | No — stateless | Partial |
| **Gets better over time** | Yes — crystallizes skills automatically | No | Manual plugins |
| **Setup complexity** | `python start.py` — one command | Web signup | Complex config |
| **Token efficiency** | <30K context window | Full context | 200K–1M tokens |
| **Multi-LLM** | Claude, GPT, Gemini, DeepSeek, Ollama | Locked to one | Varies |
| **MCP support** | Built-in client + server | No / partial | No |

## Quick Start

### One Command — That's It

```bash
git clone https://github.com/lsdefine/GenericAgent.git
cd GenericAgent
python start.py
```

That's the entire setup. `start.py` does everything:

1. **Checks dependencies** — auto-installs any missing Python packages
2. **Runs setup wizard** — on first launch, a **GUI onboarding wizard** (5 steps: Welcome → Provider → API Key → Connection Test → Ready) guides you through setup
3. **Launches the best UI** — Qt desktop app if available, otherwise Streamlit web, otherwise terminal

> **Requirements**: Python 3.10+ and an internet connection. That's all.
>
> **API key needed**: You'll need at least one LLM API key (Anthropic, OpenAI, Google Gemini, DeepSeek, or a local Ollama instance). The onboarding wizard will guide you. API keys are stored in your **OS keyring** by default (not in a plaintext file).

### Other Ways to Start

| Method | Command | Best For |
|--------|---------|----------|
| **Auto (recommended)** | `python start.py` | Everyone — first time and beyond |
| **Reconfigure** | `python start.py --configure` | Change API key, provider, or language |
| **Terminal mode** | `python start.py --cli` | Headless servers, scripting |
| **API server** | `python start.py --server` | Integration with other apps |
| **Service hub** | `python start.py --hub` | Managing multiple frontends |
| **Qt desktop** | `python frontends/qtapp.py` | Desktop users with PySide6 installed |
| **Docker** | `docker build -t genericagent . && docker run -e LLM_API_KEY=sk-... genericagent` | Deployment |

### First Time Setup

When you run `python start.py` for the first time and Qt is available, you'll see a **GUI onboarding wizard** with 5 steps:

1. **Welcome** — Introduction to GenericAgent
2. **Provider selection** — Choose your LLM provider (OpenAI, Anthropic, Google, Ollama)
3. **API Key input** — Enter your key (with show/hide toggle and "Get a key" link)
4. **Connection test** — Verifies your key works with a live test call
5. **Ready** — Start chatting!

Your API key is stored securely in the **OS keyring** (macOS Keychain, Windows Credential Manager, or Linux Secret Service). If the keyring is unavailable, it falls back to an **encrypted file** at `~/.genericagent/credentials.enc`.

If Qt is not available, `start.py` falls back to a terminal-based setup wizard.

## What Can It Do?

GenericAgent gives an LLM **9 atomic tools** to control your computer:

| Tool | What it does |
|------|-------------|
| `code_run` | Execute Python, Bash, or PowerShell code in a subprocess. **Has path traversal protection** — cannot write outside the workspace directory. |
| `file_read` | Read any file with keyword search and line-number support |
| `file_write` | Write, append, or prepend content to files. **Path traversal protected** — stays within workspace. |
| `file_patch` | Modify existing files (find & replace). **Path traversal protected**. |
| `web_scan` | Read web page content through a real browser |
| `web_execute_js` | Run JavaScript in the browser (click, type, scroll) |
| `ask_user` | Ask you a question when unsure |

Plus 2 **memory management tools** that let it save and recall information across sessions.

> **Security note**: Shell commands that match dangerous patterns (`rm`, `del`, `shutdown`, `sudo rm`, etc.) require **user confirmation** before execution. In headless mode, dangerous commands are **blocked by default** unless `--allow-dangerous-shell` is passed.

### Real-World Examples

| What you say | What GenericAgent does |
|---|---|
| "Read my WeChat messages" | Installs dependencies, reverses the database, writes a read script, saves as a skill |
| "Monitor stocks and alert me when price drops 5%" | Installs market data tools, builds a screening flow, configures scheduled checks, saves as a skill |
| "Send this file via Gmail" | Configures OAuth, writes a send script, saves as a skill |
| "Order me a milk tea" | Opens the delivery app in browser, navigates the menu, selects items, completes checkout |

**The first time**, GenericAgent explores, experiments, and figures out how to complete the task. **Every time after**, it recalls the crystallized skill and executes it directly.

## How Self-Evolution Works

This is what makes GenericAgent fundamentally different from other agents:

```
New Task → Autonomous Exploration (install deps, write scripts, debug)
         → Crystallize execution path into a reusable Skill
         → Write to Memory Layer
         → Direct recall on next similar task
```

The agent uses a **5-layer memory system**:

| Layer | Purpose |
|-------|---------|
| **L0** — Meta Rules | Core behavioral constraints |
| **L1** — Insight Index | Fast routing index for quick recall |
| **L2** — Global Facts | Stable long-term knowledge |
| **L3** — Task Skills / SOPs | Reusable step-by-step procedures |
| **L4** — Session Archive | Historical task records |

After 15+ conversation turns, the **auto-crystallization engine** automatically:
1. Triggers skill crystallization of the current execution path
2. Updates the L1 insight index for fast routing
3. Persists key information checkpoints to disk
4. Indexes new skills in the vector store for semantic retrieval

Next time you ask something similar, the agent finds and reuses the skill — **one-line invoke from memory**.

## v1.0.0 — What's New

Version 1.0.0 is a **security and UX hardening** release, fixing issues identified during a comprehensive audit. It also fixes the inverted semver (v0.6.0 was erroneously higher than the original v1.0).

### Security

| Change | Why |
|--------|-----|
| `factuality_check` guardrail **REMOVED** | It censored honest AI responses — AI answers with 3+ uncertainty markers (e.g. "I'm not sure") were blocked, punishing epistemic humility |
| `no_code_injection` and `no_pii_leak` guardrails **DISABLED by default** | Too many false positives on legitimate inputs (markdown code blocks, email addresses, config values with backticks) — can be re-enabled individually |
| **Path traversal protection** in `code_run` and `file_ops` | All file operations now validate that resolved paths stay within the workspace directory — prevents `../../etc/passwd` attacks |
| Auto-update: **Ed25519 signature verification is MANDATORY** | Updates without a valid signature are rejected (fail-closed). If no public key is configured, updates are blocked entirely |
| `mykey.py` is **DEPRECATED** with `DeprecationWarning` | API keys stored in plaintext Python files are a security risk. Migration to OS keyring via `credential_store.py` |
| Builtin tools unified in **registry** for specialist tool isolation | The 9 builtin tools are registered with full metadata in `tools/registry.py`, enabling proper specialist-based tool restriction for sub-agents |

### Internationalization (i18n)

- Full migration of all frontends to the `t()` function — **209 i18n keys** across `en.json`, `fr.json`, `zh.json`
- Categories: error messages, UI labels, browser, LLM, setup wizard, chat, circuit breaker, Qt-specific
- Pre-commit hook for i18n key consistency (`scripts/check_i18n_strings.py`)

### Performance

- Fixed **thread pool exhaustion** — replaced with `asyncio.Queue` bridge for display queue
- **ContextEngine auto-activated** with automatic compaction when context window fills
- **Circuit breaker emits events** to the UI — users now see a banner when a provider is unavailable, with countdown to retry

### Desktop UX

| Change | Why |
|--------|-----|
| **Normal window mode** by default | The app now appears in the taskbar and is Alt+Tab accessible. Use `--overlay` flag for old always-on-top behavior |
| **Onboarding wizard** (5 steps) on first launch | GUI-guided setup instead of terminal prompts — provider selection, key input, live connection test |
| **User-friendly error messages** | Python exceptions are mapped to human-readable messages with suggested actions (e.g. "API key invalid" → "Check your settings") |
| **Colors centralized** in `theme.py` + external `dark.qss` | Immutable `Theme` dataclass with dynamic CSS generation; no more scattered color constants |
| **Auto-update notification banner** in ChatPanel | Users see a banner when a new version is available, with "Update" and "Later" buttons |
| **HiDPI responsive** layout | No more `setFixedSize` — the app adapts to high-DPI screens properly |

### Code Quality

- **ga.py refactored**: from ~9,600 lines to ~941 lines — tools extracted to the `tools/` package (`code_run.py`, `file_ops.py`, `web_tools.py`)
- **Test coverage target**: 80% with 10 E2E tests using LLM stubs
- Pre-commit hook for i18n key consistency

## v0.6.0 — "Big Tech Monster"

Version 0.6.0 extracts the best patterns from 12 open-source AI agent frameworks and unifies them into GenericAgent. Each feature is lazy-loaded (only initialized when you use it) and gracefully degrades if dependencies are missing.

### What's New

| Feature | What it gives you | Inspired by |
|---------|-------------------|-------------|
| **StateGraph** | Build structured workflows with nodes, edges, and conditional branching | LangGraph |
| **MCP Server** | Expose GenericAgent's tools to any MCP-compatible client | MCP Python SDK |
| **Chroma Memory** | Persistent vector database for semantic memory search | ChromaDB |
| **Closed Learning Loop** | 5-phase cycle: Discover → Execute → Reflect → Codify → Improve | Hermes Agent |
| **Progressive Skill Disclosure** | Only show relevant skills to the LLM, reducing noise | Google ADK |
| **Agent Handoffs** | Route tasks to specialist sub-agents | OpenAI Agents SDK |
| **Agent-as-Tool** | Use one agent as a tool inside another agent's workflow | OpenAI Agents SDK |
| **Sandbox Execution** | Run untrusted code in an isolated subprocess | OpenAI Agents SDK |
| **Input/Output Guardrails** | Automatic validation of user input and agent output | OpenAI Agents SDK |
| **Extension Lifecycle Hooks** | Plugin system with before/after hooks on agent events | pi-mono |
| **Context Compaction** | Smart context window management to stay within token limits | pi-mono |
| **Flow Serialization** | Define agent workflows as JSON graphs | Langflow |
| **Flow-as-MCP-Server** | Expose a flow as an MCP tool for external consumption | Langflow |
| **DOM Intelligence** | Parse web pages into indexed interactive elements | Browser-Use |
| **Browser Agent** | Autonomous web browsing: observe → decide → act | Browser-Use |
| **Voice Pipeline** | Speech-to-text → LLM → text-to-speech, with FREE providers | AIAvatarKit |
| **VRM Avatar** | 3D anime/waifu avatar with lip-sync + VRoid Hub | AIAvatarKit / VRoid Hub |
| **Speech-to-Speech** | Full voice conversation with anime personality | AIAvatarKit |
| **Free Providers** | 100% free voice pipeline (Groq STT + Edge TTS + Pollinations LLM) | — |

### Free AI Providers — Zero Cost Voice & Chat

GenericAgent supports **completely free** providers for the voice and avatar pipeline. No API key needed for the default configuration:

| Component | Free Provider | Limits | Alternative (also free) |
|-----------|--------------|--------|------------------------|
| **STT** (Speech-to-Text) | Groq Whisper | 30 req/min | Pollinations (unlimited), local Whisper |
| **TTS** (Text-to-Speech) | Edge TTS | Unlimited, 400+ voices | VOICEVOX (anime voices, local), Pollinations |
| **LLM** (Chat) | Pollinations | Unlimited | Groq (30 req/min), UncloseAI, DeepInfra, OpenRouter |

### Anime Avatar with Personality

Give your agent a waifu/anime identity with VRM avatars from [VRoid Hub](https://hub.vroid.com):

```python
from agentmain import SpeechToSpeechEngine

# Create a 100% FREE pipeline with anime personality
engine = SpeechToSpeechEngine.create_free_pipeline(
    language="ja-JP",       # Japanese for anime
    personality="waifu",    # or: tsundere, kuudere, dandere, genki, oneesan, loli
    avatar_path="my_waifu.vrm",
)

# Text-based interaction (no microphone needed)
response = engine.process_text("Bonjour !")
print(response.text)     # The agent's text response
# response.audio contains the synthesized voice
# response.expression contains the detected expression
# response.visemes contains lip-sync data

# Or use individual components
from agentmain import VoicePipeline, LLMVoiceClient, AvatarController, STTProvider, TTSProvider

# Free STT + TTS
pipeline = VoicePipeline(stt_provider=STTProvider.GROQ, tts_provider=TTSProvider.EDGE)

# Free LLM with anime personality
llm = LLMVoiceClient()  # Defaults to Pollinations (free)
llm.set_personality("tsundere")  # "B-baka! It's not like I care..."

# VRM Avatar with expression tags
avatar = AvatarController("avatar.vrm")
text, expression = avatar.parse_expression_tags("Hello [face:joy] !")
# → text="Hello !", expression="happy"
```

**Available anime personalities**: waifu, tsundere, kuudere, dandere, genki, oneesan, loli

**VRM Avatar Viewer**: Open `assets/avatar_viewer.html` in a browser for a full 3D VRM viewer with:
- Drag-and-drop VRM loading
- Expression control (happy, angry, sad, surprised, etc.)
- Auto-blink and breathing animation
- WebSocket connection to GenericAgent for real-time control
- Direct link to VRoid Hub for downloading avatars

### Using v0.6.0 Features from Python

```python
from agentmain import GenericAgent

agent = GenericAgent()

# Search memory semantically
results = agent.search_memory("How did I automate stock screening?")

# Validate input/output
agent.validate_input("Hello, help me code")  # GuardrailResult(passed=True)

# Build a StateGraph workflow
graph = agent.build_state_graph()
graph.add_node("think", think_fn)
graph.add_node("act", act_fn)
graph.add_edge("think", "act")
graph.add_conditional_edges("act", route_fn, {"retry": "think", "done": "__end__"})

# Register an MCP tool
@agent.register_mcp_tool()
def search_web(query: str, num: int = 10) -> str:
    """Search the web."""
    return do_search(query, num)

# Run the closed learning loop
result = agent.closed_learning.run_full_cycle("Analyze quarterly sales")

# Enable voice conversation
agent.enable_voice(stt_provider="google", tts_provider="google")

# Enable 3D avatar
agent.enable_avatar(avatar_path="my_avatar.vrm")

# Create a flow
flow = agent.create_flow("research_flow", "Research and summarize a topic")
```

## Chat Interfaces

GenericAgent supports multiple ways to interact:

### Desktop App (Recommended)

```bash
python start.py          # Auto-detects and launches the best available UI
```

The Qt desktop interface features:
- Real-time tool call visualization with status badges
- Collapsible reasoning display
- Animated agent status indicator (6 states)
- Security approval dialogs for dangerous actions
- Command palette (Ctrl+K) with fuzzy search
- Dark, Light, and Catppuccin themes
- System tray with notifications
- Drag & drop file support
- **Onboarding wizard** (5-step guided setup on first launch)
- **User-friendly error messages** with suggested actions
- **Auto-update notifications** (banner in ChatPanel when new version available)
- **Circuit breaker banner** (shows when LLM provider is unavailable, with retry countdown)

The desktop app now runs in **normal window mode** by default — it appears in the taskbar and is accessible via Alt+Tab. To restore the old always-on-top overlay behavior:

```bash
python frontends/qtapp.py --overlay
```

### Terminal

```bash
python start.py --cli
```

Chat commands available in all interfaces:
- `/new` — Start a fresh conversation
- `/continue` — List recoverable session snapshots
- `/continue N` — Restore the Nth session

### Messaging Platforms

GenericAgent can run as a bot on:

| Platform | Setup |
|----------|-------|
| **Telegram** | Add `tg_bot_token` to `mykey.py` or keyring, run `python frontends/tgapp.py` |
| **WeChat** | `pip install pycryptodome qrcode`, run `python frontends/wechatapp.py` |
| **QQ** | Add `qq_app_id`/`qq_app_secret` to `mykey.py` or keyring, run `python frontends/qqapp.py` |
| **Feishu/Lark** | Add `fs_app_id`/`fs_app_secret` to `mykey.py` or keyring, run `python frontends/fsapp.py` |
| **WeCom** | Add `wecom_bot_id`/`wecom_secret` to `mykey.py` or keyring, run `python frontends/wecomapp.py` |
| **DingTalk** | Add `dingtalk_client_id`/`dingtalk_client_secret` to `mykey.py` or keyring, run `python frontends/dingtalkapp.py` |
| **Discord** | Run `python frontends/dcapp.py` |

> **Note**: `mykey.py` is **deprecated** and will show a `DeprecationWarning` at startup. For messaging platform credentials, the recommended approach is to use the **credential store** (OS keyring). See the Configuration section below.

### API Server

```bash
python start.py --server    # Starts on http://0.0.0.0:8765
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Streaming SSE chat |
| `/chat/sync` | POST | Synchronous chat |
| `/ws/chat` | WebSocket | Full-duplex chat |
| `/tools` | GET | List available tools |
| `/models` | GET | List LLM models |
| `/models/switch` | POST | Switch model |
| `/memory/search` | POST | Semantic memory search |
| `/status` | GET | Agent status |
| `/mcp/status` | GET | MCP server status |

## Supported LLM Providers

| Provider | Models | Config Key |
|----------|--------|------------|
| **Anthropic** | Claude Sonnet 4, Claude Opus 4 | `native_claude_config` |
| **OpenAI** | GPT-4o, GPT-5 | `native_oai_config` |
| **Google** | Gemini 2.5 Pro, Gemma | `google_config` |
| **DeepSeek** | DeepSeek Chat, DeepSeek Coder | `native_oai_config` (with DeepSeek base URL) |
| **Local (Ollama)** | Llama 3, Mistral, Qwen, etc. | `native_oai_config` (with Ollama URL) |
| **Mixin (failover)** | Any combination above | `mixin_config` |

You can configure multiple providers and GenericAgent will automatically fail over if one is down.

## Project Structure

```
GenericAgent/
├── start.py                    # ONE command to start everything
├── configure.py                # CLI configuration wizard
├── check_dependencies.py       # Dependency checker + auto-installer
├── hub.pyw                     # Service manager (tkinter)
├── launch.pyw                  # Streamlit + pywebview launcher
├── launch_desktop.py           # Qt desktop launcher (PyInstaller-ready)
│
├── agentmain/                  # Core agent package
│   ├── core.py                 # GenericAgent class — main orchestrator
│   ├── cli.py                  # CLI entry point (interactive/task/reflect modes)
│   ├── prompts.py              # Tool schemas, system prompts
│   ├── slash.py                # Slash command handler
│   ├── handoffs.py             # Agent handoffs + Agent-as-Tool + Sandbox
│   ├── guardrails.py           # Input/Output validation pipeline
│   ├── closed_learning.py      # 5-phase learning loop + SkillToolset
│   ├── extensions.py           # Extension lifecycle hooks + ContextEngine
│   ├── flow.py                 # Flow graph serialization + Flow-as-MCP
│   ├── browser_intel.py        # DOM extraction + BrowserAgent
│   ├── voice_avatar.py         # Voice pipeline + VRM avatar + VRoid Hub
│   ├── credential_store.py     # OS keyring + encrypted fallback for API keys
│   ├── auto_update.py          # Auto-update with Ed25519 signature verification
│   ├── safe_eval.py            # SafeExpressionEvaluator (AST allowlist)
│   ├── event_bus.py            # Event bus for decoupled subsystem communication
│   └── crash_reporter.py       # Crash reporting
│
├── ga.py                       # Tool handler (GenericAgentHandler) — re-exports from tools/
├── agent_loop.py               # Agent execution loop
├── server.py                   # FastAPI + SSE + WebSocket API server
├── config.py                   # Configuration dataclasses
├── exceptions.py               # 28-class exception hierarchy
├── protocols.py                # Protocol definitions
├── circuit_breaker.py          # LLM call circuit breaker (emits events to UI)
├── metrics.py                  # LLM metrics tracking
├── logging_config.py           # Centralized logging
├── env_loader.py               # .env file support
│
├── tools/                      # Tool implementations (extracted from ga.py)
│   ├── __init__.py             # Package init — re-exports from registry
│   ├── registry.py             # ToolRegistry + @register_tool + builtin tool definitions
│   ├── validation.py           # JSON Schema validation
│   ├── code_run.py             # Code execution + path traversal protection
│   ├── file_ops.py             # File I/O + path traversal protection
│   └── web_tools.py            # Browser / web-scanning utilities
│
├── llmcore/                    # LLM abstraction layer
│   ├── clients.py              # Multi-LLM client (Claude, OpenAI, Gemini...)
│   ├── google_provider.py      # Google AI Studio session
│   ├── sessions.py             # Session management with failover
│   ├── parsers.py              # Response parsing
│   ├── messages.py             # Message format conversion
│   ├── retry.py                # Exponential backoff + jitter
│   └── convert.py              # Tool format converters
│
├── engine/                     # StateGraph engine
│   └── state_graph.py          # Graph, nodes, edges, checkpointer
│
├── mcp/                        # Model Context Protocol
│   ├── client.py               # MCP client (stdio/SSE/HTTP)
│   └── fastmcp.py              # FastMCP server
│
├── memory/                     # Layered memory system
│   ├── crystallization.py      # Auto-crystallization engine
│   ├── vector/                 # Vector store + RAG + ChromaDB
│   └── (L0-L4 layers)         # SOPs, skills, session archives
│
├── plugins/                    # Dynamic tool plugins
│   ├── tools/                  # Built-in tool plugins
│   │   ├── web_search.py       # DuckDuckGo / SearXNG search
│   │   ├── memory_search.py    # Semantic memory search
│   │   ├── skill_search_tool.py # Skill search
│   │   └── system_tools.py     # System info, directory tree, processes
│   └── langfuse_tracing.py     # Optional Langfuse tracing
│
├── frontends/                  # UI frontends
│   ├── qt/                     # Modern Qt desktop UI (modular)
│   │   ├── pages/
│   │   │   ├── chat_page.py    # Chat interface
│   │   │   ├── onboarding_page.py  # 5-step onboarding wizard
│   │   │   ├── settings_page.py    # Settings
│   │   │   ├── history_page.py     # Session history
│   │   │   └── sop_page.py        # SOP management
│   │   ├── theme.py            # Centralized Theme dataclass + dynamic CSS
│   │   ├── error_mapper.py     # Exception → user-friendly error messages
│   │   ├── command_palette.py  # Ctrl+K command palette
│   │   ├── stream_handler.py  # Stream display handler
│   │   ├── session_manager.py  # Session persistence
│   │   └── floating_button.py  # Overlay mode floating button
│   ├── qtapp.py                # Qt app entry point (supports --overlay)
│   ├── stapp.py / stapp2.py    # Streamlit web UI
│   ├── tgapp.py                # Telegram bot
│   ├── wechatapp.py            # WeChat bot
│   ├── qqapp.py                # QQ bot
│   ├── fsapp.py                # Feishu/Lark bot
│   ├── wecomapp.py             # WeCom bot
│   ├── dingtalkapp.py          # DingTalk bot
│   └── dcapp.py                # Discord bot
│
├── i18n/                       # Internationalization (209 keys)
│   ├── en.json                 # English
│   ├── fr.json                 # Français
│   └── zh.json                 # 中文
│
├── build/                      # Build & packaging
│   ├── installer.nsi           # NSIS installer script (requires makensis to build)
│   ├── build_windows.py        # Windows build script
│   ├── build_macos.sh          # macOS build script
│   └── autoupdate.py           # Auto-update build integration
│
├── tests/                      # Test suite (target: 80% coverage)
├── stubs/                      # Type stubs
└── assets/                     # Static assets
    └── themes/
        └── dark.qss            # External dark theme stylesheet template
```

## Configuration

### Recommended: OS Keyring (v1.0.0+)

The **recommended** way to store API keys is via the **credential store**, which uses your operating system's secure keychain:

- **macOS**: Keychain
- **Windows**: Credential Manager
- **Linux**: Secret Service (e.g. GNOME Keyring)

The onboarding wizard automatically stores your API key in the keyring. You can also use the CLI:

```bash
# Migrate existing mykey.py credentials to the keyring
python -m agentmain.credential_store --migrate
```

When the OS keyring is unavailable, the credential store falls back to an **encrypted file** at `~/.genericagent/credentials.enc` (Fernet encryption with PBKDF2-derived key, 600K iterations per OWASP 2023).

### Legacy: mykey.py (Deprecated)

`mykey.py` still works but shows a `DeprecationWarning` at startup:

```
DeprecationWarning: mykey.py is DEPRECATED and will be removed in v1.0.
Migrate to credential_store.py (OS keyring).
Run: python -m agentmain.credential_store --migrate
```

To use `mykey.py`, copy the template and fill in your keys:

```bash
cp mykey_template.py mykey.py
# Edit mykey.py with your API keys
```

```python
# mykey.py — Legacy configuration (DEPRECATED)

mixin_config = {
    'llm_nos': ['gpt-native'],   # Provider names in priority order
    'max_retries': 10,
    'base_delay': 0.5,
}

native_oai_config = {
    'name': 'gpt-native',
    'apikey': 'sk-your-key-here',
    'apibase': 'https://api.openai.com/v1',
    'model': 'gpt-4o',
    'api_mode': 'chat_completions',
}

native_claude_config = {
    'name': 'claude',
    'apikey': 'sk-ant-your-key-here',
    'apibase': 'https://api.anthropic.com',
    'model': 'claude-sonnet-4-6',
    'thinking_type': 'adaptive',
}
```

Alternatively, you can use environment variables (see `.env.example`).

## Security

GenericAgent applies security at **5 layers** (from network to data protection):

| Layer | Protections |
|-------|-------------|
| **1. Network** | HTTPS, CORS (localhost only), rate limiting (30 req/min on `/chat`) |
| **2. Authentication** | JWT/Bearer tokens, WebSocket token validation, origin checking |
| **3. Input Validation** | Input guardrails, session attribute allowlist, **path traversal prevention** (`os.path.realpath` check), file size limits (10 MB) |
| **4. Code Execution** | SafeExpressionEvaluator (AST allowlist), `eval()`/`exec()` removed, **shell command confirmation** for dangerous patterns, API keys in OS keyring (not in source) |
| **5. Data Protection** | Log anonymization (API key redaction), encrypted credential fallback (Fernet), **signed auto-updates** (Ed25519, fail-closed), zip slip prevention |

### Key security decisions in v1.0.0:

- **`factuality_check` removed**: This guardrail blocked AI responses containing uncertainty markers like "I'm not sure" — epistemic humility is a safety feature, not a bug
- **`no_code_injection` / `no_pii_leak` disabled by default**: These produced too many false positives (markdown code blocks, email addresses in configs). They can be re-enabled via `add_input_guardrail()` after testing
- **Path traversal protection**: All file operations in `code_run` and `file_ops` validate that resolved paths stay within the workspace directory
- **Ed25519 mandatory for updates**: Auto-update rejects any package without a valid Ed25519 signature. If no public key is configured, updates are blocked entirely (fail-closed)
- **mykey.py deprecated**: Storing API keys in plaintext Python files is a security risk. Use the OS keyring

## Demo

| 🧋 Food Delivery | 📈 Stock Screening |
|:---:|:---:|
| <img src="assets/demo/order_tea.gif" width="100%" alt="Order Tea"> | <img src="assets/demo/selectstock.gif" width="100%" alt="Stock Selection"> |
| *"Order me a milk tea"* — Navigates the delivery app, selects items, and completes checkout | *"Find GEM stocks with EXPMA golden cross, turnover > 5%"* — Screens stocks with quantitative conditions |
| 🌐 Autonomous Web Exploration | 💰 Expense Tracking | 💬 Batch Messaging |
| <img src="assets/demo/autonomous_explore.png" width="100%" alt="Web Exploration"> | <img src="assets/demo/alipay_expense.png" width="100%" alt="Alipay Expense"> | <img src="assets/demo/wechat_batch.png" width="100%" alt="WeChat Batch"> |
| Autonomously browses and periodically summarizes web content | *"Find expenses over ¥2K in the last 3 months"* — Drives Alipay via ADB | Sends bulk WeChat messages, fully driving the WeChat client |

## FAQ

**Q: Do I need to be a programmer to use GenericAgent?**
No. The `python start.py` command handles everything. You just need Python 3.10+ and an API key from any LLM provider. The GUI onboarding wizard walks you through setup.

**Q: Which LLM provider should I use?**
Any will work. Claude and GPT are the most capable; DeepSeek is the most affordable; Ollama is free but requires a powerful GPU. You can configure multiple providers and GenericAgent will fail over automatically.

**Q: Is my data safe?**
GenericAgent runs entirely on your local machine. API keys are stored securely in your **OS keyring** (or encrypted file fallback). No data is sent anywhere except to your chosen LLM provider for inference. The browser sessions preserve your login state locally.

**Q: Can I use GenericAgent without a browser?**
Yes. The browser control is one tool among many. GenericAgent can also work purely through code execution, file operations, and terminal commands.

**Q: What's the difference between GenericAgent and Claude Code / Cursor?**
Claude Code and Cursor are coding assistants. GenericAgent is a general-purpose computer agent — it can code, but also browse the web, manage files, send messages, and automate any desktop task. It also remembers across sessions and builds skills over time.

**Q: How do I add new capabilities?**
Just ask GenericAgent to do something new. It will figure out how, and automatically save the procedure as a skill. You can also register custom tools via the plugin system or MCP.

**Q: What happened to mykey.py?**
`mykey.py` is deprecated in v1.0.0. It still works but shows a `DeprecationWarning`. The recommended way to store API keys is now the **OS keyring** via `credential_store.py`. To migrate, run: `python -m agentmain.credential_store --migrate`

**Q: How do I build the Windows installer?**
An NSIS installer script exists at `build/installer.nsi`, but you need to run `makensis` to build the `.exe` — it is not a pre-built executable.

## Changelog

- **v1.0.0** (2026-05-05) — Security & UX hardening: path traversal protection, Ed25519 mandatory for auto-update, factuality_check removed, no_code_injection/no_pii_leak disabled by default, mykey.py deprecated (keyring migration), GUI onboarding wizard, user-friendly error messages, normal window mode, auto-update notifications, circuit breaker UI banner, i18n migration (209 keys), ga.py refactored (~9600→941 lines, tools extracted to tools/ package), test coverage target 80%
- **v0.6.0** (2026-05-04) — "Big Tech Monster": 18 new features from 12 open-source frameworks — StateGraph, MCP Server, Chroma Memory, Closed Learning, Agent Handoffs, Guardrails, Extensions, Flow, Browser Agent, Voice Pipeline, VRM Avatar
- **v0.5.0** (2026-05-03) — Auto-crystallization engine, production hardening (52 issues audited, all critical fixed)
- **v0.4.0** (2026-05-02) — Dynamic tool plugins, MCP client, vector memory/RAG, multi-agent orchestration, FastAPI server, reasoning modes, Qt UI
- **v0.3.0** (2026-04-21) — Technical report on arXiv, L4 session archives
- **v0.1.0** (2026-01-16) — Initial public release

## Support

If this project helped you, please consider leaving a **Star!**

<div align="center">
  <table>
    <tr>
      <td align="center"><strong>WeChat Group 13</strong><br><img src="assets/images/wechat_group13.jpg" alt="WeChat Group 13 QR Code" width="250"/></td>
    </tr>
  </table>
</div>

## Friendly Links

[![LinuxDo](https://img.shields.io/badge/社区-LinuxDo-blue?style=for-the-badge)](https://linux.do/)

## License

MIT License — see [LICENSE](LICENSE)

*Disclaimer: This project does not build or operate any commercial website. Apart from DintalClaw, no institution, organization, or individual is currently officially authorized to conduct commercial activities under the GenericAgent name.*

---
<a name="chinese"></a>

## GenericAgent 是什么？

**GenericAgent** 是一个自我进化的 AI 代理，可以控制你的电脑。你用自然语言给它一个任务——它会自己弄清楚怎么做、执行，并记住方法以便下次直接使用。

与只会对话的聊天机器人不同，GenericAgent **会行动**：它可以浏览网页、运行代码、读写文件、操作桌面应用。与大多数需要大量配置和编程的代理框架不同，GenericAgent 的设计理念是 **随使用时间自动增长能力**——用得越多，技能越多。

### 有什么不同？

| | GenericAgent | ChatGPT / Claude | AutoGPT / CrewAI |
|---|---|---|---|
| **能操作你的电脑** | 能——浏览器、终端、文件 | 不能——仅文本 | 不确定 |
| **跨会话记忆** | 有——分层记忆 + 自动结晶 | 没有——无状态 | 部分 |
| **越用越强** | 是——自动结晶技能 | 不是 | 手动插件 |
| **安装复杂度** | `python start.py` — 一条命令 | 网页注册 | 复杂配置 |
| **Token 效率** | <30K 上下文窗口 | 全量上下文 | 200K–1M tokens |
| **多 LLM 支持** | Claude, GPT, Gemini, DeepSeek, Ollama | 绑定一个 | 不确定 |
| **MCP 支持** | 内置客户端 + 服务器 | 无/部分 | 无 |

## 快速开始

### 一条命令——就这么简单

```bash
git clone https://github.com/lsdefine/GenericAgent.git
cd GenericAgent
python start.py
```

这就是全部安装过程。`start.py` 自动完成：

1. **检查依赖** — 自动安装缺失的 Python 包
2. **运行设置向导** — 首次启动时显示 **GUI 引导向导**（5 步：欢迎 → 选择服务商 → 输入 API Key → 连接测试 → 就绪）
3. **启动最佳界面** — Qt 桌面应用 > Streamlit 网页 > 终端

> **系统要求**：Python 3.10+ 和网络连接。就这些。
>
> **需要 API Key**：至少一个 LLM API Key（Anthropic、OpenAI、Google Gemini、DeepSeek 或本地 Ollama）。引导向导会引导你。API Key 默认存储在 **OS 密钥链** 中（不是明文文件）。

### 其他启动方式

| 方式 | 命令 | 适用场景 |
|------|------|----------|
| **自动（推荐）** | `python start.py` | 所有人 |
| **重新配置** | `python start.py --configure` | 更换 API Key 或服务商 |
| **终端模式** | `python start.py --cli` | 服务器、脚本 |
| **API 服务器** | `python start.py --server` | 与其他应用集成 |
| **服务管理** | `python start.py --hub` | 管理多个前端 |

## 它能做什么？

GenericAgent 通过 **9 个原子工具** 让 LLM 控制你的电脑：

| 工具 | 功能 |
|------|------|
| `code_run` | 执行 Python/Bash/PowerShell 代码。**具有路径穿越保护** — 不能写入工作区以外的目录 |
| `file_read` | 读取文件 |
| `file_write` | 写入文件。**路径穿越保护** — 限制在工作区内 |
| `file_patch` | 修改文件（查找替换）。**路径穿越保护** |
| `web_scan` | 通过浏览器读取网页内容 |
| `web_execute_js` | 在浏览器中执行 JS（点击、输入、滚动） |
| `ask_user` | 不确定时向你提问 |

还有 2 个 **记忆管理工具**，让代理可以跨会话保存和召回信息。

> **安全说明**：匹配危险模式（`rm`、`del`、`shutdown`、`sudo rm` 等）的 Shell 命令在执行前需要 **用户确认**。无界面模式下，危险命令 **默认被阻止**，除非传入 `--allow-dangerous-shell`。

## 自我进化机制

```
新任务 → 自主探索（安装依赖、编写脚本、调试）
      → 将执行路径结晶为可复用技能
      → 写入记忆层
      → 下次同类任务直接调用
```

5 层记忆系统：L0 元规则 → L1 索引 → L2 全局知识 → L3 任务技能 → L4 会话归档

15+ 轮对话后，自动结晶引擎触发：技能保存 → 索引更新 → 检查点持久化 → 向量索引

## v1.0.0 — 新增内容

v1.0.0 是一个 **安全和用户体验加固** 版本，修复了综合审计中发现的问题，同时修正了版本号倒置问题（v0.6.0 错误地高于原始 v1.0）。

### 安全改进

| 变更 | 原因 |
|------|------|
| `factuality_check` 护栏 **已移除** | 它审查了诚实的 AI 回复——包含 3 个以上不确定性标记（如"我不确定"）的回答会被阻止，惩罚了认知谦逊 |
| `no_code_injection` 和 `no_pii_leak` 护栏 **默认禁用** | 误报太多（Markdown 代码块、邮箱地址、含反引号的配置值）——可单独重新启用 |
| `code_run` 和 `file_ops` 添加 **路径穿越保护** | 所有文件操作验证解析后的路径是否在工作区内——防止 `../../etc/passwd` 攻击 |
| 自动更新：**Ed25519 签名验证为强制** | 没有有效签名的更新被拒绝（失败即关闭）。未配置公钥时，更新完全被阻止 |
| `mykey.py` **已弃用**，显示 `DeprecationWarning` | 明文 Python 文件存储 API Key 有安全风险。迁移到 OS 密钥链 |
| 内置工具统一注册到 **registry**，支持专家工具隔离 | 9 个内置工具在 `tools/registry.py` 中注册完整元数据，实现子代理专家工具限制 |

### 国际化 (i18n)

- 所有前端完全迁移到 `t()` 函数 — **209 个 i18n 键**，覆盖 `en.json`、`fr.json`、`zh.json`
- 分类：错误消息、UI 标签、浏览器、LLM、设置向导、聊天、熔断器、Qt 特定
- i18n 键一致性预提交钩子（`scripts/check_i18n_strings.py`）

### 性能

- 修复 **线程池耗尽** — 替换为 `asyncio.Queue` 桥接显示队列
- **ContextEngine 自动激活**，上下文窗口填满时自动压缩
- **熔断器向 UI 发送事件** — 用户现在可以看到服务商不可用的横幅，带重试倒计时

### 桌面用户体验

| 变更 | 原因 |
|------|------|
| 默认 **普通窗口模式** | 应用现在出现在任务栏，可通过 Alt+Tab 切换。使用 `--overlay` 恢复旧的置顶行为 |
| 首次启动显示 **引导向导**（5 步） | GUI 引导设置取代终端提示——服务商选择、密钥输入、实时连接测试 |
| **用户友好的错误消息** | Python 异常映射为可读消息并提供建议操作 |
| 颜色集中到 `theme.py` + 外部 `dark.qss` | 不可变 `Theme` dataclass + 动态 CSS 生成；不再有分散的颜色常量 |
| ChatPanel 中 **自动更新通知横幅** | 新版本可用时显示横幅，含"更新"和"稍后"按钮 |
| **HiDPI 响应式** 布局 | 不再使用 `setFixedSize` — 应用正确适配高 DPI 屏幕 |

### 代码质量

- **ga.py 重构**：从约 9,600 行减至约 941 行 — 工具提取到 `tools/` 包
- **测试覆盖率目标**：80%，含 10 个使用 LLM 桩的 E2E 测试
- i18n 键一致性预提交钩子

## v0.6.0 — "大厂怪兽"

从 12 个开源 AI 代理框架中提取最佳模式：

| 功能 | 用途 | 灵感来源 |
|------|------|----------|
| StateGraph | 构建结构化工作流 | LangGraph |
| MCP 服务器 | 将工具暴露给 MCP 客户端 | MCP Python SDK |
| Chroma 记忆 | 语义记忆搜索 | ChromaDB |
| 闭环学习 | 5 阶段学习循环 | Hermes Agent |
| Agent 移交 | 路由任务到专家子代理 | OpenAI Agents SDK |
| Agent-as-Tool | 将代理作为工具嵌入 | OpenAI Agents SDK |
| 沙箱执行 | 隔离运行不受信任的代码 | OpenAI Agents SDK |
| 输入/输出护栏 | 自动验证用户输入和代理输出 | OpenAI Agents SDK |
| 扩展钩子 | 代理事件的前后钩子 | pi-mono |
| 上下文压缩 | 智能管理 Token 窗口 | pi-mono |
| Flow 序列化 | JSON 图定义工作流 | Langflow |
| DOM 智能 | 网页解析为可交互元素 | Browser-Use |
| 浏览器代理 | 自主浏览网页 | Browser-Use |
| 语音管线 | 语音对话 | AIAvatarKit |
| VRM 虚拟形象 | 3D 动漫头像 | AIAvatarKit / VRoid Hub |

## 聊天界面

### 桌面应用（推荐）

```bash
python start.py          # 自动检测并启动最佳可用界面
```

Qt 桌面界面功能：
- 实时工具调用可视化（状态徽章）
- 可折叠推理展示
- 动画代理状态指示器（6 种状态）
- 危险操作安全确认对话框
- 命令面板（Ctrl+K）模糊搜索
- 深色、浅色、Catppuccin 主题
- 系统托盘通知
- 拖放文件支持
- **引导向导**（首次启动 5 步引导设置）
- **用户友好错误消息**（含建议操作）
- **自动更新通知**（ChatPanel 中新版本可用时显示横幅）
- **熔断器横幅**（LLM 服务商不可用时显示，含重试倒计时）

桌面应用现在默认以 **普通窗口模式** 运行——出现在任务栏，可通过 Alt+Tab 切换。恢复旧的置顶覆盖行为：

```bash
python frontends/qtapp.py --overlay
```

### 终端

```bash
python start.py --cli
```

所有界面可用的聊天命令：
- `/new` — 开始新对话
- `/continue` — 列出可恢复的会话快照
- `/continue N` — 恢复第 N 个会话

### 消息平台

> **注意**：`mykey.py` 已 **弃用**，启动时显示 `DeprecationWarning`。推荐使用 **凭证存储**（OS 密钥链）。参见配置部分。

| 平台 | 配置 |
|------|------|
| **Telegram** | 在 `mykey.py` 或密钥链中添加 `tg_bot_token`，运行 `python frontends/tgapp.py` |
| **微信** | `pip install pycryptodome qrcode`，运行 `python frontends/wechatapp.py` |
| **QQ** | 在 `mykey.py` 或密钥链中添加 `qq_app_id`/`qq_app_secret`，运行 `python frontends/qqapp.py` |
| **飞书** | 在 `mykey.py` 或密钥链中添加 `fs_app_id`/`fs_app_secret`，运行 `python frontends/fsapp.py` |
| **企业微信** | 在 `mykey.py` 或密钥链中添加 `wecom_bot_id`/`wecom_secret`，运行 `python frontends/wecomapp.py` |
| **钉钉** | 在 `mykey.py` 或密钥链中添加 `dingtalk_client_id`/`dingtalk_client_secret`，运行 `python frontends/dingtalkapp.py` |
| **Discord** | 运行 `python frontends/dcapp.py` |

## 配置

### 推荐：OS 密钥链（v1.0.0+）

存储 API Key 的 **推荐** 方式是通过 **凭证存储**，使用操作系统的安全密钥链：

- **macOS**：Keychain
- **Windows**：Credential Manager
- **Linux**：Secret Service（如 GNOME Keyring）

引导向导会自动将你的 API Key 存储到密钥链。也可以使用命令行：

```bash
# 将现有 mykey.py 凭证迁移到密钥链
python -m agentmain.credential_store --migrate
```

OS 密钥链不可用时，凭证存储回退到 `~/.genericagent/credentials.enc` 的 **加密文件**（Fernet 加密，PBKDF2 派生密钥，600K 次迭代）。

### 旧方式：mykey.py（已弃用）

`mykey.py` 仍然可用，但启动时显示 `DeprecationWarning`：

```
DeprecationWarning: mykey.py is DEPRECATED and will be removed in v1.0.
Migrate to credential_store.py (OS keyring).
Run: python -m agentmain.credential_store --migrate
```

## 安全

GenericAgent 在 **5 层** 上应用安全防护：

| 层级 | 保护措施 |
|------|----------|
| **1. 网络** | HTTPS、CORS（仅限 localhost）、速率限制（/chat 30 请求/分钟） |
| **2. 认证** | JWT/Bearer 令牌、WebSocket 令牌验证、来源检查 |
| **3. 输入验证** | 输入护栏、会话属性白名单、**路径穿越防护**（`os.path.realpath` 检查）、文件大小限制（10 MB） |
| **4. 代码执行** | SafeExpressionEvaluator（AST 白名单）、移除 `eval()`/`exec()`、**危险模式 Shell 命令确认**、API Key 存储在 OS 密钥链 |
| **5. 数据保护** | 日志匿名化（API Key 脱敏）、加密凭证回退（Fernet）、**签名自动更新**（Ed25519，失败即关闭）、Zip Slip 防护 |

## 常见问题

**Q: 需要编程才能使用吗？**
不需要。`python start.py` 一条命令搞定。只需要 Python 3.10+ 和一个 LLM API Key。GUI 引导向导会引导你完成设置。

**Q: 用哪个 LLM 服务商？**
都可以。Claude 和 GPT 最强；DeepSeek 最便宜；Ollama 免费但需要 GPU。可以配置多个，自动切换。

**Q: 数据安全吗？**
GenericAgent 完全运行在你的本地电脑上。API Key 安全存储在你的 **OS 密钥链** 中（或加密文件回退）。数据只发送到你选择的 LLM 服务商进行推理。

**Q: mykey.py 怎么了？**
`mykey.py` 在 v1.0.0 中已弃用。仍然可用但显示 `DeprecationWarning`。推荐使用 **OS 密钥链**（`credential_store.py`）。迁移命令：`python -m agentmain.credential_store --migrate`

**Q: 如何构建 Windows 安装程序？**
NSIS 安装脚本位于 `build/installer.nsi`，但需要运行 `makensis` 来构建 `.exe`——它不是预构建的可执行文件。

## 更新日志

- **v1.0.0** (2026-05-05) — 安全和用户体验加固：路径穿越保护、自动更新强制 Ed25519 签名、移除 factuality_check、默认禁用 no_code_injection/no_pii_leak、mykey.py 弃用（密钥链迁移）、GUI 引导向导、用户友好错误消息、普通窗口模式、自动更新通知、熔断器 UI 横幅、i18n 迁移（209 键）、ga.py 重构（约9600→941行，工具提取到 tools/ 包）、测试覆盖率目标 80%
- **v0.6.0** (2026-05-04) — "大厂怪兽"：18 项新功能来自 12 个框架 — StateGraph、MCP 服务器、Chroma 记忆、闭环学习、Agent 移交、护栏、扩展、Flow、浏览器代理、语音管线、VRM 虚拟形象
- **v0.5.0** (2026-05-03) — 自动结晶引擎，生产加固（52 个问题审计，所有关键问题已修复）
- **v0.4.0** (2026-05-02) — 动态工具插件、MCP 客户端、向量记忆/RAG、多代理编排、FastAPI 服务器、推理模式、Qt 界面
- **v0.3.0** (2026-04-21) — arXiv 技术报告，L4 会话归档
- **v0.1.0** (2026-01-16) — 首次公开发布

## 支持

如果这个项目帮助了你，请考虑给一个 **Star！**

<div align="center">
  <table>
    <tr>
      <td align="center"><strong>微信群 13</strong><br><img src="assets/images/wechat_group13.jpg" alt="微信群 13 二维码" width="250"/></td>
    </tr>
  </table>
</div>

## 许可证

MIT License — 见 [LICENSE](LICENSE)

*免责声明：本项目不构建或运营任何商业网站。除 DintalClaw 外，目前没有任何机构、组织或个人被正式授权以 GenericAgent 名义进行商业活动。*

---
<a name="french"></a>

## Qu'est-ce que GenericAgent ?

**GenericAgent** est un agent AI auto-evolutif qui controle votre ordinateur. Vous lui donnez une tache en langage naturel — il trouve comment la faire, l'execute, et s'en souvient pour la prochaine fois.

Contrairement aux chatbots qui ne font que parler, GenericAgent **agit** : il peut naviguer sur le web, executer du code, lire et ecrire des fichiers, et interagir avec les applications de votre bureau. Et contrairement a la plupart des frameworks d'agents qui necessitent une configuration complexe, GenericAgent est concu pour **developper ses propres capacites** au fil du temps — plus vous l'utilisez, plus il devient competent.

### Quelle difference ?

| | GenericAgent | ChatGPT / Claude | AutoGPT / CrewAI |
|---|---|---|---|
| **Agit sur votre ordi** | Oui — navigateur, terminal, fichiers | Non — texte seul | Variable |
| **Memoire entre sessions** | Oui — memoire en couches + auto-crystallisation | Non — sans etat | Partiel |
| **S'ameliore avec le temps** | Oui — crystallise les competences automatiquement | Non | Plugins manuels |
| **Complexite d'installation** | `python start.py` — une commande | Inscription web | Config complexe |
| **Efficacite Token** | <30K fenetre de contexte | Contexte complet | 200K–1M tokens |
| **Multi-LLM** | Claude, GPT, Gemini, DeepSeek, Ollama | Bloque a un | Variable |
| **Support MCP** | Client + serveur integres | Non / partiel | Non |

## Demarrage rapide

### Une commande — C'est tout

```bash
git clone https://github.com/lsdefine/GenericAgent.git
cd GenericAgent
python start.py
```

C'est toute l'installation. `start.py` fait tout :

1. **Verifie les dependances** — installe automatiquement les paquets Python manquants
2. **Lance l'assistant de configuration** — au premier lancement, un **assistant GUI d'integration** (5 etapes : Accueil → Fournisseur → Cle API → Test de connexion → Pret) vous guide
3. **Demarre la meilleure interface** — Qt si disponible, sinon Streamlit, sinon terminal

> **Prerequis** : Python 3.10+ et une connexion internet. C'est tout.
>
> **Cle API necessaire** : Au moins une cle API LLM (Anthropic, OpenAI, Google Gemini, DeepSeek, ou une instance Ollama locale). L'assistant vous guide. Les cles API sont stockees dans votre **trousseau OS** par defaut (pas dans un fichier en clair).

### Autres facons de demarrer

| Methode | Commande | Pour qui |
|---------|----------|----------|
| **Auto (recommande)** | `python start.py` | Tout le monde |
| **Reconfigurer** | `python start.py --configure` | Changer cle API ou fournisseur |
| **Mode terminal** | `python start.py --cli` | Serveurs, scripting |
| **Serveur API** | `python start.py --server` | Integration avec d'autres apps |
| **Hub de services** | `python start.py --hub` | Gerer plusieurs frontends |

## Que peut-il faire ?

GenericAgent donne a un LLM **9 outils atomiques** pour controler votre ordinateur :

| Outil | Ce qu'il fait |
|-------|---------------|
| `code_run` | Executer du code Python/Bash/PowerShell. **Protection contre le path traversal** — ne peut pas ecrire en dehors du repertoire de travail |
| `file_read` | Lire des fichiers |
| `file_write` | Ecrire ou creer des fichiers. **Protection contre le path traversal** |
| `file_patch` | Modifier des fichiers (rechercher et remplacer). **Protection contre le path traversal** |
| `web_scan` | Lire le contenu web via un vrai navigateur |
| `web_execute_js` | Executer du JavaScript dans le navigateur |
| `ask_user` | Vous poser une question en cas de doute |

Plus 2 **outils de gestion memoire** pour sauvegarder et rappeler des informations entre les sessions.

> **Note de securite** : Les commandes shell correspondant a des motifs dangereux (`rm`, `del`, `shutdown`, `sudo rm`, etc.) necessitent une **confirmation utilisateur** avant execution. En mode headless, les commandes dangereuses sont **bloquees par defaut** sauf si `--allow-dangerous-shell` est passe.

### Exemples concrets

| Ce que vous dites | Ce que GenericAgent fait |
|---|---|
| "Lis mes messages WeChat" | Installe les dependances, inverse la base de donnees, ecrit un script, sauvegarde comme competence |
| "Surveille les actions et alerte-moi quand le prix baisse de 5%" | Installe les outils boursiers, construit un flux de selection, configure des verifs planifiees, sauvegarde |
| "Envoie ce fichier par Gmail" | Configure OAuth, ecrit un script d'envoi, sauvegarde |
| "Commande-moi un bubble tea" | Ouvre l'app de livraison dans le navigateur, navigue le menu, selectionne les articles, passe la commande |

**La premiere fois**, GenericAgent explore, experimente, et trouve comment faire la tache. **Ensuite**, il rappelle la competence cristallisee et l'execute directement.

## Comment fonctionne l'auto-evolution

C'est ce qui rend GenericAgent fondamentalement different :

```
Nouvelle tache → Exploration autonome (installer deps, ecrire scripts, debugger)
              → Crystalliser le chemin d'execution en competence reutilisable
              → Ecrire dans la couche memoire
              → Rappel direct pour la prochaine tache similaire
```

L'agent utilise un **systeme memoire a 5 couches** :

| Couche | Role |
|--------|------|
| **L0** — Regles meta | Contraintes comportementales fondamentales |
| **L1** — Index d'insights | Index de routage rapide |
| **L2** — Faits globaux | Connaissances stables a long terme |
| **L3** — Competences / SOPs | Procedures reutilisables etape par etape |
| **L4** — Archives de session | Enregistrements historiques des taches |

Apres 15+ tours de conversation, le **moteur d'auto-crystallisation** se declenche automatiquement.

## v1.0.0 — Quoi de neuf

La v1.0.0 est une version de **durcissement de la securite et de l'UX**, corrigeant les problemes identifies lors d'un audit complet. Elle corrige egalement l'inversion de semver (v0.6.0 etait erroneusement superieur au v1.0 original).

### Securite

| Changement | Pourquoi |
|------------|----------|
| Guardrail `factuality_check` **SUPPRIME** | Il censurait les reponses honnetes de l'IA — les reponses contenant 3+ marqueurs d'incertitude (ex: "Je ne suis pas sur") etaient bloques, punissant l'humilite epistemique |
| Guardrails `no_code_injection` et `no_pii_leak` **DESACTIVES par defaut** | Trop de faux positifs sur les entrees legitimes (blocs de code markdown, adresses email, valeurs de config avec backticks) — peuvent etre reactivees individuellement |
| **Protection contre le path traversal** dans `code_run` et `file_ops` | Toutes les operations de fichiers valident que les chemins resolus restent dans le repertoire de travail — empeche les attaques `../../etc/passwd` |
| Mise a jour auto : **Verification de signature Ed25519 OBLIGATOIRE** | Les mises a jour sans signature valide sont rejetees (fail-closed). Sans cle publique configuree, les mises a jour sont completement bloquées |
| `mykey.py` est **DEPRÉCIÉ** avec `DeprecationWarning` | Les cles API dans des fichiers Python en clair sont un risque de securite. Migration vers le trousseau OS |
| Outils integres unifies dans le **registry** pour l'isolation des outils specialistes | Les 9 outils integres sont enregistres avec des metadonnees completes dans `tools/registry.py` |

### Internationalisation (i18n)

- Migration complete de tous les frontends vers la fonction `t()` — **209 cles i18n** a travers `en.json`, `fr.json`, `zh.json`
- Categories : messages d'erreur, labels UI, navigateur, LLM, assistant de configuration, chat, circuit breaker, specifique Qt
- Hook pre-commit pour la coherence des cles i18n

### Performance

- Correction de l'**epuisement du pool de threads** — remplace par un pont `asyncio.Queue`
- **ContextEngine auto-activé** avec compression automatique
- **Le circuit breaker emet des evenements** vers l'UI — les utilisateurs voient une banniere quand un fournisseur est indisponible

### UX Desktop

| Changement | Pourquoi |
|------------|----------|
| **Mode fenetre normal** par defaut | L'app apparait dans la barre de taches et est accessible via Alt+Tab. Utilisez `--overlay` pour l'ancien comportement toujours au premier plan |
| **Assistant d'integration** (5 etapes) au premier lancement | Configuration guidee par GUI au lieu des invites terminal |
| **Messages d'erreur conviviaux** | Les exceptions Python sont mappees en messages lisibles avec actions suggerees |
| **Couleurs centralisees** dans `theme.py` + `dark.qss` externe | Dataclass `Theme` immutable avec generation CSS dynamique |
| **Banniere de notification de mise a jour** dans ChatPanel | Les utilisateurs voient une banniere quand une nouvelle version est disponible |
| **Layout responsive HiDPI** | Plus de `setFixedSize` — l'app s'adapte correctement aux ecrans haute DPI |

### Qualite du code

- **ga.py refactore** : de ~9 600 lignes a ~941 lignes — outils extraits vers le package `tools/`
- **Couverture de tests cible** : 80% avec 10 tests E2E utilisant des stubs LLM
- Hook pre-commit pour la coherence des cles i18n

## v0.6.0 — "Big Tech Monster"

La version 0.6.0 extrait les meilleurs modeles de 12 frameworks open-source et les unifie dans GenericAgent :

| Fonctionnalite | Ce qu'elle vous apporte | Inspire par |
|----------------|------------------------|-------------|
| StateGraph | Construire des workflows structures | LangGraph |
| Serveur MCP | Exposer les outils via le protocole MCP | MCP Python SDK |
| Memoire Chroma | Recherche semantique dans la memoire | ChromaDB |
| Boucle d'apprentissage ferme | Cycle en 5 phases : Decouvrir → Executer → Reflechir → Codifier → Ameliorer | Hermes Agent |
| Divulgation progressive | Ne montrer que les competences pertinentes | Google ADK |
| Transfert d'agent | Router les taches vers des sous-agents specialises | OpenAI Agents SDK |
| Agent-comme-outil | Utiliser un agent comme outil dans un autre | OpenAI Agents SDK |
| Execution sandbox | Executer du code non fiable en isolement | OpenAI Agents SDK |
| Guardrails entree/sortie | Validation automatique | OpenAI Agents SDK |
| Hooks d'extension | Systeme de plugins avec hooks avant/apres | pi-mono |
| Compaction de contexte | Gestion intelligente de la fenetre de tokens | pi-mono |
| Serialisation Flow | Definir des workflows en JSON | Langflow |
| Intelligence DOM | Parser les pages web en elements interactifs | Browser-Use |
| Agent navigateur | Navigation web autonome | Browser-Use |
| Pipeline vocal | Conversation vocale | AIAvatarKit |
| Avatar VRM | Avatar 3D anime avec lip-sync | AIAvatarKit / VRoid Hub |

## Interfaces de chat

### Application Desktop (Recommandee)

```bash
python start.py          # Detecte et lance la meilleure interface disponible
```

L'interface Qt Desktop comprend :
- Visualisation des appels d'outils en temps reel avec badges de statut
- Affichage du raisonnement repliable
- Indicateur d'etat de l'agent anime (6 etats)
- Dialogues d'approbation de securite pour les actions dangereuses
- Palette de commandes (Ctrl+K) avec recherche floue
- Themes Sombre, Clair et Catppuccin
- Notifications dans la barre systeme
- Support drag & drop de fichiers
- **Assistant d'integration** (5 etapes au premier lancement)
- **Messages d'erreur conviviaux** avec actions suggerees
- **Notifications de mise a jour automatique** (banniere quand une nouvelle version est disponible)
- **Banniere du circuit breaker** (affichee quand le fournisseur LLM est indisponible, avec compte a rebours de nouvelle tentative)

L'app desktop fonctionne maintenant en **mode fenetre normal** par defaut — elle apparait dans la barre de taches et est accessible via Alt+Tab. Pour restaurer l'ancien comportement toujours au premier plan :

```bash
python frontends/qtapp.py --overlay
```

### Terminal

```bash
python start.py --cli
```

Commandes de chat disponibles dans toutes les interfaces :
- `/new` — Commencer une nouvelle conversation
- `/continue` — Lister les snapshots de session recuperables
- `/continue N` — Restaurer la N-ieme session

### Plateformes de messagerie

> **Note** : `mykey.py` est **deprecie** et affiche un `DeprecationWarning` au demarrage. L'approche recommandee est d'utiliser le **credential store** (trousseau OS). Voir la section Configuration.

| Plateforme | Configuration |
|------------|---------------|
| **Telegram** | Ajouter `tg_bot_token` dans `mykey.py` ou le trousseau, executer `python frontends/tgapp.py` |
| **WeChat** | `pip install pycryptodome qrcode`, executer `python frontends/wechatapp.py` |
| **QQ** | Ajouter `qq_app_id`/`qq_app_secret` dans `mykey.py` ou le trousseau, executer `python frontends/qqapp.py` |
| **Feishu/Lark** | Ajouter `fs_app_id`/`fs_app_secret` dans `mykey.py` ou le trousseau, executer `python frontends/fsapp.py` |
| **WeCom** | Ajouter `wecom_bot_id`/`wecom_secret` dans `mykey.py` ou le trousseau, executer `python frontends/wecomapp.py` |
| **DingTalk** | Ajouter `dingtalk_client_id`/`dingtalk_client_secret` dans `mykey.py` ou le trousseau, executer `python frontends/dingtalkapp.py` |
| **Discord** | Executer `python frontends/dcapp.py` |

## Configuration

### Recommande : Trousseau OS (v1.0.0+)

La facon **recommandee** de stocker les cles API est via le **credential store**, qui utilise le trousseau securise de votre systeme d'exploitation :

- **macOS** : Keychain
- **Windows** : Credential Manager
- **Linux** : Secret Service (ex: GNOME Keyring)

L'assistant d'integration stocke automatiquement votre cle API dans le trousseau. Vous pouvez aussi utiliser la CLI :

```bash
# Migrer les identifiants mykey.py existants vers le trousseau
python -m agentmain.credential_store --migrate
```

Quand le trousseau OS n'est pas disponible, le credential store revient a un **fichier chiffre** dans `~/.genericagent/credentials.enc` (chiffrement Fernet, cle derivee PBKDF2, 600K iterations).

### Ancienne methode : mykey.py (Deprecie)

`mykey.py` fonctionne toujours mais affiche un `DeprecationWarning` au demarrage :

```
DeprecationWarning: mykey.py is DEPRECATED and will be removed in v1.0.
Migrate to credential_store.py (OS keyring).
Run: python -m agentmain.credential_store --migrate
```

## Securite

GenericAgent applique la securite sur **5 couches** :

| Couche | Protections |
|--------|-------------|
| **1. Reseau** | HTTPS, CORS (localhost uniquement), limitation de debit (30 req/min sur `/chat`) |
| **2. Authentification** | Jetons JWT/Bearer, validation de jeton WebSocket, verification d'origine |
| **3. Validation des entrees** | Guardrails d'entree, liste blanche d'attributs de session, **prevention du path traversal** (verification `os.path.realpath`), limites de taille de fichier (10 MB) |
| **4. Execution de code** | SafeExpressionEvaluator (liste blanche AST), `eval()`/`exec()` supprimes, **confirmation des commandes shell** pour les motifs dangereux, cles API dans le trousseau OS |
| **5. Protection des donnees** | Anonymisation des logs (redaction des cles API), fallback de credential chiffre (Fernet), **mises a jour signees** (Ed25519, fail-closed), prevention zip slip |

## FAQ

**Q: Faut-il savoir programmer pour utiliser GenericAgent ?**
Non. La commande `python start.py` s'occupe de tout. Il suffit de Python 3.10+ et d'une cle API. L'assistant GUI d'integration vous guide.

**Q: Quel fournisseur LLM choisir ?**
Tous fonctionnent. Claude et GPT sont les plus capables ; DeepSeek est le moins cher ; Ollama est gratuit mais necessite un GPU. Vous pouvez en configurer plusieurs avec basculement automatique.

**Q: Mes donnees sont-elles en securite ?**
GenericAgent tourne entierement sur votre machine locale. Les cles API sont stockees securiseement dans votre **trousseau OS** (ou fallback chiffre). Aucune donnee n'est envoyee ailleurs que vers votre fournisseur LLM pour l'inference.

**Q: Qu'est devenu mykey.py ?**
`mykey.py` est deprecie dans la v1.0.0. Il fonctionne toujours mais affiche un `DeprecationWarning`. La methode recommandee est le **trousseau OS** via `credential_store.py`. Pour migrer : `python -m agentmain.credential_store --migrate`

**Q: Comment construire l'installateur Windows ?**
Un script d'installation NSIS existe dans `build/installer.nsi`, mais vous devez executer `makensis` pour construire le `.exe` — ce n'est pas un executable pre-construit.

## Historique des versions

- **v1.0.0** (2026-05-05) — Durcissement securite et UX : protection path traversal, signature Ed25519 obligatoire pour auto-update, factuality_check supprime, no_code_injection/no_pii_leak desactives par defaut, mykey.py deprecie (migration trousseau), assistant GUI d'integration, messages d'erreur conviviaux, mode fenetre normal, notifications de mise a jour, banniere circuit breaker, migration i18n (209 cles), ga.py refactore (~9600→941 lignes, outils extraits vers tools/), couverture de tests cible 80%
- **v0.6.0** (2026-05-04) — "Big Tech Monster" : 18 nouvelles fonctionnalites de 12 frameworks — StateGraph, MCP Serveur, Chroma Memoire, Apprentissage ferme, Transferts d'agents, Guardrails, Extensions, Flow, Agent navigateur, Pipeline vocal, Avatar VRM
- **v0.5.0** (2026-05-03) — Moteur d'auto-crystallisation, durcissement production (52 problemes audites, tous les critiques corriges)
- **v0.4.0** (2026-05-02) — Plugins d'outils dynamiques, client MCP, memoire vectorielle/RAG, orchestration multi-agents, serveur FastAPI, modes de raisonnement, interface Qt
- **v0.3.0** (2026-04-21) — Rapport technique sur arXiv, archives de session L4
- **v0.1.0** (2026-01-16) — Premiere version publique

## Support

Si ce projet vous a aide, pensez a laisser une **Star !**

<div align="center">
  <table>
    <tr>
      <td align="center"><strong>Groupe WeChat 13</strong><br><img src="assets/images/wechat_group13.jpg" alt="QR Code Groupe WeChat 13" width="250"/></td>
    </tr>
  </table>
</div>

## Licence

MIT License — voir [LICENSE](LICENSE)

*Avertissement : Ce projet ne construit ni n'exploite aucun site web commercial. A l'exception de DintalClaw, aucune institution, organisation ou individu n'est actuellement officiellement autorise a mener des activites commerciales sous le nom GenericAgent.*

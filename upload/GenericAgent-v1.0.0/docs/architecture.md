# GenericAgent v1.0.0 — Architecture

This document provides a visual overview of GenericAgent's architecture
using [Mermaid](https://mermaid.js.org/) diagrams.

---

## 1. Global Architecture

The system is divided into three layers: **Frontend**, **Core**, and
**Subsystems**.  The Core orchestrates LLM calls, tool dispatch, and
the agent loop.  Subsystems (Memory, Tools, MCP, etc.) are
lazy-initialised and communicate through the EventBus.

```mermaid
graph TB
    subgraph Frontend
        Qt["Qt Desktop App<br/>(qtapp.py)"]
        API["REST API Server<br/>(server.py)"]
        CLI["CLI / Headless<br/>(cli.py)"]
        WS["WebSocket Clients"]
    end

    subgraph Core["Core (agentmain/)"]
        Agent["GenericAgent<br/>(core.py)"]
        Loop["Agent Loop<br/>(agent_loop.py)"]
        EventBus["EventBus<br/>(event_bus.py)"]
        StateGraph["StateGraph Engine<br/>(engine/state_graph.py)"]
        Flow["Flow Engine<br/>(flow.py)"]
        Guard["Guardrails<br/>(guardrails.py)"]
        Slash["Slash Commands<br/>(slash.py)"]
        SafeEval["SafeExpressionEvaluator<br/>(safe_eval.py)"]
    end

    subgraph LLM["LLM Layer (llmcore/)"]
        Sessions["Sessions<br/>(sessions.py)"]
        Clients["Tool Clients<br/>(clients.py)"]
        Parsers["Parsers<br/>(parsers.py)"]
        Retry["Retry + Circuit Breaker<br/>(retry.py)"]
    end

    subgraph Subsystems["Subsystems"]
        Memory["Memory<br/>(ChromaDB / Crystallization)"]
        Tools["Tools<br/>(registry.py + plugins/)"]
        MCP["MCP Client/Server<br/>(mcp/)"]
        Extensions["Extensions<br/>(extensions.py)"]
        Handoffs["Handoffs<br/>(handoffs.py)"]
        Voice["Voice + Avatar<br/>(voice_avatar.py)"]
        Browser["Browser Intel<br/>(browser_intel.py)"]
        AutoUpdate["Auto-Update<br/>(auto_update.py)"]
    end

    Qt --> Agent
    API --> Agent
    CLI --> Agent
    WS --> API

    Agent --> Loop
    Agent --> EventBus
    Agent --> StateGraph
    Agent --> Flow
    Agent --> Guard
    Agent --> Slash

    Loop --> Clients
    Clients --> Sessions
    Sessions --> Parsers
    Sessions --> Retry

    Flow --> SafeEval
    StateGraph --> SafeEval

    Agent --> Memory
    Agent --> Tools
    Agent --> MCP
    Agent --> Extensions
    Agent --> Handoffs
    Agent --> Voice
    Agent --> Browser
    Agent --> AutoUpdate

    EventBus -.->|events| Memory
    EventBus -.->|events| Extensions
    EventBus -.->|events| AutoUpdate
```

---

## 2. Agent Loop Flow

The main loop processes one task at a time from the task queue, running
the LLM + tool cycle until the task is complete or aborted.

```mermaid
flowchart TD
    Start["put_task(query)"] --> Queue["Task Queue"]
    Queue --> Dequeue["Dequeue task"]
    Dequeue --> SlashCheck{"Slash<br/>command?"}
    SlashCheck -->|Yes| SlashHandle["handle_slash_cmd()"]
    SlashCheck -->|No| GuardIn{"Input<br/>guardrail?"}
    SlashHandle --> GuardIn
    GuardIn -->|Blocked| Reject["Return guardrail message"]
    GuardIn -->|Passed| BuildPrompt["Build system prompt<br/>+ tool schemas"]
    BuildPrompt --> LLMLoop["agent_runner_loop()"]

    subgraph LLMToolCycle["LLM ↔ Tool Cycle"]
        LLMLoop --> LLMCall["LLM call<br/>(stream)"]
        LLMCall --> Parse["Parse response"]
        Parse --> ToolCall{"Tool call<br/>present?"}
        ToolCall -->|Yes| ExecTool["Execute tool<br/>(with confirmation)"]
        ExecTool --> ToolResult["Append tool result"]
        ToolResult --> LLMCall
        ToolCall -->|No| Done["Final response"]
    end

    Done --> GuardOut{"Output<br/>guardrail?"}
    GuardOut -->|Warning| Append["Append warning"]
    GuardOut -->|Passed| Deliver["Deliver to display queue"]
    Append --> Deliver
    Reject --> End["Task done"]
    Deliver --> End
```

---

## 3. Tool Dispatch Flow

When the LLM produces a tool call, the handler dispatches it through the
tool registry with security checks.

```mermaid
flowchart TD
    LLM["LLM Response"] --> Parse["Parse tool_use block"]
    Parse --> Validate["Validate tool name<br/>+ arguments"]
    Validate --> Registry{"Tool in<br/>registry?"}
    Registry -->|No| Error1["Return: unknown tool"]
    Registry -->|Yes| Confirm{"Requires<br/>confirmation?"}
    Confirm -->|Yes| ShellCheck{"Shell<br/>command?"}
    ShellCheck --> Dangerous{"Dangerous<br/>pattern?"}
    Dangerous -->|Yes| UserConfirm["Ask user for<br/>confirmation"]
    Dangerous -->|No| Execute
    ShellCheck -->|No| Execute["Execute tool handler"]
    Confirm -->|No| Execute
    UserConfirm -->|Approved| Execute
    UserConfirm -->|Denied| Error2["Return: denied by user"]
    Execute --> Result["Collect result"]
    Result --> EventBus["Publish TOOL_EXECUTED"]
    EventBus --> Return["Return to agent loop"]
    Error1 --> Return
    Error2 --> Return
```

---

## 4. Security Layers

Security is applied at multiple layers, from network to code execution.

```mermaid
graph TB
    subgraph Layer1["Layer 1: Network"]
        HTTPS["Strict-Transport-Security"]
        CSP["Content-Security-Policy"]
        CORS["CORS (localhost only)"]
        RateLimit["Rate Limiting<br/>(30 req/min /chat)"]
    end

    subgraph Layer2["Layer 2: Authentication"]
        JWT["JWT / Bearer Token<br/>(~/.genericagent/auth_token)"]
        WSAUTH["WebSocket Token Validation"]
        OriginCheck["Origin Validation"]
    end

    subgraph Layer3["Layer 3: Input Validation"]
        Guardrails["Input Guardrails<br/>(guardrails.py)"]
        SlashAllowlist["Session Attr Allowlist<br/>(SESSION_WRITABLE_ATTRS)"]
        PathCheck["Path Traversal Prevention<br/>(os.path.realpath check)"]
        FileLimit["File Size Limit<br/>(10 MB)"]
    end

    subgraph Layer4["Layer 4: Code Execution"]
        SafeEval["SafeExpressionEvaluator<br/>(AST allowlist)"]
        NoEval["eval()/exec() Removed"]
        ShellConfirm["Shell Confirmation<br/>+ Dangerous Pattern Detection"]
        Keyring["API Keys in OS Keyring<br/>(not in source)"]
        PathTraversal["Path Traversal Prevention<br/>(workspace validation in code_run/file_ops)"]
    end

    subgraph Layer5["Layer 5: Data Protection"]
        LogRedact["Log Anonymization<br/>(API key redaction)"]
        EncryptedStore["Encrypted Credential Fallback<br/>(Fernet)"]
        SignedUpdates["Signed Auto-Updates<br/>(Ed25519 signature mandatory,<br/>fail-closed, not optional)"]
        ZipSlipFix["Zip Slip Prevention<br/>(path boundary check)"]
    end

    Layer1 --> Layer2 --> Layer3 --> Layer4 --> Layer5
```

---

## 5. Module Dependency Map

A simplified view of how the main modules depend on each other.  The
EventBus breaks cycles between the Core and Subsystems.

```mermaid
graph LR
    core["core.py"] --> agent_loop["agent_loop.py"]
    core --> slash["slash.py"]
    core --> guardrails["guardrails.py"]
    core --> flow["flow.py"]
    core --> event_bus["event_bus.py"]

    agent_loop --> ga["ga.py<br/>(shim, ~941 lines)"]
    ga --> tools["tools/registry.py"]
    ga --> tools_pkg["tools/<br/>(builtin tool package)"]

    tools_pkg --> code_run["tools/code_run.py"]
    tools_pkg --> file_ops["tools/file_ops.py"]
    tools_pkg --> search["tools/search.py"]

    flow --> safe_eval["safe_eval.py"]

    llmcore["llmcore/"] --> sessions["sessions.py"]
    llmcore --> clients["clients.py"]
    llmcore --> retry["retry.py"]

    core --> llmcore

    extensions["extensions.py"] --> event_bus
    handoffs["handoffs.py"] --> event_bus
    auto_update["auto_update.py"] --> event_bus

    style event_bus fill:#f9f,stroke:#333,stroke-width:2px
```

---

## 6. Memory Pipeline

Data flows from the agent's conversation through memory extraction,
vector embedding, and semantic search, with a crystallization step
that persists long-term insights.

```mermaid
flowchart TD
    Chat["Agent Conversation<br/>(history)"] --> Extract["Extract Key Info<br/>(working memory)"]
    Extract --> ShortTerm["Short-Term Memory<br/>(in-memory dict)"]
    Extract --> Crystallize["Crystallization<br/>(summarize + persist)"]

    Crystallize --> L3["L3: Crystallized Insights<br/>(JSON files)"]
    Crystallize --> L4["L4: Raw Session Logs<br/>(compressed)"]

    ShortTerm --> Embed["Embed & Index<br/>(ChromaDB / Hash)"]
    L3 --> Embed

    Embed --> VectorStore["Vector Store<br/>(ChromaDB / JSON)"]

    Query["User Query"] --> Retrieve["Semantic Search<br/>(RAG Engine)"]
    VectorStore --> Retrieve
    L3 --> Retrieve

    Retrieve --> Context["Relevant Context<br/>(injected into prompt)"]
    Context --> LLM["LLM Call"]

    SOP["SOP Documents<br/>(memory/*.md)"] --> SOPIndex["SOP Index"]
    SOPIndex --> Retrieve
```

---

## 7. Frontend-Backend Communication

The Qt frontend communicates with the agent backend through thread-safe
queues and signals.  The optional REST/WebSocket API provides remote
access.

```mermaid
sequenceDiagram
    participant User
    participant Qt as Qt Frontend<br/>(ChatPanel)
    participant SH as StreamHandler
    participant Agent as GenericAgent<br/>(core.py)
    participant Loop as Agent Loop<br/>(agent_loop.py)
    participant LLM as LLM Provider
    participant CB as Circuit Breaker
    participant EB as EventBus

    User->>Qt: Type message + Send
    Qt->>Agent: put_task(query)
    Agent-->>Qt: display_queue (Queue)

    Qt->>SH: start_stream(agent, prompt)
    Note over Qt,SH: poll_timer starts (50ms)

    Agent->>Loop: agent_runner_loop()
    Loop->>LLM: streaming API call
    LLM-->>Loop: text chunks + tool calls

    Loop-->>Agent: yield chunks
    Agent->>Agent: display_queue.put({"next": chunk})

    SH->>Agent: display_queue.get()
    Agent-->>SH: chunk dict
    SH->>Qt: _on_stream_chunk(text)
    Qt->>User: Update streaming row

    Loop-->>Agent: final response
    Agent->>Agent: display_queue.put({"done": full_text})

    SH->>Agent: display_queue.get()
    Agent-->>SH: {"done": full_text}
    SH->>Qt: _on_stream_done(final_text)
    Qt->>User: Display final message

    Note over CB,EB: Circuit Breaker state changes
    CB->>EB: state_changed event
    EB->>Qt: UI banner update (open/half-open/closed)

    Note over Qt,Agent: Also available via REST API:<br/>POST /chat → SSE stream<br/>WebSocket /ws/chat
```

---

## 8. Onboarding Wizard Flow

On first launch, if Qt is available, a GUI onboarding wizard replaces
the old terminal configuration menu.  The wizard guides new users
through essential setup and stores credentials securely in the OS
keyring.

```mermaid
flowchart TD
    Launch["First Launch<br/>(agentmain.py)"] --> QtCheck{"Qt<br/>available?"}
    QtCheck -->|No| CLI["CLI Mode<br/>(terminal input prompt)"]
    QtCheck -->|Yes| Wizard["GUI Onboarding Wizard"]

    Wizard --> Step1["Step 1: Welcome<br/>Language selection (zh/en/fr)"]
    Step1 --> Step2["Step 2: API Key Setup<br/>Enter key → stored in OS keyring"]
    Step2 --> Step3["Step 3: Model Selection<br/>Choose preferred LLM model"]
    Step3 --> Step4["Step 4: Workspace Config<br/>Set working directory"]
    Step4 --> Step5["Step 5: Ready<br/>Launch main window"]

    Step5 --> MainWindow["Qt Main Window<br/>(normal mode, not overlay)"]

    CLI --> ManualConfig["Manual credential_store.py<br/>or mykey.py (deprecated)"]
    ManualConfig --> ReadyCLI["Ready — CLI Mode"]

    style Wizard fill:#bfb,stroke:#333,stroke-width:2px
    style MainWindow fill:#bbf,stroke:#333,stroke-width:2px
```

> **Note:** On subsequent launches the wizard is skipped; the main
> window opens directly.  The `--overlay` flag can be used to switch
> from normal window mode to the developer overlay.

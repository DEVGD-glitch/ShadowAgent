# SHADOW AGENT - Plan d'Audit Complet

## Objectif
Audit technique approfondi de TOUS les fichiers du projet pour évaluer la maturité, identifier les problèmes, et préparer la publication sur GitHub.

---

## 📊 INVENTAIRE COMPLET DU PROJET

### 🔴 PYTHON BACKEND (upload/GenericAgent-v1.0.0/) - 142 fichiers Python

#### Root Level (15 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| server.py | FastAPI + SSE API Server | ⬜ TODO |
| ga.py | Main handler (LEGACY - à migrer) | ⬜ TODO |
| agent_loop.py | Agent execution loop | ⬜ TODO |
| config.py | Configuration dataclasses | ⬜ TODO |
| exceptions.py | Exception hierarchy | ⬜ TODO |
| protocols.py | Protocol definitions | ⬜ TODO |
| logging_config.py | Logging setup | ⬜ TODO |
| env_loader.py | .env file support | ⬜ TODO |
| metrics.py | LLM metrics tracking | ⬜ TODO |
| circuit_breaker.py | Rate limiting | ⬜ TODO |
| start.py | Entry point | ⬜ TODO |
| configure.py | CLI config wizard | ⬜ TODO |
| check_dependencies.py | Dependency checker | ⬜ TODO |
| launch_desktop.py | Desktop launcher | ⬜ TODO |
| conftest.py | Pytest config | ⬜ TODO |

#### agentmain/ (24 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| core.py | GenericAgent orchestrator | ⬜ TODO |
| cli.py | CLI entry point | ⬜ TODO |
| prompts.py | Tool schemas, system prompts | ⬜ TODO |
| slash.py | Slash command handler | ⬜ TODO |
| guardrails.py | Input/Output validation | ⬜ TODO |
| extensions.py | Extension lifecycle hooks | ⬜ TODO |
| event_bus.py | Event bus | ⬜ TODO |
| handoffs.py | Agent handoffs | ⬜ TODO |
| flow.py | Flow graph serialization | ⬜ TODO |
| closed_learning.py | 5-phase learning loop | ⬜ TODO |
| browser_intel.py | DOM extraction | ⬜ TODO |
| voice_avatar.py | Voice pipeline + VRM | ⬜ TODO |
| reasoning.py | Reasoning module | ⬜ TODO |
| safe_eval.py | SafeExpressionEvaluator | ⬜ TODO |
| orchestrator.py | Task orchestrator | ⬜ TODO |
| credential_store.py | OS keyring storage | ⬜ TODO |
| auto_update.py | Auto-update with Ed25519 | ⬜ TODO |
| crash_reporter.py | Crash reporting | ⬜ TODO |
| config_schema.py | Config validation | ⬜ TODO |
| health_check.py | Health checks | ⬜ TODO |
| agent_context.py | Agent context | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |
| __main__.py | Main module | ⬜ TODO |

##### agentmain/agent/ (3 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| llm_manager.py | LLM session management | ⬜ TODO |
| task_queue.py | Task queue | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

##### agentmain/voice/ (4 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| stt_providers.py | Speech-to-Text | ⬜ TODO |
| ts_providers.py | Text-to-Speech | ⬜ TODO |
| avatar_controller.py | VRM avatar control | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

#### llmcore/ (9 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| clients.py | Multi-LLM clients | ⬜ TODO |
| sessions.py | Session management | ⬜ TODO |
| parsers.py | Response parsing | ⬜ TODO |
| messages.py | Message format conversion | ⬜ TODO |
| retry.py | Exponential backoff | ⬜ TODO |
| convert.py | Tool format converters | ⬜ TODO |
| config.py | LLM config | ⬜ TODO |
| google_provider.py | Google AI Studio | ⬜ TODO |
| utils.py | Utilities | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

#### tools/ (6 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| registry.py | ToolRegistry + @register_tool | ⬜ TODO |
| code_run.py | Code execution | ⬜ TODO |
| file_ops.py | File I/O | ⬜ TODO |
| web_tools.py | Browser automation | ⬜ TODO |
| validation.py | JSON Schema validation | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

#### plugins/ (5 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| tools/web_search.py | DuckDuckGo search | ⬜ TODO |
| tools/memory_search.py | Semantic memory | ⬜ TODO |
| tools/skill_search_tool.py | Skill search | ⬜ TODO |
| tools/system_tools.py | System info | ⬜ TODO |
| langfuse_tracing.py | Langfuse tracing | ⬜ TODO |

#### mcp/ (3 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| client.py | MCP client | ⬜ TODO |
| fastmcp.py | FastMCP server | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

#### engine/ (2 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| state_graph.py | StateGraph engine | ⬜ TODO |
| __init__.py | Package init | ⬜ TODO |

#### memory/ (dossier complexe)
- vision_api.template.py
- ui_detect.py
- procmem_scanner.py
- ocr_utils.py
- ljqCtrl.py
- keychain.py
- adb_ui.py
- skill_search/skill_search/
- L4_raw_sessions/
- autonomous_operation_sop/

#### frontends/ (14 fichiers + qt/)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| qtapp.py | Qt desktop UI | ⬜ TODO |
| stapp.py | Streamlit app | ⬜ TODO |
| tgapp.py | Telegram bot | ⬜ TODO |
| dcapp.py | Discord bot | ⬜ TODO |
| wechatapp.py | WeChat bot | ⬜ TODO |
| fsapp.py | Feishu bot | ⬜ TODO |
| qqapp.py | QQ bot | ⬜ TODO |
| dingtalkapp.py | DingTalk bot | ⬜ TODO |
| wecomapp.py | WeCom bot | ⬜ TODO |
| chatapp_common.py | Common chat logic | ⬜ TODO |
| continue_cmd.py | Continue command | ⬜ TODO |

#### qt/ (12 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| pages/chat_page.py | Chat UI | ⬜ TODO |
| pages/settings_page.py | Settings UI | ⬜ TODO |
| pages/onboarding_page.py | Onboarding | ⬜ TODO |
| pages/history_page.py | History UI | ⬜ TODO |
| pages/sop_page.py | SOP UI | ⬜ TODO |
| widgets.py | Custom widgets | ⬜ TODO |
| theme.py | Theme management | ⬜ TODO |
| stream_handler.py | Output streaming | ⬜ TODO |
| session_manager.py | Session handling | ⬜ TODO |
| tray_icon.py | System tray | ⬜ TODO |
| command_palette.py | Ctrl+K palette | ⬜ TODO |
| error_mapper.py | Error mapping | ⬜ TODO |

#### tests/ (21 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| test_ga.py | Main tests | ⬜ TODO |
| test_server.py | Server tests | ⬜ TODO |
| test_llmcore.py | LLM tests | ⬜ TODO |
| test_e2e.py | E2E tests | ⬜ TODO |
| test_security*.py | Security tests | ⬜ TODO |
| ... (autres) | | ⬜ TODO |

#### assets/ & i18n/
| Dossier | Description | Status Audit |
|---------|------------|--------------|
| assets/ | Themes, prompts, images | ⬜ TODO |
| i18n/ | Translations (en/fr/zh) | ⬜ TODO |

---

### 🟢 FRONTEND NEXT.JS (src/) - 76 fichiers)

#### Core Files (5 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| app/page.tsx | Main page | ⬜ TODO |
| app/layout.tsx | Root layout | ⬜ TODO |
| app/globals.css | Global styles | ⬜ TODO |

#### Components/Chat (6 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| chat/chat-page.tsx | Chat interface | ⬜ TODO |
| chat/chat-input.tsx | Input component | ⬜ TODO |
| chat/message-item.tsx | Message display | ⬜ TODO |
| chat/message-list.tsx | Message list | ⬜ TODO |
| chat/thinking-section.tsx | Thinking display | ⬜ TODO |
| chat/tool-call-badge.tsx | Tool badges | ⬜ TODO |

#### Components/Settings (3 fichiers)
#### Components/Dashboard (4 fichiers)
#### Components/Memory (1 fichier)
#### Components/History (1 fichier)
#### Components/Avatar (1 fichier)
#### Components/Pet (1 fichier)
#### Components/Onboarding (1 fichier)
#### Components/Tauri (3 fichiers)
#### Components/UI (42 fichiers - shadcn/ui)

#### Lib/Stores (4 fichiers)
| Fichier | Description | Status Audit |
|---------|------------|--------------|
| lib/backend.ts | Backend connection | ⬜ TODO |
| lib/tauri.ts | Tauri integration | ⬜ TODO |
| lib/api.ts | API client | ⬜ TODO |
| lib/db.ts | Database | ⬜ TODO |

#### Stores (3 fichiers)
#### Hooks (2 fichiers)
#### Tests (7 fichiers)

---

### 🔵 TAURI/RUST (src-tauri/)

| Fichier | Description | Status Audit |
|---------|------------|--------------|
| src/main.rs | Rust main entry | ⬜ TODO |
| Cargo.toml | Rust dependencies | ⬜ TODO |
| tauri.conf.json | Tauri config | ⬜ TODO |
| build.rs | Build script | ⬜ TODO |
| capabilities/default.json | Permissions | ⬜ TODO |
| binaries/sidecar_entry.py | PyInstaller entry | ⬜ TODO |
| binaries/launch_backend.py | Backend launcher | ⬜ TODO |

---

## 🎯 CRITÈRES D'AUDIT

Pour chaque fichier, vérifier:

### 1. **Qualité du Code**
- [ ] Typage correct (Python type hints, TypeScript types)
- [ ] Documentation/docstrings présentes
- [ ] Pas de code dupliqué
- [ ] Fonctions simples et courtes

### 2. **Sécurité**
- [ ] Pas de secrets hardcodés
- [ ] Validation des entrées
- [ ] Protection path traversal
- [ ] Rate limiting
- [ ] sanitization des entrées

### 3. **Erreurs et Exceptions**
- [ ] Gestion d'erreurs appropriée
- [ ] Pas de try/except pass
- [ ] Messages d'erreur clairs

### 4. **Performance**
- [ ] Pas de loops infinies
- [ ] Gestion des timeouts
- [ ] Resources bien libérées

### 5. **Modernité**
- [ ] Code moderne (Python 3.10+)
- [ ] Pas de deprecated APIs
- [ ] Bonnes pratiques

---

## 📋 RAPPORT D'AUDIT

### Problèmes Critiques Retirables avant publication:
```
[X] fichier mykey_template.py - EXCLURE (contient exemples de clés)
[X] fichiers __pycache__ - EXCLURE
[X] fichiers .pyc - EXCLURE
[ ] ga.py - LEGACY, migrer vers agentmain/
```

### Problèmes à Corriger:
```
1. [ ] server.py - Vérifier gestion errors
2. [ ] tools/code_run.py - Vérifier sécurité
3. [ ] frontends/qtapp.py - Moderniser si nécessaire
```

### Points Forts Identifiés:
```
[+] Architecture modulaire (agentmain/, llmcore/, tools/)
[+] Système d'extensions bien conçu
[+] Tests de sécurité présents
[+] Documentation internationale (i18n)
```

---

## 🚀 ORDRE D'AUDIT RECOMMANDÉ

1. **Phase 1**: Core Backend (server.py, agentmain/core.py, ga.py)
2. **Phase 2**: LLM Layer (llmcore/)
3. **Phase 3**: Tools System (tools/)
4. **Phase 4**: Memory System (memory/)
5. **Phase 5**: Frontends (frontends/, Qt)
6. **Phase 6**: Frontend Next.js (src/)
7. **Phase 7**: Tauri/Rust (src-tauri/)
8. **Phase 8**: Build System et Configs

---

*Document créé pour l'audit Shadow Agent*
*Date: Mai 2026*

"""
agentmain — Core agent runtime for GenericAgent.

This package defines :class:`GenericAgent`, the primary orchestrator that manages
LLM sessions, task queues, and the agent execution loop.  It supports three
operational modes when run as ``python -m agentmain``:

* **Interactive** — REPL-style chat with incremental output.
* **Task mode** (``--task IODIR``) — file-based I/O for headless / batch runs.
* **Reflect mode** (``--reflect SCRIPT``) — watchdog-style automation triggered
  by an external monitoring script.

Backward compatibility: the legacy name ``GeneraticAgent`` is retained as an
alias so that existing ``from agentmain import GeneraticAgent`` imports continue
to work unchanged.
"""

from __future__ import annotations

__version__ = "1.0.0"

# Re-export all public symbols so that the package is a drop-in replacement
# for the old monolithic agentmain.py module.
from agentmain.core import GenericAgent
from agentmain.prompts import TOOLS_SCHEMA, get_system_prompt
from agentmain.cli import main_cli

# v1.0.0 symbols — lazy imports to avoid hard deps
from agentmain.closed_learning import ClosedLearningLoop, SkillDocument, SkillToolset, SelfNudge
from agentmain.handoffs import Handoff, AgentHandoff, AgentAsTool, SandboxConfig
from agentmain.guardrails import InputGuardrail, OutputGuardrail, GuardrailManager
from agentmain.flow import Flow, FlowExecutor, FlowMCPServer
from agentmain.browser_intel import DOMExtractor, BrowserSession, BrowserAgent
from agentmain.voice_avatar import (
    VoicePipeline, VADProcessor, LLMVoiceClient,
    STTProvider, TTSProvider, LLMVoiceProvider,
)
from agentmain.voice.avatar_controller import AvatarController
from agentmain.voice.tts_providers import EDGE_VOICES

# NOTE: VRoidHubClient, SpeechToSpeechEngine, S2SResponse are not yet
# implemented in the voice modules. They will be added in a future release.
# For now, they are omitted from the public API to avoid ImportError.
from agentmain.extensions import ExtensionManager, Extension, ExtensionHook, ContextEngine

__all__ = [
    "GenericAgent",
    # GeneraticAgent removed — use GenericAgent instead (see DeprecationWarning in core.py)
    "TOOLS_SCHEMA",
    "get_system_prompt",
    "main_cli",
    # v0.6.0 closed learning
    "ClosedLearningLoop",
    "SkillDocument",
    "SkillToolset",
    "SelfNudge",
    # v0.6.0 handoffs
    "Handoff",
    "AgentHandoff",
    "AgentAsTool",
    "SandboxConfig",
    # v0.6.0 guardrails
    "InputGuardrail",
    "OutputGuardrail",
    "GuardrailManager",
    # v0.6.0 flow
    "Flow",
    "FlowExecutor",
    "FlowMCPServer",
    # v0.6.0 browser intel
    "DOMExtractor",
    "BrowserSession",
    "BrowserAgent",
    # v0.6.0 voice & avatar
    "VoicePipeline",
    "VADProcessor",
    "AvatarController",
    # "VRoidHubClient",       # Not yet implemented
    # "SpeechToSpeechEngine", # Not yet implemented
    "LLMVoiceClient",
    # "S2SResponse",          # Not yet implemented
    "STTProvider",
    "TTSProvider",
    "LLMVoiceProvider",
    "EDGE_VOICES",
    # v0.6.0 extensions
    "ExtensionManager",
    "Extension",
    "ExtensionHook",
    "ContextEngine",
]

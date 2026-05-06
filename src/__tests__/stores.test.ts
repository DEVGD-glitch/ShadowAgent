import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useSettingsStore, LLM_PROVIDERS, STT_PROVIDERS, TTS_PROVIDERS, PERSONALITIES, PET_SKINS } from '@/stores/settings-store';
import { useAgentStore } from '@/stores/agent-store';
import { useOnboardingStore } from '@/stores/onboarding-store';

describe('settings-store', () => {
  beforeEach(() => {
    // Reset stores
    useSettingsStore.setState({
      theme: 'dark',
      language: 'en',
      autonomousMode: false,
      autoUpdate: true,
      showOnboarding: true,
      voice: {
        sttProvider: 'browser',
        ttsProvider: 'edge',
        language: 'en',
        voiceStyle: 'female',
        avatarEnabled: true,
        avatarModel: 'default',
        avatarExpressionMode: 'automatic',
      },
      avatar: { enabled: true, modelPath: '/models/avatar.vrm', expressionMode: 'automatic', showLipSync: true },
      desktopPet: { enabled: true, skin: 'vita', position: { x: 100, y: 100 }, interactionEnabled: true },
      personality: 'assistant',
      mcpServers: [],
      health: { uptime: 0, llmCalls: 0, tokenUsage: 0, errorCount: 0, platform: 'Unknown', pythonVersion: 'Unknown', lastCheck: Date.now() },
      sidebarCollapsed: false,
      commandPaletteOpen: false,
      backendConfig: { host: 'localhost', port: 8765, autoConnect: true },
      apiKeys: {},
    });
  });

  describe('initial state', () => {
    it('has correct defaults', () => {
      const state = useSettingsStore.getState();
      expect(state.theme).toBe('dark');
      expect(state.language).toBe('en');
      expect(state.autonomousMode).toBe(false);
      expect(state.autoUpdate).toBe(true);
      expect(state.backendConfig.host).toBe('localhost');
      expect(state.backendConfig.port).toBe(8765);
      expect(state.apiKeys).toEqual({});
    });
  });

  describe('setTheme', () => {
    it('changes theme', () => {
      useSettingsStore.getState().setTheme('light');
      expect(useSettingsStore.getState().theme).toBe('light');
    });

    it('supports all theme modes', () => {
      const themes = ['dark', 'light', 'catppuccin', 'glass'] as const;
      for (const theme of themes) {
        useSettingsStore.getState().setTheme(theme);
        expect(useSettingsStore.getState().theme).toBe(theme);
      }
    });
  });

  describe('setLanguage', () => {
    it('changes language', () => {
      useSettingsStore.getState().setLanguage('fr');
      expect(useSettingsStore.getState().language).toBe('fr');
    });
  });

  describe('setAutonomousMode', () => {
    it('toggles autonomous mode', () => {
      useSettingsStore.getState().setAutonomousMode(true);
      expect(useSettingsStore.getState().autonomousMode).toBe(true);
    });
  });

  describe('setVoice', () => {
    it('updates voice config partially', () => {
      useSettingsStore.getState().setVoice({ sttProvider: 'groq' });
      const voice = useSettingsStore.getState().voice;
      expect(voice.sttProvider).toBe('groq');
      expect(voice.ttsProvider).toBe('edge'); // unchanged
    });
  });

  describe('setAvatar', () => {
    it('updates avatar config partially', () => {
      useSettingsStore.getState().setAvatar({ enabled: false });
      const avatar = useSettingsStore.getState().avatar;
      expect(avatar.enabled).toBe(false);
      expect(avatar.modelPath).toBe('/models/avatar.vrm'); // unchanged
    });
  });

  describe('setDesktopPet', () => {
    it('updates desktop pet config', () => {
      useSettingsStore.getState().setDesktopPet({ skin: 'tard' });
      expect(useSettingsStore.getState().desktopPet.skin).toBe('tard');
    });
  });

  describe('setPersonality', () => {
    it('sets personality', () => {
      useSettingsStore.getState().setPersonality('tsundere');
      expect(useSettingsStore.getState().personality).toBe('tsundere');
    });
  });

  describe('setMcpServers', () => {
    it('sets MCP servers', () => {
      const servers = [{ name: 'Test', url: 'http://localhost:3001', status: 'connected' as const, toolsCount: 5 }];
      useSettingsStore.getState().setMcpServers(servers);
      expect(useSettingsStore.getState().mcpServers).toHaveLength(1);
    });
  });

  describe('updateHealth', () => {
    it('updates health info partially', () => {
      useSettingsStore.getState().updateHealth({ uptime: 3600, llmCalls: 42 });
      const health = useSettingsStore.getState().health;
      expect(health.uptime).toBe(3600);
      expect(health.llmCalls).toBe(42);
      expect(health.platform).toBe('Unknown'); // unchanged
    });
  });

  describe('setBackendConfig', () => {
    it('updates backend config partially', () => {
      useSettingsStore.getState().setBackendConfig({ port: 9999 });
      const config = useSettingsStore.getState().backendConfig;
      expect(config.port).toBe(9999);
      expect(config.host).toBe('localhost'); // unchanged
    });
  });

  describe('setApiKey / removeApiKey', () => {
    it('sets an API key', () => {
      useSettingsStore.getState().setApiKey('openai', 'sk-test');
      expect(useSettingsStore.getState().apiKeys.openai).toBe('sk-test');
    });

    it('removes an API key', () => {
      useSettingsStore.getState().setApiKey('openai', 'sk-test');
      useSettingsStore.getState().setApiKey('anthropic', 'sk-ant-test');
      useSettingsStore.getState().removeApiKey('openai');
      expect(useSettingsStore.getState().apiKeys.openai).toBeUndefined();
      expect(useSettingsStore.getState().apiKeys.anthropic).toBe('sk-ant-test');
    });

    it('handles removing non-existent key gracefully', () => {
      expect(() => useSettingsStore.getState().removeApiKey('nonexistent')).not.toThrow();
    });
  });

  describe('toggleSidebar', () => {
    it('toggles sidebar state', () => {
      expect(useSettingsStore.getState().sidebarCollapsed).toBe(false);
      useSettingsStore.getState().toggleSidebar();
      expect(useSettingsStore.getState().sidebarCollapsed).toBe(true);
      useSettingsStore.getState().toggleSidebar();
      expect(useSettingsStore.getState().sidebarCollapsed).toBe(false);
    });
  });

  describe('setCommandPaletteOpen', () => {
    it('sets palette state', () => {
      useSettingsStore.getState().setCommandPaletteOpen(true);
      expect(useSettingsStore.getState().commandPaletteOpen).toBe(true);
    });
  });

  describe('constant data', () => {
    it('LLM_PROVIDERS has expected entries', () => {
      expect(LLM_PROVIDERS.length).toBeGreaterThanOrEqual(8);
      expect(LLM_PROVIDERS.some(p => p.id === 'openai')).toBe(true);
      expect(LLM_PROVIDERS.some(p => p.id === 'anthropic')).toBe(true);
      expect(LLM_PROVIDERS.some(p => p.id === 'ollama')).toBe(true);
    });

    it('STT_PROVIDERS has entries', () => {
      expect(STT_PROVIDERS.length).toBeGreaterThan(0);
    });

    it('TTS_PROVIDERS has entries', () => {
      expect(TTS_PROVIDERS.length).toBeGreaterThan(0);
    });

    it('PERSONALITIES has entries', () => {
      expect(PERSONALITIES.length).toBeGreaterThan(0);
    });

    it('PET_SKINS has entries', () => {
      expect(PET_SKINS.length).toBeGreaterThan(0);
    });
  });
});

// ============ AGENT STORE ============
describe('agent-store', () => {
  beforeEach(() => {
    useAgentStore.setState({
      sessions: [],
      currentSessionId: null,
      messages: [],
      currentModel: null,
      models: [],
      isStreaming: false,
      status: 'idle',
      metrics: {
        totalMessages: 0,
        tokensUsed: 0,
        llmCalls: 0,
        uptime: 0,
        errorRate: 0,
        memoryUsage: 0,
        skillsCrystallized: 0,
      },
      backendConnected: 'disconnected',
      isAuthenticated: false,
    });
  });

  describe('initial state', () => {
    it('has correct defaults', () => {
      const state = useAgentStore.getState();
      expect(state.sessions).toEqual([]);
      expect(state.messages).toEqual([]);
      expect(state.isStreaming).toBe(false);
      expect(state.status).toBe('idle');
      expect(state.backendConnected).toBe('disconnected');
    });
  });

  describe('sessions', () => {
    it('adds a new session', () => {
      const session = { id: 's1', title: 'Test Session', messageCount: 0, date: Date.now(), messages: [] };
      useAgentStore.getState().addSession(session);
      expect(useAgentStore.getState().sessions.length).toBe(1);
      expect(useAgentStore.getState().sessions[0].title).toBe('Test Session');
    });

    it('sets current session', () => {
      const session = { id: 's1', title: 'Test', messageCount: 0, date: Date.now(), messages: [] };
      useAgentStore.getState().addSession(session);
      useAgentStore.getState().setCurrentSession('s1');
      expect(useAgentStore.getState().currentSessionId).toBe('s1');
    });

    it('removes a session', () => {
      const session = { id: 's1', title: 'Test', messageCount: 0, date: Date.now(), messages: [] };
      useAgentStore.getState().addSession(session);
      useAgentStore.getState().removeSession('s1');
      expect(useAgentStore.getState().sessions.length).toBe(0);
    });
  });

  describe('messages', () => {
    it('adds a user message', () => {
      useAgentStore.getState().addMessage({ id: 'm1', role: 'user', content: 'Hello!', timestamp: Date.now() });
      expect(useAgentStore.getState().messages.length).toBe(1);
      expect(useAgentStore.getState().messages[0].role).toBe('user');
      expect(useAgentStore.getState().messages[0].content).toBe('Hello!');
    });

    it('adds an assistant message', () => {
      useAgentStore.getState().addMessage({ id: 'm1', role: 'assistant', content: 'Hi there!', timestamp: Date.now() });
      expect(useAgentStore.getState().messages[0].role).toBe('assistant');
    });

    it('clears messages', () => {
      useAgentStore.getState().addMessage({ id: 'm1', role: 'user', content: 'Hello!', timestamp: Date.now() });
      useAgentStore.getState().clearMessages();
      expect(useAgentStore.getState().messages).toEqual([]);
    });
  });

  describe('streaming state', () => {
    it('sets streaming state', () => {
      useAgentStore.getState().setStreaming(true);
      expect(useAgentStore.getState().isStreaming).toBe(true);
    });

    it('sets status', () => {
      useAgentStore.getState().setStatus('thinking');
      expect(useAgentStore.getState().status).toBe('thinking');
    });
  });

  describe('models', () => {
    it('sets models', () => {
      const mockModels = [
        { id: 'm1', name: 'GPT-4o', provider: 'OpenAI', isActive: true, health: 'healthy' as const, index: 0 },
      ];
      useAgentStore.getState().setModels(mockModels);
      expect(useAgentStore.getState().models).toHaveLength(1);
    });

    it('sets current model', () => {
      const model = { id: 'm1', name: 'GPT-4o', provider: 'OpenAI', isActive: true, health: 'healthy' as const, index: 0 };
      useAgentStore.getState().setCurrentModel(model);
      expect(useAgentStore.getState().currentModel?.name).toBe('GPT-4o');
    });
  });

  describe('backend connection', () => {
    it('sets backend connected', () => {
      useAgentStore.getState().setBackendConnected('connected');
      expect(useAgentStore.getState().backendConnected).toBe('connected');
    });

    it('sets authenticated', () => {
      useAgentStore.getState().setAuthenticated(true);
      expect(useAgentStore.getState().isAuthenticated).toBe(true);
    });
  });

  describe('metrics', () => {
    it('updates metrics', () => {
      useAgentStore.getState().updateMetrics({ tokensUsed: 500, llmCalls: 3 });
      expect(useAgentStore.getState().metrics.tokensUsed).toBe(500);
      expect(useAgentStore.getState().metrics.llmCalls).toBe(3);
    });
  });
});

// ============ ONBOARDING STORE ============
describe('onboarding-store', () => {
  beforeEach(() => {
    useOnboardingStore.setState({
      step: 0,
      selectedProvider: null,
      apiKey: '',
      showApiKey: false,
      connectionStatus: 'idle',
      connectionError: null,
    });
  });

  describe('step navigation', () => {
    it('starts at step 0', () => {
      expect(useOnboardingStore.getState().step).toBe(0);
    });

    it('advances to next step', () => {
      useOnboardingStore.getState().nextStep();
      expect(useOnboardingStore.getState().step).toBe(1);
    });

    it('goes to previous step', () => {
      useOnboardingStore.getState().nextStep();
      useOnboardingStore.getState().prevStep();
      expect(useOnboardingStore.getState().step).toBe(0);
    });

    it('does not go below 0', () => {
      useOnboardingStore.getState().prevStep();
      expect(useOnboardingStore.getState().step).toBe(0);
    });

    it('sets step directly', () => {
      useOnboardingStore.getState().setStep(3);
      expect(useOnboardingStore.getState().step).toBe(3);
    });
  });

  describe('provider selection', () => {
    it('selects a provider', () => {
      useOnboardingStore.getState().setSelectedProvider('openai');
      expect(useOnboardingStore.getState().selectedProvider).toBe('openai');
    });
  });

  describe('API key', () => {
    it('sets API key', () => {
      useOnboardingStore.getState().setApiKey('sk-test-key');
      expect(useOnboardingStore.getState().apiKey).toBe('sk-test-key');
    });

    it('toggles show API key', () => {
      useOnboardingStore.getState().toggleShowApiKey();
      expect(useOnboardingStore.getState().showApiKey).toBe(true);
    });
  });

  describe('connection status', () => {
    it('sets connection status', () => {
      useOnboardingStore.getState().setConnectionStatus('testing');
      expect(useOnboardingStore.getState().connectionStatus).toBe('testing');
    });

    it('sets connection error', () => {
      useOnboardingStore.getState().setConnectionError('Network error');
      expect(useOnboardingStore.getState().connectionError).toBe('Network error');
    });
  });

  describe('completeOnboarding', () => {
    it('marks onboarding as complete', () => {
      useOnboardingStore.getState().completeOnboarding();
      expect(useOnboardingStore.getState().isComplete).toBe(true);
    });
  });

  describe('reset', () => {
    it('resets all state', () => {
      useOnboardingStore.getState().setStep(5);
      useOnboardingStore.getState().setSelectedProvider('openai');
      useOnboardingStore.getState().reset();
      expect(useOnboardingStore.getState().step).toBe(0);
      expect(useOnboardingStore.getState().selectedProvider).toBeNull();
      expect(useOnboardingStore.getState().isComplete).toBe(false);
    });
  });
});

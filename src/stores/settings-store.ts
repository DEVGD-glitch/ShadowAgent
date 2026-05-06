import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemeMode = 'dark' | 'light' | 'catppuccin' | 'glass';

export interface MCPConfig {
  name: string;
  url: string;
  status: 'connected' | 'disconnected' | 'error';
  toolsCount: number;
}

// ============ LLM PROVIDERS ============
export const LLM_PROVIDERS = [
  { id: 'openai', name: 'OpenAI', description: 'GPT-4o, GPT-4o Mini, o1, o3', icon: '🤖', apiKeyUrl: 'https://platform.openai.com/api-keys', requiresKey: true },
  { id: 'anthropic', name: 'Anthropic', description: 'Claude 4 Sonnet, Claude 3.5', icon: '🧠', apiKeyUrl: 'https://console.anthropic.com/', requiresKey: true },
  { id: 'google', name: 'Google', description: 'Gemini 2.5 Pro, Gemma', icon: '✨', apiKeyUrl: 'https://aistudio.google.com/apikey', requiresKey: true },
  { id: 'ollama', name: 'Ollama', description: 'Local LLMs: Llama, Mistral, Phi, Qwen', icon: '🦙', apiKeyUrl: '', requiresKey: false },
  { id: 'groq', name: 'Groq', description: 'Fast Llama & Mixtral inference', icon: '⚡', apiKeyUrl: 'https://console.groq.com/keys', requiresKey: true },
  { id: 'pollinations', name: 'Pollinations', description: 'Free AI — no API key needed!', icon: '🌸', apiKeyUrl: 'https://pollinations.ai', requiresKey: false },
  { id: 'deepinfra', name: 'DeepInfra', description: 'Serverless LLM inference', icon: '🔥', apiKeyUrl: 'https://deepinfra.com/dash/api_keys', requiresKey: true },
  { id: 'openrouter', name: 'OpenRouter', description: 'Unified API for 200+ models', icon: '🌐', apiKeyUrl: 'https://openrouter.ai/keys', requiresKey: true },
  { id: 'together', name: 'Together AI', description: 'Open-source model hosting', icon: '🤝', apiKeyUrl: 'https://api.together.xyz/settings/api-keys', requiresKey: true },
  { id: 'mistral', name: 'Mistral', description: 'Mistral & Codestral models', icon: '🌀', apiKeyUrl: 'https://console.mistral.ai/api-keys/', requiresKey: true },
] as const;

// ============ STT PROVIDERS ============
export const STT_PROVIDERS = [
  { id: 'browser', name: 'Browser Speech', description: 'Free, built-in Web Speech API (no key needed)' },
  { id: 'groq', name: 'Groq Whisper', description: 'Fast whisper via Groq API' },
  { id: 'pollinations', name: 'Pollinations', description: 'Free STT via Pollinations' },
  { id: 'google', name: 'Google Speech', description: 'Google Cloud Speech-to-Text' },
  { id: 'openai', name: 'OpenAI Whisper', description: 'OpenAI Whisper API' },
  { id: 'azure', name: 'Azure Speech', description: 'Azure Cognitive Services' },
  { id: 'local-whisper', name: 'Local Whisper', description: 'Local Whisper model (no API key needed)' },
] as const;

// ============ TTS PROVIDERS ============
export const TTS_PROVIDERS = [
  { id: 'edge', name: 'Edge TTS', description: 'Microsoft Edge TTS (free)' },
  { id: 'voicevox', name: 'VOICEVOX', description: 'Japanese TTS engine' },
  { id: 'pollinations', name: 'Pollinations', description: 'Free TTS via Pollinations' },
  { id: 'google', name: 'Google TTS', description: 'Google Cloud Text-to-Speech' },
  { id: 'openai', name: 'OpenAI TTS', description: 'OpenAI TTS API' },
  { id: 'azure', name: 'Azure TTS', description: 'Azure Cognitive Services TTS' },
  { id: 'elevenlabs', name: 'ElevenLabs', description: 'High-quality voice AI' },
] as const;

// ============ PERSONALITIES ============
export const PERSONALITIES = [
  { id: 'assistant', name: 'Assistant', description: 'Professional and helpful', emoji: '💼', color: 'from-blue-500/20 to-indigo-500/20', border: 'border-blue-500/20' },
  { id: 'developer', name: 'Developer', description: 'Technical expert for coding tasks', emoji: '👨‍💻', color: 'from-green-500/20 to-emerald-500/20', border: 'border-green-500/20' },
  { id: 'researcher', name: 'Researcher', description: 'Analytical and thorough', emoji: '🔬', color: 'from-purple-500/20 to-violet-500/20', border: 'border-purple-500/20' },
  { id: 'creative', name: 'Creative', description: 'Creative and brainstorming partner', emoji: '🎨', color: 'from-pink-500/20 to-rose-500/20', border: 'border-pink-500/20' },
  { id: 'analyst', name: 'Analyst', description: 'Data-driven and precise', emoji: '📊', color: 'from-orange-500/20 to-amber-500/20', border: 'border-orange-500/20' },
  { id: 'teacher', name: 'Teacher', description: 'Patient and explanatory', emoji: '📚', color: 'from-cyan-500/20 to-teal-500/20', border: 'border-cyan-500/20' },
  { id: 'expert', name: 'Expert', description: 'Senior advisor for complex tasks', emoji: '🎓', color: 'from-red-500/20 to-orange-500/20', border: 'border-red-500/20' },
] as const;

// ============ DESKTOP PET SKINS ============
export const PET_SKINS = [
  { id: 'orb', name: 'Orb', emoji: '🔮', description: 'Mysterious energy orb' },
  { id: 'bot', name: 'Bot', emoji: '🤖', description: 'Helpful robot companion' },
  { id: 'spark', name: 'Spark', emoji: '✨', description: 'Magical sparkle' },
  { id: 'ghost', name: 'Ghost', emoji: '👻', description: 'Friendly ghost' },
  { id: 'star', name: 'Star', emoji: '⭐', description: 'Shining star' },
  { id: 'moon', name: 'Moon', emoji: '🌙', description: 'Wise moon spirit' },
  { id: 'cube', name: 'Cube', emoji: '🧊', description: 'Geometric companion' },
] as const;

// ============ VOICE STYLES ============
export const VOICE_STYLES = [
  { id: 'female', name: 'Female', description: 'Feminine voice' },
  { id: 'male', name: 'Male', description: 'Masculine voice' },
  { id: 'anime', name: 'Anime', description: 'Animated anime voice' },
] as const;

export interface VoiceConfig {
  sttProvider: string;
  ttsProvider: string;
  language: string;
  voiceStyle: string;
  avatarEnabled: boolean;
  avatarModel: string;
  avatarExpressionMode: 'automatic' | 'manual';
}

export interface AvatarConfig {
  enabled: boolean;
  modelPath: string;
  expressionMode: 'automatic' | 'manual';
  showLipSync: boolean;
}

export interface DesktopPetConfig {
  enabled: boolean;
  skin: string;
  position: { x: number; y: number };
  interactionEnabled: boolean;
}

export interface BackendConfig {
  host: string;
  port: number;
  autoConnect: boolean;
}

export interface HealthInfo {
  uptime: number;
  llmCalls: number;
  tokenUsage: number;
  errorCount: number;
  platform: string;
  pythonVersion: string;
  lastCheck: number;
}

interface SettingsState {
  theme: ThemeMode;
  language: string;
  autonomousMode: boolean;
  autoUpdate: boolean;
  showOnboarding: boolean;
  voice: VoiceConfig;
  avatar: AvatarConfig;
  desktopPet: DesktopPetConfig;
  personality: string;
  mcpServers: MCPConfig[];
  health: HealthInfo;
  sidebarCollapsed: boolean;
  commandPaletteOpen: boolean;
  backendConfig: BackendConfig;
  apiKeys: Record<string, string>;

  // Actions
  setTheme: (theme: ThemeMode) => void;
  setLanguage: (language: string) => void;
  setAutonomousMode: (enabled: boolean) => void;
  setAutoUpdate: (enabled: boolean) => void;
  setShowOnboarding: (show: boolean) => void;
  setVoice: (voice: Partial<VoiceConfig>) => void;
  setAvatar: (avatar: Partial<AvatarConfig>) => void;
  setDesktopPet: (pet: Partial<DesktopPetConfig>) => void;
  setPersonality: (personality: string) => void;
  setMcpServers: (servers: MCPConfig[]) => void;
  updateHealth: (health: Partial<HealthInfo>) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setBackendConfig: (config: Partial<BackendConfig>) => void;
  setApiKey: (provider: string, key: string) => void;
  removeApiKey: (provider: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
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
      avatar: {
        enabled: true,
        modelPath: '/models/avatar.vrm',
        expressionMode: 'automatic',
        showLipSync: true,
      },
      desktopPet: {
        enabled: true,
        skin: 'vita',
        position: { x: 100, y: 100 },
        interactionEnabled: true,
      },
      personality: 'assistant' as string,
      mcpServers: [] as MCPConfig[],
      health: {
        uptime: 0,
        llmCalls: 0,
        tokenUsage: 0,
        errorCount: 0,
        platform: 'Unknown',
        pythonVersion: 'Unknown',
        lastCheck: Date.now(),
      },
      sidebarCollapsed: false,
      commandPaletteOpen: false,
      backendConfig: {
        host: 'localhost',
        port: 8765,
        autoConnect: true,
      },
      apiKeys: {},

      setTheme: (theme) => set({ theme }),
      setLanguage: (language) => set({ language }),
      setAutonomousMode: (enabled) => set({ autonomousMode: enabled }),
      setAutoUpdate: (enabled) => set({ autoUpdate: enabled }),
      setShowOnboarding: (show) => set({ showOnboarding: show }),
      setVoice: (voice) =>
        set((state) => ({
          voice: { ...state.voice, ...voice },
        })),
      setAvatar: (avatar) =>
        set((state) => ({
          avatar: { ...state.avatar, ...avatar },
        })),
      setDesktopPet: (pet) =>
        set((state) => ({
          desktopPet: { ...state.desktopPet, ...pet },
        })),
      setPersonality: (personality) => set({ personality }),
      setMcpServers: (servers) => set({ mcpServers: servers }),
      updateHealth: (health) =>
        set((state) => ({
          health: { ...state.health, ...health },
        })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
      setBackendConfig: (config) =>
        set((state) => ({
          backendConfig: { ...state.backendConfig, ...config },
        })),
      setApiKey: (provider, key) =>
        set((state) => ({
          apiKeys: { ...state.apiKeys, [provider]: key },
        })),
      removeApiKey: (provider) =>
        set((state) => {
          const { [provider]: _, ...rest } = state.apiKeys;
          return { apiKeys: rest };
        }),
    }),
    {
      name: 'ga-settings',
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
        autonomousMode: state.autonomousMode,
        voice: state.voice,
        avatar: state.avatar,
        desktopPet: state.desktopPet,
        personality: state.personality,
        // apiKeys removed - stored securely in credential store only
        mcpServers: state.mcpServers,
        health: state.health,
        sidebarCollapsed: state.sidebarCollapsed,
        backendConfig: state.backendConfig,
        showOnboarding: state.showOnboarding,
      }),
    }
  )
);

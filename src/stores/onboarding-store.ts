import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface OnboardingProvider {
  id: string;
  name: string;
  description: string;
  icon: string;
  apiKeyUrl: string;
  requiresKey: boolean;
}

export const ONBOARDING_PROVIDERS: OnboardingProvider[] = [
  {
    id: 'pollinations',
    name: 'Pollinations (Free)',
    description: 'Free AI — no API key needed!',
    icon: '🌸',
    apiKeyUrl: 'https://pollinations.ai',
    requiresKey: false,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4o Mini, o1, o3',
    icon: '🤖',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
    requiresKey: true,
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude 4 Sonnet, Claude 4 Opus',
    icon: '🧠',
    apiKeyUrl: 'https://console.anthropic.com/settings/keys',
    requiresKey: true,
  },
  {
    id: 'google',
    name: 'Google AI',
    description: 'Gemini 2.5 Pro, Gemini 2.5 Flash',
    icon: '✨',
    apiKeyUrl: 'https://aistudio.google.com/apikey',
    requiresKey: true,
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    description: 'Llama, Mistral, Phi — runs locally',
    icon: '🦙',
    apiKeyUrl: 'https://ollama.com',
    requiresKey: false,
  },
  {
    id: 'groq',
    name: 'Groq',
    description: 'Fast Llama & Mixtral inference',
    icon: '⚡',
    apiKeyUrl: 'https://console.groq.com/keys',
    requiresKey: true,
  },
  {
    id: 'deepinfra',
    name: 'DeepInfra',
    description: 'Serverless LLM inference',
    icon: '🔥',
    apiKeyUrl: 'https://deepinfra.com/dash/api_keys',
    requiresKey: true,
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: 'Unified API for 200+ models',
    icon: '🌐',
    apiKeyUrl: 'https://openrouter.ai/keys',
    requiresKey: true,
  },
  {
    id: 'together',
    name: 'Together AI',
    description: 'Open-source model hosting',
    icon: '🤝',
    apiKeyUrl: 'https://api.together.xyz/settings/api-keys',
    requiresKey: true,
  },
  {
    id: 'mistral',
    name: 'Mistral',
    description: 'Mistral & Codestral models',
    icon: '🌀',
    apiKeyUrl: 'https://console.mistral.ai/api-keys/',
    requiresKey: true,
  },
];

interface OnboardingState {
  step: number;
  selectedProvider: string | null;
  apiKey: string;
  showApiKey: boolean;
  connectionStatus: 'idle' | 'testing' | 'success' | 'error';
  connectionError: string | null;
  isComplete: boolean;

  // Actions
  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  setSelectedProvider: (provider: string) => void;
  setApiKey: (key: string) => void;
  toggleShowApiKey: () => void;
  setConnectionStatus: (status: 'idle' | 'testing' | 'success' | 'error') => void;
  setConnectionError: (error: string | null) => void;
  completeOnboarding: () => void;
  reset: () => void;
}

const initialState = {
  step: 0,
  selectedProvider: null,
  apiKey: '',
  showApiKey: false,
  connectionStatus: 'idle' as const,
  connectionError: null,
  isComplete: false,
};

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setStep: (step) => set({ step }),
      nextStep: () => set((state) => ({ step: Math.min(state.step + 1, 5) })),
      prevStep: () => set((state) => ({ step: Math.max(state.step - 1, 0) })),
      setSelectedProvider: (provider) => set({ selectedProvider: provider }),
      setApiKey: (key) => set({ apiKey: key }),
      toggleShowApiKey: () => set((state) => ({ showApiKey: !state.showApiKey })),
      setConnectionStatus: (status) => set({ connectionStatus: status }),
      setConnectionError: (error) => set({ connectionError: error }),
      completeOnboarding: () => set({ isComplete: true }),
      reset: () => set(initialState),
    }),
    {
      name: 'ga-onboarding',
      partialize: (state) => ({
        isComplete: state.isComplete,
        selectedProvider: state.selectedProvider,
      }),
    }
  )
);

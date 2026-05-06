import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { BackendConnectionState } from '@/lib/backend';

export type AgentStatus = 'idle' | 'thinking' | 'acting' | 'streaming' | 'error';

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: 'pending' | 'success' | 'error';
  result?: string;
  duration?: number;
}

export interface ThinkingSection {
  id: string;
  content: string;
  duration?: number;
  collapsed: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: number;
  toolCalls?: ToolCall[];
  thinking?: ThinkingSection;
  isStreaming?: boolean;
  attachments?: string[];
  model?: string;
  expressions?: string[];
}

export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  isActive: boolean;
  health: 'healthy' | 'degraded' | 'down' | 'unknown';
  index: number;
}

export interface AgentMetrics {
  totalMessages: number;
  tokensUsed: number;
  llmCalls: number;
  uptime: number;
  errorRate: number;
  memoryUsage: number;
  skillsCrystallized: number;
}

export interface Session {
  id: string;
  title: string;
  messageCount: number;
  date: number;
  messages: ChatMessage[];
}

interface AgentState {
  status: AgentStatus;
  currentModel: LLMModel | null;
  models: LLMModel[];
  messages: ChatMessage[];
  sessions: Session[];
  currentSessionId: string | null;
  metrics: AgentMetrics;
  isStreaming: boolean;
  circuitBreakerOpen: boolean;
  activeTools: string[];

  // Backend connection
  backendConnected: BackendConnectionState;
  authToken: string | null;
  isAuthenticated: boolean;
  requiresAuth: boolean;

  // Personality / Expression
  currentExpression: string;

  // Actions
  setStatus: (status: AgentStatus) => void;
  setCurrentModel: (model: LLMModel) => void;
  setModels: (models: LLMModel[]) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  removeMessage: (id: string) => void;
  clearMessages: () => void;
  setStreaming: (streaming: boolean) => void;
  setCircuitBreaker: (open: boolean) => void;
  setActiveTools: (tools: string[]) => void;
  updateMetrics: (metrics: Partial<AgentMetrics>) => void;
  addSession: (session: Session) => void;
  removeSession: (id: string) => void;
  setCurrentSession: (id: string | null) => void;
  loadSession: (id: string) => Promise<void>;

  // Backend actions
  setBackendConnected: (state: BackendConnectionState) => void;
  setAuthToken: (token: string | null) => void;
  setAuthenticated: (auth: boolean) => void;
  setRequiresAuth: (requires: boolean) => void;
  setCurrentExpression: (expression: string) => void;
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      status: 'idle',
      currentModel: null,
      models: [],
      messages: [],
      sessions: [] as Session[],
      currentSessionId: null,
      metrics: {
        totalMessages: 0,
        tokensUsed: 0,
        llmCalls: 0,
        uptime: 0,
        errorRate: 0,
        memoryUsage: 0,
        skillsCrystallized: 0,
      },
      isStreaming: false,
      circuitBreakerOpen: false,
      activeTools: [],

      // Backend state
      backendConnected: 'disconnected',
      authToken: null,
      isAuthenticated: false,
      requiresAuth: false,

      // Expression state
      currentExpression: 'neutral',

      setStatus: (status) => set({ status }),
      setCurrentModel: (model) =>
        set((state) => ({
          currentModel: model,
          models: state.models.map((m) => ({
            ...m,
            isActive: m.id === model.id,
          })),
        })),
      setModels: (models) => {
        const activeModel = models.find((m) => m.isActive);
        set({
          models,
          currentModel: activeModel || models[0] || null,
        });
      },
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
          metrics: {
            ...state.metrics,
            totalMessages: state.metrics.totalMessages + 1,
          },
        })),
      updateMessage: (id, updates) =>
        set((state) => ({
          messages: state.messages.map((m) => {
            if (m.id !== id) return m;
            // toolCalls replaces entirely on update (expected behavior for state refreshes)
            return { ...m, ...updates };
          }),
        })),
      removeMessage: (id) =>
        set((state) => ({
          messages: state.messages.filter((m) => m.id !== id),
        })),
      clearMessages: () => set({ messages: [] }),
      setStreaming: (streaming) => set({ isStreaming: streaming }),
      setCircuitBreaker: (open) => set({ circuitBreakerOpen: open }),
      setActiveTools: (tools) => set({ activeTools: tools }),
      updateMetrics: (metrics) =>
        set((state) => ({
          metrics: { ...state.metrics, ...metrics },
        })),
      addSession: (session) =>
        set((state) => ({
          sessions: [session, ...state.sessions],
        })),
      removeSession: (id) =>
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== id),
        })),
      setCurrentSession: (id) => set({ currentSessionId: id }),
      loadSession: async (id) => {
        const { getMessagesBySession } = await import('@/lib/db');
        const messages = await getMessagesBySession(id);
        set({ currentSessionId: id, messages: messages || [] });
      },

      // Backend actions
      setBackendConnected: (state) => set({ backendConnected: state }),
      setAuthToken: (token) => set({ authToken: token }),
      setAuthenticated: (auth) => set({ isAuthenticated: auth }),
      setRequiresAuth: (requires) => set({ requiresAuth: requires }),
      setCurrentExpression: (expression) => set({ currentExpression: expression }),
    }),
    {
      name: 'ga-agent',
      partialize: (state) => ({
        sessions: state.sessions.map(s => ({ ...s, messages: [] })),
        currentSessionId: state.currentSessionId,
        currentModel: state.currentModel,
        backendConnected: state.backendConnected,
        // authToken removed - already stored in backend.ts localStorage
        // messages removed - loaded from IndexedDB on demand
      }),
    }
  )
);

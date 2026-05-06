import type { LLMModel, AgentMetrics, AgentStatus } from '@/stores/agent-store';
import { getApiBase, buildHeaders, getAuthToken, setAuthToken } from './backend';

// API_BASE is resolved dynamically via getApiBase() on every request

// ============ FALLBACK MOCK DATA (used when backend is disconnected) ============

const MOCK_TOOLS = [
  { name: 'web_search', description: 'Search the web for information', category: 'web', source: 'builtin', requires_confirmation: false },
  { name: 'file_read', description: 'Read file contents', category: 'filesystem', source: 'builtin', requires_confirmation: false },
  { name: 'file_write', description: 'Write content to a file', category: 'filesystem', source: 'builtin', requires_confirmation: true },
  { name: 'code_execute', description: 'Execute code in a sandbox', category: 'code', source: 'builtin', requires_confirmation: true },
  { name: 'screenshot', description: 'Take a screenshot of the screen', category: 'system', source: 'builtin', requires_confirmation: false },
  { name: 'browser_navigate', description: 'Navigate to a URL in browser', category: 'web', source: 'builtin', requires_confirmation: false },
  { name: 'terminal_run', description: 'Run terminal commands', category: 'system', source: 'builtin', requires_confirmation: true },
  { name: 'memory_store', description: 'Store information in memory', category: 'memory', source: 'builtin', requires_confirmation: false },
  { name: 'ocr_read', description: 'Read text from images', category: 'vision', source: 'builtin', requires_confirmation: false },
  { name: 'clipboard_read', description: 'Read clipboard contents', category: 'system', source: 'builtin', requires_confirmation: false },
  { name: 'clipboard_write', description: 'Write to clipboard', category: 'system', source: 'builtin', requires_confirmation: false },
  { name: 'skill_search', description: 'Search for crystallized skills', category: 'memory', source: 'builtin', requires_confirmation: false },
];

const MOCK_MEMORY_LAYERS = [
  { level: 'L0', name: 'Meta Rules', description: 'Core behavior and safety rules', size: 12, maxSize: 50, color: '#ef4444' },
  { level: 'L1', name: 'Index', description: 'Semantic index of knowledge', size: 156, maxSize: 500, color: '#f59e0b' },
  { level: 'L2', name: 'Global Facts', description: 'Verified facts and patterns', size: 89, maxSize: 300, color: '#22c55e' },
  { level: 'L3', name: 'Skills & SOPs', description: 'Crystallized skills and procedures', size: 34, maxSize: 200, color: '#7c3aed' },
  { level: 'L4', name: 'Archives', description: 'Compressed session history', size: 267, maxSize: 1000, color: '#6366f1' },
];

const MOCK_SKILLS = [
  { id: 'skill-1', name: 'Web Search & Summarize', category: 'web', quality: 0.92, tags: ['search', 'summarize', 'research'], usageCount: 45, lastUsed: Date.now() - 3600000 },
  { id: 'skill-2', name: 'Code Debug Cycle', category: 'code', quality: 0.88, tags: ['debug', 'code', 'fix'], usageCount: 32, lastUsed: Date.now() - 7200000 },
  { id: 'skill-3', name: 'File Organization SOP', category: 'filesystem', quality: 0.95, tags: ['organize', 'files', 'structure'], usageCount: 18, lastUsed: Date.now() - 86400000 },
  { id: 'skill-4', name: 'API Integration Pattern', category: 'code', quality: 0.85, tags: ['api', 'integration', 'rest'], usageCount: 27, lastUsed: Date.now() - 14400000 },
  { id: 'skill-5', name: 'Screen Analysis', category: 'vision', quality: 0.78, tags: ['screenshot', 'vision', 'analysis'], usageCount: 12, lastUsed: Date.now() - 43200000 },
  { id: 'skill-6', name: 'Data Extraction SOP', category: 'web', quality: 0.91, tags: ['extract', 'data', 'scrape'], usageCount: 22, lastUsed: Date.now() - 28800000 },
  { id: 'skill-7', name: 'Terminal Workflow', category: 'system', quality: 0.83, tags: ['terminal', 'cli', 'commands'], usageCount: 38, lastUsed: Date.now() - 1800000 },
];

const MOCK_SOPS = [
  { id: 'sop-1', name: 'Web Setup SOP', description: 'Standard procedure for setting up web automation', steps: 5, lastUpdated: Date.now() - 86400000 },
  { id: 'sop-2', name: 'Memory Management SOP', description: 'How to manage and clean memory layers', steps: 8, lastUpdated: Date.now() - 172800000 },
  { id: 'sop-3', name: 'Autonomous Operation SOP', description: 'Guidelines for autonomous task execution', steps: 12, lastUpdated: Date.now() - 259200000 },
  { id: 'sop-4', name: 'Vision API SOP', description: 'Procedure for vision-related tasks', steps: 6, lastUpdated: Date.now() - 345600000 },
];

// ============ SSE STREAMING TYPES ============

export interface SSEEvent {
  type: 'token' | 'thinking' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'keepalive' | 'expression';
  data: string;
}

export interface ChatRequest {
  message: string;
  stream?: boolean;
  images?: string[];
  source?: string;
}

// ============ HELPER: Fetch with error handling ============

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const baseUrl = getApiBase();
  const url = `${baseUrl}${path}`;
  const headers = buildHeaders();

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Token expired, clear it
      setAuthToken(null);
      throw new Error('Authentication required');
    }
    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorData.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ============ AUTH ============

// Auth functions are in backend.ts - use loginToBackend() and checkAuthStatus()

// ============ CHAT ============

/** Send a message and get a streaming response (SSE) using ReadableStream */
export async function* sendMessage(
  message: string,
  options?: { stream?: boolean; images?: string[]; source?: string; signal?: AbortSignal }
): AsyncGenerator<SSEEvent, void, unknown> {
  const baseUrl = getApiBase();
  const url = `${baseUrl}/chat`;
  const headers = buildHeaders();

  const body: ChatRequest = {
    message,
    stream: true,
    images: options?.images,
    source: options?.source,
  };

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        ...headers,
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(body),
      signal: options?.signal,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      yield { type: 'error', data: errorData.detail || `API error: ${response.status}` };
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      yield { type: 'error', data: 'No response body' };
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEventType = 'token';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        // SSE format: "event: xxx" or "data: xxx" or empty line
        if (line.startsWith('event:')) {
          currentEventType = line.slice(6).trim();
        } else if (line.startsWith('data:') && currentEventType !== 'event') {
          // Only process data lines if we have a complete event type
          // If currentEventType is still 'event' (partial), skip this data line
          const data = line.slice(5).trim();

          if (data === '[DONE]') {
            yield { type: 'done', data: '' };
            return;
          }

          // Map SSE event types to our types
          let eventType: SSEEvent['type'] = 'token';
          if (currentEventType === 'thinking') eventType = 'thinking';
          else if (currentEventType === 'tool_call') eventType = 'tool_call';
          else if (currentEventType === 'tool_result') eventType = 'tool_result';
          else if (currentEventType === 'expression' || data.startsWith('[face:')) eventType = 'expression';
          else if (currentEventType === 'keepalive' || data === '') eventType = 'keepalive';
          else if (currentEventType === 'error') eventType = 'error';

          // Check for expression tags in data
          const faceMatch = data.match(/\[face:(\w+)\]/);
          if (faceMatch) {
            yield { type: 'expression', data: faceMatch[1] };
            // Remove the tag and yield the rest as a token
            const cleaned = data.replace(/\[face:\w+\]/g, '').trim();
            if (cleaned) {
              yield { type: 'token', data: cleaned };
            }
          } else if (eventType !== 'keepalive') {
            yield { type: eventType, data };
          }

          currentEventType = 'token'; // Reset to default
        }
        // Empty line resets event type
        if (line.trim() === '') {
          currentEventType = 'token';
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      const remainingLine = buffer.trim();
      // Only yield if we have a complete data line (not a partial event: line)
      if (remainingLine.startsWith('data:')) {
        const data = remainingLine.slice(5).trim();
        if (data && data !== '[DONE]') {
          // Use the persisted currentEventType for the remaining buffer
          let eventType: SSEEvent['type'] = 'token';
          if (currentEventType === 'thinking') eventType = 'thinking';
          else if (currentEventType === 'tool_call') eventType = 'tool_call';
          else if (currentEventType === 'tool_result') eventType = 'tool_result';
          else if (currentEventType === 'expression') eventType = 'expression';
          else if (currentEventType === 'error') eventType = 'error';
          yield { type: eventType, data };
        }
      }
      // Don't yield partial event: lines as tokens
    }

    yield { type: 'done', data: '' };
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      yield { type: 'done', data: '' };
      return;
    }
    yield { type: 'error', data: err instanceof Error ? err.message : 'Unknown error occurred' };
  }
}

/** Send a message synchronously */
export async function sendMessageSync(message: string, options?: { images?: string[]; source?: string }): Promise<string> {
  try {
    const data = await apiFetch<{ response: string }>('/chat/sync', {
      method: 'POST',
      body: JSON.stringify({
        message,
        stream: false,
        images: options?.images,
        source: options?.source,
      }),
    });
    return data.response;
  } catch (err) {
    // Fallback to mock if backend is unavailable
    console.warn('Backend unavailable for sync chat, using fallback');
    return "I'm currently unable to connect to the backend. Please check that the GenericAgent server is running on port 8765.";
  }
}

// ============ MODELS ============

/** Get available LLM models from backend */
export async function getModels(): Promise<LLMModel[]> {
  try {
    const data = await apiFetch<Array<{ index: number; name: string; active: boolean }>>('/models');
    return data.map((model) => {
      // Parse provider from model name convention
      const provider = inferProvider(model.name);
      return {
        id: `model-${model.index}`,
        name: model.name,
        provider,
        isActive: model.active,
        health: 'healthy' as const, // Will be updated by status check
        index: model.index,
      };
    });
  } catch (err) {
    // Fallback to default models when backend unavailable
    console.warn('Backend unavailable for models, using defaults');
    return [
      { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI', isActive: true, health: 'unknown', index: 0 },
      { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', isActive: false, health: 'unknown', index: 1 },
      { id: 'claude-4-sonnet', name: 'Claude 4 Sonnet', provider: 'Anthropic', isActive: false, health: 'unknown', index: 2 },
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', provider: 'Google', isActive: false, health: 'unknown', index: 3 },
      { id: 'llama-3.3-70b', name: 'Llama 3.3 70B', provider: 'Ollama', isActive: false, health: 'unknown', index: 4 },
      { id: 'groq-llama-70b', name: 'Groq Llama 70B', provider: 'Groq', isActive: false, health: 'unknown', index: 5 },
      { id: 'pollinations-openai', name: 'Pollinations (Free)', provider: 'Pollinations', isActive: false, health: 'unknown', index: 6 },
      { id: 'deepinfra-llama', name: 'DeepInfra Llama', provider: 'DeepInfra', isActive: false, health: 'unknown', index: 7 },
      { id: 'openrouter-auto', name: 'OpenRouter Auto', provider: 'OpenRouter', isActive: false, health: 'unknown', index: 8 },
      { id: 'mistral-large', name: 'Mistral Large', provider: 'Mistral', isActive: false, health: 'unknown', index: 9 },
    ];
  }
}

/** Infer provider from model name */
function inferProvider(modelName: string): string {
  const lower = modelName.toLowerCase();
  if (lower.includes('gpt') || lower.includes('o1') || lower.includes('o3') || lower.includes('dall-e')) return 'OpenAI';
  if (lower.includes('claude')) return 'Anthropic';
  if (lower.includes('gemini') || lower.includes('gemma')) return 'Google';
  // Check specific providers BEFORE generic llama/mistral/phi/qwen catch-all
  if (lower.includes('groq')) return 'Groq';
  if (lower.includes('pollination')) return 'Pollinations';
  if (lower.includes('deepinfra') || lower.includes('deep-infra')) return 'DeepInfra';
  if (lower.includes('openrouter')) return 'OpenRouter';
  if (lower.includes('together')) return 'Together AI';
  if (lower.includes('codestral')) return 'Mistral';
  // Generic catch-all for locally-hosted models
  if (lower.includes('llama') || lower.includes('phi') || lower.includes('qwen')) return 'Ollama';
  if (lower.includes('mistral')) return 'Mistral';
  return 'Other';
}

/** Switch to a different LLM model */
export async function switchModel(modelIndex: number): Promise<{ success: boolean; model: string }> {
  try {
    const data = await apiFetch<{ success: boolean; model: string }>('/models/switch', {
      method: 'POST',
      body: JSON.stringify({ index: modelIndex }),
    });
    return data;
  } catch (err) {
    console.warn('Backend unavailable for model switch');
    return { success: false, model: '' };
  }
}

// ============ TOOLS ============

/** Get available tools */
export async function getTools() {
  try {
    const data = await apiFetch<Array<{
      name: string;
      description: string;
      category?: string;
      source?: string;
      requires_confirmation?: boolean;
    }>>('/tools');
    return data.map((tool) => ({
      name: tool.name,
      description: tool.description,
      category: tool.category || 'general',
      source: tool.source || 'builtin',
      requires_confirmation: tool.requires_confirmation || false,
    }));
  } catch (err) {
    console.warn('Backend unavailable for tools, using defaults');
    return MOCK_TOOLS;
  }
}

// ============ STATUS ============

/** Get agent status */
export async function getStatus(): Promise<{ status: AgentStatus; metrics: AgentMetrics; modelName: string }> {
  try {
    const data = await apiFetch<{
      status: string;
      model: string;
      metrics?: {
        total_messages?: number;
        tokens_used?: number;
        llm_calls?: number;
        uptime?: number;
        error_rate?: number;
        memory_usage?: number;
        skills_crystallized?: number;
      };
    }>('/status');

    const statusMap: Record<string, AgentStatus> = {
      idle: 'idle',
      running: 'streaming',
      thinking: 'thinking',
      acting: 'acting',
      error: 'error',
    };

    return {
      status: statusMap[data.status] || 'idle',
      modelName: data.model || '',
      metrics: {
        totalMessages: data.metrics?.total_messages || 0,
        tokensUsed: data.metrics?.tokens_used || 0,
        llmCalls: data.metrics?.llm_calls || 0,
        uptime: data.metrics?.uptime || 0,
        errorRate: data.metrics?.error_rate || 0,
        memoryUsage: data.metrics?.memory_usage || 0,
        skillsCrystallized: data.metrics?.skills_crystallized || 0,
      },
    };
  } catch (err) {
    console.warn('Backend unavailable for status');
    return {
      status: 'idle',
      modelName: '',
      metrics: {
        totalMessages: 0,
        tokensUsed: 0,
        llmCalls: 0,
        uptime: 0,
        errorRate: 0,
        memoryUsage: 0,
        skillsCrystallized: 0,
      },
    };
  }
}

// ============ MEMORY ============

/** Search memory semantically */
export async function searchMemory(query: string, options?: { top_k?: number; category?: string }) {
  try {
    const data = await apiFetch<Array<{
      id?: string;
      content: string;
      layer?: string;
      score: number;
      timestamp?: number;
      category?: string;
    }>>('/memory/search', {
      method: 'POST',
      body: JSON.stringify({
        query,
        top_k: options?.top_k || 5,
        category: options?.category,
      }),
    });
    return data.map((item) => ({
      id: item.id || `mem-${Math.random().toString(36).slice(2, 8)}`,
      content: item.content,
      layer: item.layer || item.category || 'L2',
      score: item.score,
      timestamp: item.timestamp || Date.now(),
    }));
  } catch (err) {
    console.warn('Backend unavailable for memory search, using fallback');
    return [
      {
        id: 'mem-1',
        content: `Found relevant information about "${query}" in memory layer L2 (Global Facts).`,
        layer: 'L2',
        score: 0.92,
        timestamp: Date.now() - 3600000,
      },
      {
        id: 'mem-2',
        content: `Related skill: Web Search & Summarize — often used for queries similar to "${query}".`,
        layer: 'L3',
        score: 0.85,
        timestamp: Date.now() - 7200000,
      },
      {
        id: 'mem-3',
        content: `Archived session containing discussions about "${query}" and related topics.`,
        layer: 'L4',
        score: 0.73,
        timestamp: Date.now() - 86400000,
      },
    ];
  }
}

// ============ ABORT ============

/** Abort current task */
export async function abortTask(): Promise<{ success: boolean }> {
  try {
    const data = await apiFetch<{ success: boolean }>('/abort', { method: 'POST' });
    return data;
  } catch (err) {
    console.warn('Backend unavailable for abort');
    return { success: false };
  }
}

// ============ CONNECTION TEST ============

/** Test connection to LLM provider */
export async function testConnection(provider: string, apiKey: string): Promise<{ success: boolean; error?: string }> {
  try {
    // Try to hit the backend's models endpoint to verify connectivity
    const data = await apiFetch<{ success: boolean; error?: string }>('/models/test', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    return data;
  } catch (err) {
    return { success: false, error: 'Cannot connect to backend. Is the server running on port 8765?' };
  }
}

// ============ MCP ============

/** Get MCP server status */
export async function getMcpStatus() {
  try {
    const data = await apiFetch<Array<{
      name: string;
      url?: string;
      status: string;
      tools_count?: number;
    }>>('/mcp/status');
    return data.map((server) => ({
      name: server.name,
      url: server.url || '',
      status: server.status as 'connected' | 'disconnected' | 'error',
      toolsCount: server.tools_count || 0,
    }));
  } catch (err) {
    console.warn('Backend unavailable for MCP status, using defaults');
    return [
      { name: 'Filesystem MCP', url: 'http://localhost:3001', status: 'disconnected' as const, toolsCount: 5 },
      { name: 'Web Search MCP', url: 'http://localhost:3002', status: 'disconnected' as const, toolsCount: 3 },
      { name: 'Database MCP', url: 'http://localhost:3003', status: 'disconnected' as const, toolsCount: 0 },
    ];
  }
}

// ============ WEBSOCKET ============

/** Create a WebSocket connection for full-duplex chat */
export function createChatWebSocket(): WebSocket | null {
  try {
    const httpBase = getApiBase();
    const wsBase = httpBase.replace(/^http/, 'ws');
    const token = getAuthToken();
    const url = token ? `${wsBase}/ws/chat?token=${encodeURIComponent(token)}` : `${wsBase}/ws/chat`;
    return new WebSocket(url);
  } catch (err) {
    console.warn('Failed to create WebSocket:', err);
    return null;
  }
}

// ============ EXPRESSION PARSING ============

/** Parse [face:xxx] expression tags from text */
export function parseExpressions(text: string): { expressions: string[]; cleanText: string } {
  const expressionRegex = /\[face:(\w+)\]/g;
  const expressions: string[] = [];
  let match;

  while ((match = expressionRegex.exec(text)) !== null) {
    expressions.push(match[1]);
  }

  const cleanText = text.replace(/\[face:\w+\]/g, '').trim();
  return { expressions, cleanText };
}

// ============ MEMORY LAYERS / SKILLS / SOPs ============

/** Get memory layers from backend, with fallback to mock data */
export async function getMemoryLayers() {
  try {
    const data = await apiFetch<Array<{
      level: string;
      name: string;
      description: string;
      size: number;
      maxSize: number;
      color: string;
    }>>('/memory/layers');
    return data;
  } catch (err) {
    console.warn('Backend unavailable for memory layers, using fallback');
    return MOCK_MEMORY_LAYERS;
  }
}

/** Get skills from backend, with fallback to mock data */
export async function getSkills() {
  try {
    const data = await apiFetch<Array<{
      id: string;
      name: string;
      category: string;
      quality: number;
      tags: string[];
      usageCount: number;
      lastUsed: number;
    }>>('/memory/skills');
    return data;
  } catch (err) {
    console.warn('Backend unavailable for skills, using fallback');
    return MOCK_SKILLS;
  }
}

/** Get SOPs from backend, with fallback to mock data */
export async function getSOPs() {
  try {
    const data = await apiFetch<Array<{
      id: string;
      name: string;
      description: string;
      steps: number;
      lastUpdated: number;
    }>>('/memory/sops');
    return data;
  } catch (err) {
    console.warn('Backend unavailable for SOPs, using fallback');
    return MOCK_SOPS;
  }
}

// Export mock data for direct access (fallback)
export { MOCK_TOOLS, MOCK_MEMORY_LAYERS, MOCK_SKILLS, MOCK_SOPS };

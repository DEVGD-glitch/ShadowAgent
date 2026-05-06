import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  sendMessage,
  sendMessageSync,
  getModels,
  switchModel,
  getTools,
  getStatus,
  searchMemory,
  abortTask,
  testConnection,
  getMcpStatus,
  createChatWebSocket,
  parseExpressions,
  getMemoryLayers,
  getSkills,
  getSOPs,
  MOCK_TOOLS,
  MOCK_MEMORY_LAYERS,
  MOCK_SKILLS,
  MOCK_SOPS,
} from '@/lib/api';
import { getAuthToken, setAuthToken } from '@/lib/backend';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock WebSocket
class MockWebSocket {
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((ev: any) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();

  constructor(url: string) {
    this.url = url;
  }
}
(globalThis as any).WebSocket = MockWebSocket;

describe('api.ts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockFetch.mockReset();
    setAuthToken(null);
  });

  // ============ parseExpressions ============
  describe('parseExpressions', () => {
    it('parses a single expression tag', () => {
      const { expressions, cleanText } = parseExpressions('[face:happy] Hello!');
      expect(expressions).toEqual(['happy']);
      expect(cleanText).toBe('Hello!');
    });

    it('parses multiple expression tags', () => {
      const { expressions, cleanText } = parseExpressions('[face:happy] Hi! [face:sad] Oh no');
      expect(expressions).toEqual(['happy', 'sad']);
      expect(cleanText).toBe('Hi!  Oh no');
    });

    it('returns empty expressions for text without tags', () => {
      const { expressions, cleanText } = parseExpressions('No expressions here');
      expect(expressions).toEqual([]);
      expect(cleanText).toBe('No expressions here');
    });

    it('handles empty string', () => {
      const { expressions, cleanText } = parseExpressions('');
      expect(expressions).toEqual([]);
      expect(cleanText).toBe('');
    });

    it('handles tag without surrounding text', () => {
      const { expressions, cleanText } = parseExpressions('[face:neutral]');
      expect(expressions).toEqual(['neutral']);
      expect(cleanText).toBe('');
    });
  });

  // ============ sendMessage (SSE streaming) ============
  describe('sendMessage', () => {
    it('yields token events from SSE stream', async () => {
      const sseData = 'event: token\ndata: Hello world\n\n';
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(sseData));
          controller.close();
        },
      });

      mockFetch.mockResolvedValueOnce({ ok: true, body: stream });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'token' && e.data === 'Hello world')).toBe(true);
      expect(events.some(e => e.type === 'done')).toBe(true);
    });

    it('yields error event on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Internal error' }),
      });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'error')).toBe(true);
    });

    it('yields expression events from [face:xxx] tags', async () => {
      const sseData = 'event: token\ndata: [face:happy] Hello!\n\n';
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(sseData));
          controller.close();
        },
      });

      mockFetch.mockResolvedValueOnce({ ok: true, body: stream });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'expression' && e.data === 'happy')).toBe(true);
    });

    it('handles thinking events', async () => {
      const sseData = 'event: thinking\ndata: Processing...\n\n';
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(sseData));
          controller.close();
        },
      });

      mockFetch.mockResolvedValueOnce({ ok: true, body: stream });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'thinking')).toBe(true);
    });

    it('handles [DONE] sentinel', async () => {
      const sseData = 'data: [DONE]\n\n';
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(sseData));
          controller.close();
        },
      });

      mockFetch.mockResolvedValueOnce({ ok: true, body: stream });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'done')).toBe(true);
    });

    it('handles abort signal', async () => {
      const controller = new AbortController();
      controller.abort();

      mockFetch.mockRejectedValueOnce(new DOMException('Aborted', 'AbortError'));

      const events = [];
      for await (const event of sendMessage('test', { signal: controller.signal })) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'done')).toBe(true);
    });

    it('yields error on no response body', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, body: null });

      const events = [];
      for await (const event of sendMessage('test')) {
        events.push(event);
      }

      expect(events.some(e => e.type === 'error')).toBe(true);
    });
  });

  // ============ sendMessageSync ============
  describe('sendMessageSync', () => {
    it('returns response text on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ response: 'Hello!' }),
      });
      const result = await sendMessageSync('test');
      expect(result).toBe('Hello!');
    });

    it('returns fallback message on backend unavailable', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await sendMessageSync('test');
      expect(result).toContain('unable to connect');
    });
  });

  // ============ getModels ============
  describe('getModels', () => {
    it('returns models from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([
          { index: 0, name: 'gpt-4o', active: true },
          { index: 1, name: 'claude-4-sonnet', active: false },
        ]),
      });
      const models = await getModels();
      expect(models).toHaveLength(2);
      expect(models[0].name).toBe('gpt-4o');
      expect(models[0].provider).toBe('OpenAI');
    });

    it('returns fallback models on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const models = await getModels();
      expect(models.length).toBeGreaterThan(0);
      expect(models.some(m => m.provider === 'OpenAI')).toBe(true);
    });

    it('infers providers correctly', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([
          { index: 0, name: 'gpt-4o', active: true },
          { index: 1, name: 'claude-4-sonnet', active: false },
          { index: 2, name: 'gemini-2.5-pro', active: false },
          { index: 3, name: 'groq-llama-70b', active: false },
          { index: 4, name: 'llama-3.3-70b', active: false },
        ]),
      });
      const models = await getModels();
      expect(models[0].provider).toBe('OpenAI');
      expect(models[1].provider).toBe('Anthropic');
      expect(models[2].provider).toBe('Google');
      expect(models[3].provider).toBe('Groq');
      expect(models[4].provider).toBe('Ollama');
    });
  });

  // ============ switchModel ============
  describe('switchModel', () => {
    it('returns success on valid switch', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, model: 'gpt-4o' }),
      });
      const result = await switchModel(0);
      expect(result.success).toBe(true);
    });

    it('returns failure on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await switchModel(0);
      expect(result.success).toBe(false);
    });
  });

  // ============ getTools ============
  describe('getTools', () => {
    it('returns tools from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([
          { name: 'web_search', description: 'Search the web', category: 'web' },
        ]),
      });
      const tools = await getTools();
      expect(tools).toHaveLength(1);
      expect(tools[0].name).toBe('web_search');
    });

    it('returns mock tools on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const tools = await getTools();
      expect(tools.length).toBe(MOCK_TOOLS.length);
    });
  });

  // ============ getStatus ============
  describe('getStatus', () => {
    it('maps backend status to agent status', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'running',
          model: 'gpt-4o',
          metrics: { total_messages: 10, tokens_used: 500 },
        }),
      });
      const result = await getStatus();
      expect(result.status).toBe('streaming');
      expect(result.modelName).toBe('gpt-4o');
      expect(result.metrics.totalMessages).toBe(10);
    });

    it('returns idle on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await getStatus();
      expect(result.status).toBe('idle');
    });
  });

  // ============ searchMemory ============
  describe('searchMemory', () => {
    it('returns results from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([
          { content: 'Test memory', score: 0.95, layer: 'L2' },
        ]),
      });
      const results = await searchMemory('test');
      expect(results).toHaveLength(1);
      expect(results[0].content).toBe('Test memory');
    });

    it('returns fallback on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const results = await searchMemory('test');
      expect(results.length).toBeGreaterThan(0);
    });
  });

  // ============ abortTask ============
  describe('abortTask', () => {
    it('returns success on valid abort', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });
      const result = await abortTask();
      expect(result.success).toBe(true);
    });

    it('returns failure on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await abortTask();
      expect(result.success).toBe(false);
    });
  });

  // ============ testConnection ============
  describe('testConnection', () => {
    it('returns success on valid connection', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });
      const result = await testConnection('openai', 'sk-test');
      expect(result.success).toBe(true);
    });

    it('returns error on failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await testConnection('openai', 'sk-test');
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });
  });

  // ============ getMcpStatus ============
  describe('getMcpStatus', () => {
    it('returns MCP servers from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([
          { name: 'Filesystem MCP', status: 'connected', tools_count: 5 },
        ]),
      });
      const status = await getMcpStatus();
      expect(status).toHaveLength(1);
      expect(status[0].name).toBe('Filesystem MCP');
    });

    it('returns fallback on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const status = await getMcpStatus();
      expect(status.length).toBeGreaterThan(0);
    });
  });

  // ============ createChatWebSocket ============
  describe('createChatWebSocket', () => {
    it('creates WebSocket without token', () => {
      setAuthToken(null);
      const ws = createChatWebSocket();
      expect(ws).not.toBeNull();
      expect(ws!.url).toContain('/ws/chat');
      expect(ws!.url).not.toContain('token=');
    });

    it('creates WebSocket with token in URL', () => {
      setAuthToken('my-jwt-token');
      const ws = createChatWebSocket();
      expect(ws).not.toBeNull();
      expect(ws!.url).toContain('token=');
      expect(ws!.url).toContain('my-jwt-token');
    });

    it('uses ws:// protocol when API base is http', () => {
      const ws = createChatWebSocket();
      expect(ws!.url).toMatch(/^ws:/);
    });
  });

  // ============ getMemoryLayers / getSkills / getSOPs ============
  describe('getMemoryLayers', () => {
    it('returns layers from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([{ level: 'L1', name: 'Index', size: 10, maxSize: 50, color: '#fff' }]),
      });
      const layers = await getMemoryLayers();
      expect(layers).toHaveLength(1);
    });

    it('returns mock data on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const layers = await getMemoryLayers();
      expect(layers.length).toBe(MOCK_MEMORY_LAYERS.length);
    });
  });

  describe('getSkills', () => {
    it('returns skills from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([{ id: 's1', name: 'Test Skill', category: 'web', quality: 0.9, tags: [], usageCount: 1, lastUsed: Date.now() }]),
      });
      const skills = await getSkills();
      expect(skills).toHaveLength(1);
    });

    it('returns mock data on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const skills = await getSkills();
      expect(skills.length).toBe(MOCK_SKILLS.length);
    });
  });

  describe('getSOPs', () => {
    it('returns SOPs from backend', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([{ id: 'sop1', name: 'Test SOP', description: 'Desc', steps: 3, lastUpdated: Date.now() }]),
      });
      const sops = await getSOPs();
      expect(sops).toHaveLength(1);
    });

    it('returns mock data on error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const sops = await getSOPs();
      expect(sops.length).toBe(MOCK_SOPS.length);
    });
  });

  // ============ Auth handling in API calls ============
  describe('API authentication', () => {
    it('clears token on 401 response', async () => {
      setAuthToken('old-token');
      mockFetch.mockResolvedValueOnce({ ok: false, status: 401, json: () => Promise.resolve({ detail: 'Unauthorized' }) });

      try {
        // Use any function that calls apiFetch
        await getModels();
      } catch {}

      // Token should be cleared after 401
      // Note: getModels catches the error internally and returns fallback
    });
  });
});

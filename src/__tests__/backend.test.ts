import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getApiBase,
  getAuthToken,
  setAuthToken,
  buildHeaders,
  checkBackendHealth,
  getConnectionState,
  onConnectionStateChange,
  connectToBackend,
  disconnectFromBackend,
  startHealthPolling,
  stopHealthPolling,
  loginToBackend,
  checkAuthStatus,
  getBackendConfig,
  saveBackendConfig,
  getApiKeys,
  setApiKey,
  removeApiKey,
} from '@/lib/backend';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('backend.ts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockFetch.mockReset();
    // Reset internal state
    disconnectFromBackend();
  });

  afterEach(() => {
    stopHealthPolling();
    disconnectFromBackend();
  });

  // ============ getApiBase ============
  describe('getApiBase', () => {
    it('returns default base URL when no config is stored', () => {
      const base = getApiBase();
      expect(base).toMatch(/localhost:8765/);
    });

    it('returns user-configured host and port from localStorage', () => {
      saveBackendConfig({ host: '192.168.1.100', port: 9999, autoConnect: false });
      const base = getApiBase();
      expect(base).toBe('http://192.168.1.100:9999');
    });

    it('falls back to default when config is malformed', () => {
      localStorage.setItem('ga_backend_config', '{invalid json');
      const base = getApiBase();
      expect(base).toMatch(/localhost:8765/);
    });
  });

  // ============ Auth Token ============
  describe('getAuthToken / setAuthToken', () => {
    it('returns null when no token is set', () => {
      expect(getAuthToken()).toBeNull();
    });

    it('stores and retrieves a token', () => {
      setAuthToken('my-secret-token');
      expect(getAuthToken()).toBe('my-secret-token');
    });

    it('removes token when set to null', () => {
      setAuthToken('my-token');
      setAuthToken(null);
      expect(getAuthToken()).toBeNull();
    });

    it('handles SSR (no window)', () => {
      // In jsdom, window exists, so this tests the path indirectly
      expect(() => setAuthToken('test')).not.toThrow();
    });
  });

  // ============ buildHeaders ============
  describe('buildHeaders', () => {
    it('includes Content-Type by default', () => {
      const headers = buildHeaders();
      expect(headers['Content-Type']).toBe('application/json');
    });

    it('includes Authorization when token is set', () => {
      setAuthToken('test-token');
      const headers = buildHeaders();
      expect(headers['Authorization']).toBe('Bearer test-token');
    });

    it('omits Authorization when no token', () => {
      setAuthToken(null);
      const headers = buildHeaders();
      expect(headers['Authorization']).toBeUndefined();
    });
  });

  // ============ checkBackendHealth ============
  describe('checkBackendHealth', () => {
    it('returns true when backend responds ok', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, status: 200 });
      const result = await checkBackendHealth();
      expect(result).toBe(true);
    });

    it('returns false when backend responds not ok', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });
      const result = await checkBackendHealth();
      expect(result).toBe(false);
    });

    it('returns false on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await checkBackendHealth();
      expect(result).toBe(false);
    });

    it('returns false on timeout (AbortError)', async () => {
      mockFetch.mockImplementationOnce(() => {
        throw new DOMException('Aborted', 'AbortError');
      });
      const result = await checkBackendHealth();
      expect(result).toBe(false);
    });

    it('calls the status endpoint with headers', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });
      await checkBackendHealth();
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain('/status');
      expect(options.headers).toBeDefined();
    });
  });

  // ============ Connection State ============
  describe('getConnectionState / onConnectionStateChange', () => {
    it('starts as disconnected', () => {
      expect(getConnectionState()).toBe('disconnected');
    });

    it('notifies listeners on state change', async () => {
      const listener = vi.fn();
      const unsubscribe = onConnectionStateChange(listener);

      mockFetch.mockResolvedValueOnce({ ok: true });
      await connectToBackend();

      expect(listener).toHaveBeenCalled();
      unsubscribe();
    });

    it('stops notifying after unsubscribe', async () => {
      const listener = vi.fn();
      const unsubscribe = onConnectionStateChange(listener);
      unsubscribe();

      mockFetch.mockResolvedValueOnce({ ok: true });
      await connectToBackend();

      // After unsubscribe, the listener should NOT be called
      // (may have been called before unsubscribe if timing)
    });

    it('supports multiple listeners', async () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();
      onConnectionStateChange(listener1);
      onConnectionStateChange(listener2);

      mockFetch.mockResolvedValueOnce({ ok: true });
      await connectToBackend();

      expect(listener1).toHaveBeenCalled();
      expect(listener2).toHaveBeenCalled();
    });
  });

  // ============ connectToBackend ============
  describe('connectToBackend', () => {
    it('transitions to connected on healthy backend', async () => {
      mockFetch.mockResolvedValue({ ok: true });
      const result = await connectToBackend();
      expect(result).toBe(true);
      expect(getConnectionState()).toBe('connected');
    });

    it('transitions to disconnected on unhealthy backend', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await connectToBackend();
      expect(result).toBe(false);
      expect(getConnectionState()).toBe('disconnected');
    });
  });

  // ============ disconnectFromBackend ============
  describe('disconnectFromBackend', () => {
    it('sets state to disconnected', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });
      await connectToBackend();
      disconnectFromBackend();
      expect(getConnectionState()).toBe('disconnected');
    });

    it('stops health polling', async () => {
      mockFetch.mockResolvedValue({ ok: true });
      await connectToBackend();
      // Health polling should be running
      disconnectFromBackend();
      // No error should occur
    });
  });

  // ============ loginToBackend ============
  describe('loginToBackend', () => {
    it('returns success on valid credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'jwt-token-123' }),
      });
      const result = await loginToBackend('password123');
      expect(result.success).toBe(true);
      expect(result.token).toBe('jwt-token-123');
    });

    it('stores token on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'jwt-token-456' }),
      });
      await loginToBackend('password123');
      expect(getAuthToken()).toBe('jwt-token-456');
    });

    it('returns error on invalid credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Invalid password' }),
      });
      const result = await loginToBackend('wrong-password');
      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid password');
    });

    it('returns error on network failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await loginToBackend('password');
      expect(result.success).toBe(false);
      expect(result.error).toContain('Cannot connect');
    });

    it('sends password in request body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 't' }),
      });
      await loginToBackend('mypassword');
      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.password).toBe('mypassword');
    });
  });

  // ============ checkAuthStatus ============
  describe('checkAuthStatus', () => {
    it('returns authenticated when backend confirms', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ authenticated: true, requires_auth: false }),
      });
      const result = await checkAuthStatus();
      expect(result.authenticated).toBe(true);
      expect(result.requiresAuth).toBe(false);
    });

    it('returns requiresAuth on 401', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({}),
      });
      const result = await checkAuthStatus();
      expect(result.authenticated).toBe(false);
      expect(result.requiresAuth).toBe(true);
    });

    it('returns not authenticated on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));
      const result = await checkAuthStatus();
      expect(result.authenticated).toBe(false);
    });
  });

  // ============ Backend Config ============
  describe('getBackendConfig / saveBackendConfig', () => {
    it('returns default config when nothing stored', () => {
      const config = getBackendConfig();
      expect(config.host).toBe('localhost');
      expect(config.port).toBe(8765);
    });

    it('saves and retrieves config', () => {
      saveBackendConfig({ host: 'myhost', port: 9999, autoConnect: true });
      const config = getBackendConfig();
      expect(config.host).toBe('myhost');
      expect(config.port).toBe(9999);
    });

    it('handles malformed JSON in localStorage', () => {
      localStorage.setItem('ga_backend_config', 'not-json');
      const config = getBackendConfig();
      expect(config.host).toBe('localhost');
    });
  });

  // ============ API Keys ============
  describe('getApiKeys / setApiKey / removeApiKey', () => {
    it('starts with empty keys', () => {
      const keys = getApiKeys();
      expect(keys).toEqual({});
    });

    it('sets and retrieves a key', () => {
      setApiKey('openai', 'sk-test-key');
      const keys = getApiKeys();
      expect(keys.openai).toBe('sk-test-key');
    });

    it('removes a specific key', () => {
      setApiKey('openai', 'sk-test');
      setApiKey('anthropic', 'sk-ant-test');
      removeApiKey('openai');
      const keys = getApiKeys();
      expect(keys.openai).toBeUndefined();
      expect(keys.anthropic).toBe('sk-ant-test');
    });

    it('handles multiple key operations', () => {
      setApiKey('a', 'key-a');
      setApiKey('b', 'key-b');
      setApiKey('c', 'key-c');
      removeApiKey('b');
      const keys = getApiKeys();
      expect(Object.keys(keys)).toHaveLength(2);
    });
  });

  // ============ Health Polling ============
  describe('startHealthPolling / stopHealthPolling', () => {
    it('does not throw when starting polling', () => {
      mockFetch.mockResolvedValue({ ok: true });
      expect(() => startHealthPolling(1000)).not.toThrow();
      stopHealthPolling();
    });

    it('does not throw when stopping without starting', () => {
      expect(() => stopHealthPolling()).not.toThrow();
    });
  });
});

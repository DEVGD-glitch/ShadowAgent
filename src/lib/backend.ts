/**
 * Backend Connection Manager for GenericAgent FastAPI backend.
 * Handles auto-discovery, health checks, auto-reconnect, and token management.
 */

const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8765';
const TOKEN_KEY = 'ga_auth_token';
const BACKEND_STATUS_KEY = 'ga_backend_status';

export type BackendConnectionState = 'connected' | 'disconnected' | 'connecting';

// BackendConfig is defined in settings-store.ts
import type { BackendConfig } from '@/stores/settings-store';
export type { BackendConfig } from '@/stores/settings-store';

let healthCheckInterval: ReturnType<typeof setInterval> | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
let statusListeners: Array<(state: BackendConnectionState) => void> = [];
let currentConnectionState: BackendConnectionState = 'disconnected';

/**
 * Get the API base URL, respecting user-configured host/port
 */
export function getApiBase(): string {
  try {
    const config = getBackendConfig();
    if (config.host && config.port) {
      return `http://${config.host}:${config.port}`;
    }
  } catch {
    // Fall through to default
  }
  return DEFAULT_API_BASE;
}

/**
 * Get the stored auth token
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Set the auth token
 */
export function setAuthToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

/**
 * Build headers with optional auth
 */
export function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Check if backend is reachable
 */
export async function checkBackendHealth(): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${getApiBase()}/status`, {
      signal: controller.signal,
      headers: buildHeaders(),
    });
    clearTimeout(timeout);
    return response.ok;
  } catch {
    clearTimeout(timeout);
    return false;
  }
}

/**
 * Get current connection state
 */
export function getConnectionState(): BackendConnectionState {
  return currentConnectionState;
}

/**
 * Register a callback for connection state changes
 * Returns an unsubscribe function
 */
export function onConnectionStateChange(callback: (state: BackendConnectionState) => void): () => void {
  statusListeners.push(callback);
  return () => {
    statusListeners = statusListeners.filter(l => l !== callback);
  };
}

/**
 * Update connection state and notify listeners
 */
function notifyStatusChange(state: BackendConnectionState): void {
  statusListeners.forEach(l => l(state));
}

function updateConnectionState(state: BackendConnectionState): void {
  currentConnectionState = state;
  if (typeof window !== 'undefined') {
    localStorage.setItem(BACKEND_STATUS_KEY, state);
  }
  notifyStatusChange(state);
}

/**
 * Start health check polling
 */
export function startHealthPolling(intervalMs: number = 15000): void {
  stopHealthPolling();

  // Initial check
  performHealthCheck();

  healthCheckInterval = setInterval(performHealthCheck, intervalMs);
}

/**
 * Stop health check polling
 */
export function stopHealthPolling(): void {
  if (healthCheckInterval) {
    clearInterval(healthCheckInterval);
    healthCheckInterval = null;
  }
}

/**
 * Perform a single health check
 */
async function performHealthCheck(): Promise<void> {
  const wasConnected = currentConnectionState === 'connected';
  const isHealthy = await checkBackendHealth();

  if (isHealthy && !wasConnected) {
    updateConnectionState('connected');
  } else if (!isHealthy && wasConnected) {
    updateConnectionState('disconnected');
    // Attempt auto-reconnect after a delay (cancellable)
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    reconnectTimeout = setTimeout(async () => {
      reconnectTimeout = null;
      const retry = await checkBackendHealth();
      if (retry) {
        updateConnectionState('connected');
      }
    }, 5000);
  }
}

/**
 * Attempt to connect to the backend
 */
export async function connectToBackend(): Promise<boolean> {
  updateConnectionState('connecting');
  const isHealthy = await checkBackendHealth();
  if (isHealthy) {
    updateConnectionState('connected');
    startHealthPolling();
    return true;
  }
  updateConnectionState('disconnected');
  return false;
}

/**
 * Disconnect from backend
 */
export function disconnectFromBackend(): void {
  stopHealthPolling();
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  updateConnectionState('disconnected');
}

/**
 * Login to the backend
 */
export async function loginToBackend(password?: string): Promise<{ success: boolean; token?: string; error?: string }> {
  try {
    const response = await fetch(`${getApiBase()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password || '' }),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.token) {
        setAuthToken(data.token);
      }
      return { success: true, token: data.token };
    }

    const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
    return { success: false, error: errorData.detail || 'Login failed' };
  } catch (err) {
    return { success: false, error: 'Cannot connect to backend' };
  }
}

/**
 * Check authentication status
 */
export async function checkAuthStatus(): Promise<{ authenticated: boolean; requiresAuth: boolean }> {
  try {
    const response = await fetch(`${getApiBase()}/auth/status`, {
      headers: buildHeaders(),
    });
    if (response.ok) {
      const data = await response.json();
      return { authenticated: data.authenticated ?? true, requiresAuth: data.requires_auth ?? false };
    }
    return { authenticated: false, requiresAuth: response.status === 401 };
  } catch {
    return { authenticated: false, requiresAuth: false };
  }
}

/**
 * Get backend config from localStorage
 */
export function getBackendConfig(): BackendConfig {
  if (typeof window === 'undefined') return { host: 'localhost', port: 8765, autoConnect: false };
  try {
    const stored = localStorage.getItem('ga_backend_config');
    if (stored) {
      const config = JSON.parse(stored);
      if (!config.autoConnect) config.autoConnect = false;
      return config;
    }
  } catch {}
  return { host: 'localhost', port: 8765, autoConnect: false };
}

/**
 * Save backend config to localStorage
 */
export function saveBackendConfig(config: BackendConfig): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('ga_backend_config', JSON.stringify(config));
}

/**
 * API keys management per provider
 */
export function getApiKeys(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  try {
    const stored = localStorage.getItem('ga_api_keys');
    if (stored) return JSON.parse(stored);
  } catch {}
  return {};
}

export function setApiKey(provider: string, key: string): void {
  if (typeof window === 'undefined') return;
  const keys = getApiKeys();
  keys[provider] = key;
  localStorage.setItem('ga_api_keys', JSON.stringify(keys));
}

export function removeApiKey(provider: string): void {
  if (typeof window === 'undefined') return;
  const keys = getApiKeys();
  delete keys[provider];
  localStorage.setItem('ga_api_keys', JSON.stringify(keys));
}

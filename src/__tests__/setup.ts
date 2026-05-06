import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock IndexedDB
const indexedDBMock = (() => {
  let stores: Record<string, Map<string, any>> = {};
  let dbInstance: any = null;

  const createObjectStore = (name: string, options: any) => {
    if (!stores[name]) stores[name] = new Map();
    const store = stores[name];
    return {
      createIndex: () => {},
    };
  };

  return {
    open: vi.fn((name: string, version: number) => {
      const request: any = {
        onerror: null as any,
        onsuccess: null as any,
        onupgradeneeded: null as any,
        result: null as any,
        error: null as any,
      };

      // Simulate async
      setTimeout(() => {
        const db = {
          objectStoreNames: {
            contains: (n: string) => !!stores[n],
          },
          createObjectStore,
          transaction: (storeNames: string | string[], mode: string) => {
            const names = Array.isArray(storeNames) ? storeNames : [storeNames];
            const txStores: Record<string, any> = {};
            for (const n of names) {
              if (!stores[n]) stores[n] = new Map();
              txStores[n] = {
                put: (value: any) => {
                  const key = value.id || value.key || value.provider;
                  stores[n].set(key, value);
                  return { onsuccess: null, onerror: null };
                },
                get: (key: string) => {
                  const result = stores[n].get(key) || null;
                  return { onsuccess: null, onerror: null, result };
                },
                getAll: () => {
                  const result = Array.from(stores[n].values());
                  return { onsuccess: null, onerror: null, result };
                },
                delete: (key: string) => {
                  stores[n].delete(key);
                  return { onsuccess: null, onerror: null };
                },
                index: (idxName: string) => ({
                  openCursor: (range?: any) => ({
                    onsuccess: null,
                    result: null,
                  }),
                  getAll: (range?: any) => {
                    const result = Array.from(stores[n].values());
                    return { onsuccess: null, onerror: null, result };
                  },
                }),
                clear: () => {
                  stores[n].clear();
                  return { onsuccess: null, onerror: null };
                },
              };
            }
            return {
              objectStore: (name: string) => txStores[name],
              oncomplete: null as any,
              onerror: null as any,
              error: null,
            };
          },
          close: () => { dbInstance = null; },
          onclose: null as any,
          onversionchange: null as any,
        };
        dbInstance = db;
        request.result = db;

        if (version > 1 && request.onupgradeneeded) {
          request.onupgradeneeded({ target: request, oldVersion: 0, newVersion: version });
        }
        if (request.onsuccess) request.onsuccess({ target: request });
      }, 0);

      return request;
    }),
  };
})();

Object.defineProperty(globalThis, 'indexedDB', { value: indexedDBMock, writable: true });

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
  };
})();
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true });

// Mock matchMedia
Object.defineProperty(globalThis, 'matchMedia', {
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
  writable: true,
});

// Mock crypto.randomUUID
Object.defineProperty(globalThis, 'crypto', {
  value: {
    randomUUID: vi.fn(() => `${Math.random().toString(36).slice(2)}-${Date.now()}`),
  },
  writable: true,
});

// Mock ResizeObserver
globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock IntersectionObserver
globalThis.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Suppress console.warn in tests
const originalWarn = console.warn;
console.warn = (...args: any[]) => {
  if (typeof args[0] === 'string' && (args[0].includes('[DB]') || args[0].includes('[Tauri]'))) return;
  originalWarn(...args);
};

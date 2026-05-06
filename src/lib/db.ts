/**
 * Local Database Layer for GenericAgent
 * Uses IndexedDB for persistent client-side storage.
 * No server/database required — works entirely in the browser.
 */

const DB_NAME = 'genericagent-db';
const DB_VERSION = 1;

const STORES = {
  sessions: 'sessions',
  messages: 'messages',
  settings: 'settings',
  apiKeys: 'apiKeys',
  memory: 'memory',
} as const;

let dbInstance: IDBDatabase | null = null;
let openPromise: Promise<IDBDatabase> | null = null;

function openDB(): Promise<IDBDatabase> {
  if (dbInstance) return Promise.resolve(dbInstance);
  if (typeof window === 'undefined') return Promise.reject(new Error('Not in browser'));

  if (openPromise) return openPromise;

  openPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      openPromise = null; // Clear on failure so subsequent calls can retry
      reject(request.error);
    };

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // Sessions store
      if (!db.objectStoreNames.contains(STORES.sessions)) {
        const sessionStore = db.createObjectStore(STORES.sessions, { keyPath: 'id' });
        sessionStore.createIndex('date', 'date', { unique: false });
      }

      // Messages store
      if (!db.objectStoreNames.contains(STORES.messages)) {
        const msgStore = db.createObjectStore(STORES.messages, { keyPath: 'id' });
        msgStore.createIndex('sessionId', 'sessionId', { unique: false });
        msgStore.createIndex('timestamp', 'timestamp', { unique: false });
      }

      // Settings store
      if (!db.objectStoreNames.contains(STORES.settings)) {
        db.createObjectStore(STORES.settings, { keyPath: 'key' });
      }

      // API Keys store
      if (!db.objectStoreNames.contains(STORES.apiKeys)) {
        db.createObjectStore(STORES.apiKeys, { keyPath: 'provider' });
      }

      // Memory store
      if (!db.objectStoreNames.contains(STORES.memory)) {
        const memStore = db.createObjectStore(STORES.memory, { keyPath: 'id' });
        memStore.createIndex('category', 'category', { unique: false });
        memStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      openPromise = null;
      // Handle database close and version change events
      dbInstance.onclose = () => {
        dbInstance = null;
        openPromise = null;
        console.warn('[DB] IndexedDB connection closed unexpectedly');
      };
      dbInstance.onversionchange = () => {
        dbInstance?.close();
        dbInstance = null;
        openPromise = null;
        console.warn('[DB] IndexedDB version change detected, connection closed');
      };
      resolve(dbInstance);
    };
  });
  return openPromise;
}

// ============ GENERIC OPERATIONS ============

async function dbPut(storeName: string, value: any): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).put(value);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbGet<T>(storeName: string, key: string): Promise<T | undefined> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).get(key);
    request.onsuccess = () => resolve(request.result as T | undefined);
    request.onerror = () => reject(request.error);
  });
}

async function dbGetAll<T>(storeName: string): Promise<T[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).getAll();
    request.onsuccess = () => resolve(request.result as T[]);
    request.onerror = () => reject(request.error);
  });
}

async function dbDelete(storeName: string, key: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function dbClear(storeName: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ============ SESSION OPERATIONS ============

export interface DBSession {
  id: string;
  title: string;
  messageCount: number;
  date: number;
  createdAt: number;
}

export async function saveSession(session: DBSession): Promise<void> {
  return dbPut(STORES.sessions, session);
}

export async function getSessions(): Promise<DBSession[]> {
  const sessions = await dbGetAll<DBSession>(STORES.sessions);
  return sessions.sort((a, b) => b.date - a.date);
}

export async function deleteSession(id: string): Promise<void> {
  const db = await openDB();
  // Delete messages and session in a single atomic transaction
  const tx = db.transaction([STORES.messages, STORES.sessions], 'readwrite');
  const msgStore = tx.objectStore(STORES.messages);
  const sessionStore = tx.objectStore(STORES.sessions);

  // Delete all messages for this session using a cursor
  const index = msgStore.index('sessionId');
  const request = index.openCursor(IDBKeyRange.only(id));

  // Also delete the session itself within the same transaction
  sessionStore.delete(id);

  return new Promise((resolve, reject) => {
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ============ MESSAGE OPERATIONS ============

export interface DBMessage {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: number;
  model?: string;
  expressions?: string[];
}

export async function saveMessage(message: DBMessage): Promise<void> {
  return dbPut(STORES.messages, message);
}

export async function getMessagesBySession(sessionId: string): Promise<DBMessage[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.messages, 'readonly');
    const store = tx.objectStore(STORES.messages);
    const index = store.index('sessionId');
    const request = index.getAll(sessionId);
    request.onsuccess = () => {
      const messages = (request.result as DBMessage[]).sort(
        (a, b) => a.timestamp - b.timestamp
      );
      resolve(messages);
    };
    request.onerror = () => reject(request.error);
  });
}

export async function clearMessages(sessionId?: string): Promise<void> {
  if (sessionId) {
    const db = await openDB();
    const tx = db.transaction(STORES.messages, 'readwrite');
    const store = tx.objectStore(STORES.messages);
    const index = store.index('sessionId');
    const request = index.openCursor(IDBKeyRange.only(sessionId));

    return new Promise((resolve, reject) => {
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result;
        if (cursor) {
          cursor.delete();
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } else {
    await dbClear(STORES.messages);
  }
}

// ============ SETTINGS OPERATIONS ============

export async function saveSetting(key: string, value: any): Promise<void> {
  return dbPut(STORES.settings, { key, value });
}

export async function getSetting<T>(key: string): Promise<T | undefined> {
  const result = await dbGet<{ key: string; value: T }>(STORES.settings, key);
  return result?.value;
}

// ============ API KEY OPERATIONS ============

export async function saveApiKey(provider: string, keyValue: string): Promise<void> {
  return dbPut(STORES.apiKeys, { provider, key: keyValue });
}

export async function getApiKey(provider: string): Promise<string | undefined> {
  const result = await dbGet<{ provider: string; key: string }>(STORES.apiKeys, provider);
  return result?.key;
}

export async function deleteApiKey(provider: string): Promise<void> {
  return dbDelete(STORES.apiKeys, provider);
}

export async function getAllApiKeys(): Promise<Record<string, string>> {
  const keys = await dbGetAll<{ provider: string; key: string }>(STORES.apiKeys);
  const result: Record<string, string> = {};
  for (const k of keys) {
    result[k.provider] = k.key;
  }
  return result;
}

// ============ MEMORY OPERATIONS ============

export interface DBMemory {
  id: string;
  content: string;
  category: string;
  layer?: string;
  timestamp: number;
  tags?: string[];
}

export async function saveMemoryItem(item: DBMemory): Promise<void> {
  return dbPut(STORES.memory, item);
}

export async function getMemoryItems(category?: string): Promise<DBMemory[]> {
  if (category) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORES.memory, 'readonly');
      const index = tx.objectStore(STORES.memory).index('category');
      const request = index.getAll(category);
      request.onsuccess = () => resolve(request.result as DBMemory[]);
      request.onerror = () => reject(request.error);
    });
  }
  return dbGetAll<DBMemory>(STORES.memory);
}

export async function searchMemory(query: string, limit: number = 10): Promise<DBMemory[]> {
  const all = await dbGetAll<DBMemory>(STORES.memory);
  const lowerQuery = query.toLowerCase();
  return all
    .filter((item) => item.content.toLowerCase().includes(lowerQuery))
    .slice(0, limit);
}

// ============ INITIALIZATION ============

export async function initDB(): Promise<void> {
  try {
    await openDB();
    console.log('[DB] IndexedDB initialized successfully');
  } catch (err) {
    console.warn('[DB] IndexedDB initialization failed, falling back to localStorage:', err);
  }
}

// Auto-initialize on import (browser only)
if (typeof window !== 'undefined') {
  initDB().catch((err) => {
    console.warn('[DB] Auto-initialization failed:', err);
  });
}

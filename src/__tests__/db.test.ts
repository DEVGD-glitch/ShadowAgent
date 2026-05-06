import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  initDB,
  saveSession,
  getSessions,
  deleteSession,
  saveMessage,
  getMessagesBySession,
  clearMessages,
  saveSetting,
  getSetting,
  saveApiKey,
  getApiKey,
  deleteApiKey,
  getAllApiKeys,
  saveMemoryItem,
  getMemoryItems,
  searchMemory,
  type DBSession,
  type DBMessage,
  type DBMemory,
} from '@/lib/db';

describe('db.ts', () => {
  beforeEach(async () => {
    // Re-initialize DB for each test
    try {
      await initDB();
    } catch {
      // OK if already initialized
    }
  });

  // ============ Session Operations ============
  describe('session operations', () => {
    const testSession: DBSession = {
      id: 'session-1',
      title: 'Test Session',
      messageCount: 0,
      date: Date.now(),
      createdAt: Date.now(),
    };

    it('saves and retrieves a session', async () => {
      await saveSession(testSession);
      const sessions = await getSessions();
      expect(sessions).toHaveLength(1);
      expect(sessions[0].id).toBe('session-1');
      expect(sessions[0].title).toBe('Test Session');
    });

    it('retrieves sessions sorted by date (newest first)', async () => {
      await saveSession({ id: 's1', title: 'Old', messageCount: 0, date: 1000, createdAt: 1000 });
      await saveSession({ id: 's2', title: 'New', messageCount: 0, date: 2000, createdAt: 2000 });
      const sessions = await getSessions();
      expect(sessions[0].title).toBe('New');
      expect(sessions[1].title).toBe('Old');
    });

    it('deletes a session and its messages', async () => {
      await saveSession(testSession);
      await saveMessage({
        id: 'msg-1',
        sessionId: 'session-1',
        role: 'user',
        content: 'Hello',
        timestamp: Date.now(),
      });
      await deleteSession('session-1');
      const sessions = await getSessions();
      expect(sessions).toHaveLength(0);
    });

    it('handles deleting non-existent session', async () => {
      await expect(deleteSession('nonexistent')).resolves.not.toThrow();
    });
  });

  // ============ Message Operations ============
  describe('message operations', () => {
    const testSession: DBSession = {
      id: 'session-msg',
      title: 'Message Test',
      messageCount: 0,
      date: Date.now(),
      createdAt: Date.now(),
    };

    beforeEach(async () => {
      await saveSession(testSession);
    });

    it('saves and retrieves messages by session', async () => {
      await saveMessage({
        id: 'msg-1',
        sessionId: 'session-msg',
        role: 'user',
        content: 'Hello!',
        timestamp: 1000,
      });
      await saveMessage({
        id: 'msg-2',
        sessionId: 'session-msg',
        role: 'assistant',
        content: 'Hi!',
        timestamp: 2000,
      });
      const messages = await getMessagesBySession('session-msg');
      expect(messages).toHaveLength(2);
    });

    it('retrieves messages sorted by timestamp', async () => {
      await saveMessage({
        id: 'msg-b',
        sessionId: 'session-msg',
        role: 'assistant',
        content: 'Hi!',
        timestamp: 2000,
      });
      await saveMessage({
        id: 'msg-a',
        sessionId: 'session-msg',
        role: 'user',
        content: 'Hello!',
        timestamp: 1000,
      });
      const messages = await getMessagesBySession('session-msg');
      expect(messages[0].content).toBe('Hello!');
      expect(messages[1].content).toBe('Hi!');
    });

    it('returns empty array for session with no messages', async () => {
      const messages = await getMessagesBySession('empty-session');
      expect(messages).toEqual([]);
    });

    it('clears messages for a specific session', async () => {
      await saveMessage({
        id: 'msg-1',
        sessionId: 'session-msg',
        role: 'user',
        content: 'Hello',
        timestamp: Date.now(),
      });
      await clearMessages('session-msg');
      const messages = await getMessagesBySession('session-msg');
      expect(messages).toEqual([]);
    });

    it('clears all messages when no session specified', async () => {
      await saveMessage({
        id: 'msg-1',
        sessionId: 'session-msg',
        role: 'user',
        content: 'Hello',
        timestamp: Date.now(),
      });
      await clearMessages();
      const messages = await getMessagesBySession('session-msg');
      expect(messages).toEqual([]);
    });

    it('handles messages with expressions', async () => {
      await saveMessage({
        id: 'msg-expr',
        sessionId: 'session-msg',
        role: 'assistant',
        content: '[face:happy] Hello!',
        timestamp: Date.now(),
        expressions: ['happy'],
      });
      const messages = await getMessagesBySession('session-msg');
      expect(messages[0].expressions).toEqual(['happy']);
    });
  });

  // ============ Settings Operations ============
  describe('settings operations', () => {
    it('saves and retrieves a setting', async () => {
      await saveSetting('test-key', { value: 'test-value' });
      const result = await getSetting<{ value: string }>('test-key');
      expect(result?.value).toBe('test-value');
    });

    it('returns undefined for non-existent setting', async () => {
      const result = await getSetting('nonexistent');
      expect(result).toBeUndefined();
    });

    it('overwrites existing setting', async () => {
      await saveSetting('overwrite-key', 'v1');
      await saveSetting('overwrite-key', 'v2');
      const result = await getSetting<string>('overwrite-key');
      expect(result).toBe('v2');
    });
  });

  // ============ API Key Operations ============
  describe('API key operations', () => {
    it('saves and retrieves an API key', async () => {
      await saveApiKey('openai', 'sk-test-key');
      const key = await getApiKey('openai');
      expect(key).toBe('sk-test-key');
    });

    it('returns undefined for non-existent key', async () => {
      const key = await getApiKey('nonexistent');
      expect(key).toBeUndefined();
    });

    it('deletes an API key', async () => {
      await saveApiKey('openai', 'sk-test');
      await deleteApiKey('openai');
      const key = await getApiKey('openai');
      expect(key).toBeUndefined();
    });

    it('gets all API keys', async () => {
      await saveApiKey('openai', 'sk-oai');
      await saveApiKey('anthropic', 'sk-ant');
      const keys = await getAllApiKeys();
      expect(keys.openai).toBe('sk-oai');
      expect(keys.anthropic).toBe('sk-ant');
    });

    it('overwrites existing key', async () => {
      await saveApiKey('openai', 'old-key');
      await saveApiKey('openai', 'new-key');
      const key = await getApiKey('openai');
      expect(key).toBe('new-key');
    });
  });

  // ============ Memory Operations ============
  describe('memory operations', () => {
    const testMemory: DBMemory = {
      id: 'mem-1',
      content: 'Test memory content about cats',
      category: 'facts',
      layer: 'L2',
      timestamp: Date.now(),
      tags: ['animals', 'cats'],
    };

    it('saves and retrieves memory items', async () => {
      await saveMemoryItem(testMemory);
      const items = await getMemoryItems();
      expect(items.length).toBeGreaterThanOrEqual(1);
    });

    it('retrieves memory items by category', async () => {
      await saveMemoryItem(testMemory);
      await saveMemoryItem({
        id: 'mem-2',
        content: 'Code pattern',
        category: 'code',
        timestamp: Date.now(),
      });
      const items = await getMemoryItems('facts');
      expect(items.every(i => i.category === 'facts')).toBe(true);
    });

    it('searches memory by content', async () => {
      await saveMemoryItem(testMemory);
      const results = await searchMemory('cats');
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].content).toContain('cats');
    });

    it('returns empty for no search matches', async () => {
      const results = await searchMemory('zzzznonexistent');
      expect(results).toEqual([]);
    });

    it('respects search limit', async () => {
      for (let i = 0; i < 20; i++) {
        await saveMemoryItem({
          id: `mem-batch-${i}`,
          content: `Memory item ${i} about testing`,
          category: 'test',
          timestamp: Date.now(),
        });
      }
      const results = await searchMemory('testing', 5);
      expect(results.length).toBeLessThanOrEqual(5);
    });
  });

  // ============ initDB ============
  describe('initDB', () => {
    it('initializes without error', async () => {
      await expect(initDB()).resolves.not.toThrow();
    });
  });
});

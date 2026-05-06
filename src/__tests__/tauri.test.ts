import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('tauri.ts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    delete (window as any).__TAURI_INTERNALS__;
  });

  describe('isTauri', () => {
    it('returns false in browser (no __TAURI_INTERNALS__)', async () => {
      const { isTauri } = await import('@/lib/tauri');
      expect(isTauri()).toBe(false);
    });
  });

  describe('window operations', () => {
    it('minimizeWindow does not throw when not in Tauri', async () => {
      const { minimizeWindow } = await import('@/lib/tauri');
      expect(() => minimizeWindow()).not.toThrow();
    });

    it('closeWindow does not throw when not in Tauri', async () => {
      const { closeWindow } = await import('@/lib/tauri');
      expect(() => closeWindow()).not.toThrow();
    });
  });

  describe('module exports', () => {
    it('exports isTauri function', async () => {
      const mod = await import('@/lib/tauri');
      expect(typeof mod.isTauri).toBe('function');
    });

    it('exports window operation functions', async () => {
      const mod = await import('@/lib/tauri');
      expect(typeof mod.minimizeWindow).toBe('function');
      expect(typeof mod.toggleMaximize).toBe('function');
      expect(typeof mod.closeWindow).toBe('function');
    });
  });
});

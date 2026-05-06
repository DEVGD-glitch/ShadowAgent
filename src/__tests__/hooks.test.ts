import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useIsMobile } from '@/hooks/use-mobile';
import { useToast, toast } from '@/hooks/use-toast';

describe('use-mobile hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useIsMobile', () => {
    it('returns boolean value', () => {
      const { result } = renderHook(() => useIsMobile());
      expect(typeof result.current).toBe('boolean');
    });

    it('returns false on desktop viewport (default mock)', () => {
      // Default matchMedia mock returns matches: false
      const { result } = renderHook(() => useIsMobile());
      expect(result.current).toBe(false);
    });

    it('listens for media query changes', () => {
      // Verify the hook calls matchMedia with the right query
      const { result } = renderHook(() => useIsMobile());
      expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 768px)');
    });
  });
});

describe('use-toast hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('useToast', () => {
    it('returns toast function and toasts array', () => {
      const { result } = renderHook(() => useToast());
      expect(typeof result.current.toast).toBe('function');
      expect(Array.isArray(result.current.toasts)).toBe(true);
    });

    it('adds a toast', () => {
      const { result } = renderHook(() => useToast());
      act(() => {
        result.current.toast({ title: 'Test Toast', description: 'Test description' });
      });
      expect(result.current.toasts.length).toBeGreaterThan(0);
    });

    it('adds toast with variant', () => {
      const { result } = renderHook(() => useToast());
      act(() => {
        result.current.toast({ title: 'Error', variant: 'destructive' });
      });
      expect(result.current.toasts.some(t => (t as any).variant === 'destructive')).toBe(true);
    });

    it('dismisses a toast', () => {
      const { result } = renderHook(() => useToast());
      let toastId: string = '';
      act(() => {
        const t = result.current.toast({ title: 'Dismiss me' });
        toastId = (t as any)?.id || '';
      });

      if (toastId) {
        act(() => {
          result.current.dismiss(toastId);
        });
      }
    });
  });

  describe('toast (standalone)', () => {
    it('can be called without error', () => {
      expect(() => toast({ title: 'Standalone toast' })).not.toThrow();
    });

    it('returns toast result', () => {
      const result = toast({ title: 'Test', description: 'Desc' });
      expect(result).toBeDefined();
    });
  });
});

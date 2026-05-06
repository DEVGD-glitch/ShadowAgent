import { describe, it, expect } from 'vitest';
import { cn } from '@/lib/utils';

describe('utils', () => {
  describe('cn (className merger)', () => {
    it('merges class names', () => {
      expect(cn('foo', 'bar')).toBe('foo bar');
    });

    it('handles conditional classes', () => {
      expect(cn('base', false && 'hidden', 'visible')).toBe('base visible');
    });

    it('handles undefined and null values', () => {
      expect(cn('base', undefined, null, 'end')).toBe('base end');
    });

    it('merges tailwind conflict classes correctly', () => {
      // tailwind-merge should resolve conflicts
      expect(cn('px-2', 'px-4')).toBe('px-4');
    });

    it('handles empty input', () => {
      expect(cn()).toBe('');
    });

    it('handles arrays of classes', () => {
      expect(cn(['foo', 'bar'], 'baz')).toBe('foo bar baz');
    });

    it('handles object-style classes', () => {
      expect(cn({ active: true, disabled: false })).toBe('active');
    });

    it('resolves responsive tailwind conflicts', () => {
      expect(cn('sm:px-2', 'sm:px-4')).toBe('sm:px-4');
    });
  });
});

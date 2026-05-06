import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

// ============ Component Exports ============
describe('Component exports', () => {
  it('ChatPage is exported', async () => {
    const mod = await import('@/components/chat/chat-page');
    expect(mod.ChatPage).toBeDefined();
    expect(typeof mod.ChatPage).toBe('function');
  });

  it('DashboardPage is exported', async () => {
    const mod = await import('@/components/dashboard/dashboard-page');
    expect(mod.DashboardPage).toBeDefined();
  });

  it('SettingsPage is exported', async () => {
    const mod = await import('@/components/settings/settings-page');
    expect(mod.SettingsPage).toBeDefined();
  });

  it('MemoryPage is exported', async () => {
    const mod = await import('@/components/memory/memory-page');
    expect(mod.MemoryPage).toBeDefined();
  });

  it('MessageItem is exported', async () => {
    const mod = await import('@/components/chat/message-item');
    expect(mod.MessageItem).toBeDefined();
  });

  it('MessageList is exported', async () => {
    const mod = await import('@/components/chat/message-list');
    expect(mod.MessageList).toBeDefined();
  });

  it('ChatInput is exported', async () => {
    const mod = await import('@/components/chat/chat-input');
    expect(mod.ChatInput).toBeDefined();
  });

  it('StreamingCursor is exported', async () => {
    const mod = await import('@/components/chat/streaming-cursor');
    expect(mod.StreamingCursor).toBeDefined();
  });

  it('ModelList is exported', async () => {
    const mod = await import('@/components/settings/model-list');
    expect(mod.ModelList).toBeDefined();
  });

  it('HealthDashboard is exported', async () => {
    const mod = await import('@/components/settings/health-dashboard');
    expect(mod.HealthDashboard).toBeDefined();
  });

  it('MetricCard is exported', async () => {
    const mod = await import('@/components/dashboard/metric-card');
    expect(mod.MetricCard).toBeDefined();
  });

  it('StatusOrb is exported', async () => {
    const mod = await import('@/components/dashboard/status-orb');
    expect(mod.StatusOrb).toBeDefined();
  });

  it('HistoryPage is exported', async () => {
    const mod = await import('@/components/history/history-page');
    expect(mod.HistoryPage).toBeDefined();
  });

  it('OnboardingWizard is exported', async () => {
    const mod = await import('@/components/onboarding/onboarding-wizard');
    expect(mod.OnboardingWizard).toBeDefined();
  });

  it('CommandPalette is exported', async () => {
    const mod = await import('@/components/command-palette');
    expect(mod.CommandPalette).toBeDefined();
  });
});

// ============ CommandPalette Rendering ============
describe('CommandPalette', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('renders when commandPaletteOpen is true', async () => {
    // Mock settings store to return open state
    vi.mock('@/stores/settings-store', () => ({
      useSettingsStore: (selector: any) => {
        const state = {
          commandPaletteOpen: true,
          setCommandPaletteOpen: vi.fn(),
          theme: 'dark' as const,
          setTheme: vi.fn(),
          autonomousMode: false,
          setAutonomousMode: vi.fn(),
        };
        return selector ? selector(state) : state;
      },
    }));

    vi.mock('@/stores/agent-store', () => ({
      useAgentStore: (selector: any) => {
        const state = { clearMessages: vi.fn() };
        return selector ? selector(state) : state;
      },
    }));

    const { CommandPalette } = await import('@/components/command-palette');
    const onNavigate = vi.fn();
    render(React.createElement(CommandPalette, { onNavigate }));
    expect(screen.getByPlaceholderText('Type a command...')).toBeTruthy();
  });

  it('shows command items when open', async () => {
    vi.mock('@/stores/settings-store', () => ({
      useSettingsStore: (selector: any) => {
        const state = {
          commandPaletteOpen: true,
          setCommandPaletteOpen: vi.fn(),
          theme: 'dark' as const,
          setTheme: vi.fn(),
          autonomousMode: false,
          setAutonomousMode: vi.fn(),
        };
        return selector ? selector(state) : state;
      },
    }));

    vi.mock('@/stores/agent-store', () => ({
      useAgentStore: (selector: any) => {
        const state = { clearMessages: vi.fn() };
        return selector ? selector(state) : state;
      },
    }));

    const { CommandPalette } = await import('@/components/command-palette');
    const onNavigate = vi.fn();
    render(React.createElement(CommandPalette, { onNavigate }));
    expect(screen.getByText('Go to Chat')).toBeTruthy();
  });
});

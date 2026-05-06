'use client';

import { useState, useEffect, lazy, Suspense, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChatPage } from '@/components/chat/chat-page';
import { useSettingsStore } from '@/stores/settings-store';
import { useAgentStore } from '@/stores/agent-store';
import { connectToBackend, disconnectFromBackend } from '@/lib/backend';
import {
  MessageSquare,
  LayoutDashboard,
  Settings,
  Brain,
  Sparkles,
  Loader2,
  HelpCircle,
  Keyboard,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { CommandPalette } from '@/components/command-palette';
import { QuickTour } from '@/components/onboarding/quick-tour';
import { KeyboardShortcutsModal } from '@/components/keyboard-shortcuts-modal';

type PageId = 'chat' | 'dashboard' | 'memory' | 'settings' | 'history' | 'help';

// Lazy load heavy components (Three.js, etc.)
// These modules use named exports, so we must map them to default for React.lazy()
const DashboardPage = lazy(() =>
  import('@/components/dashboard/dashboard-page').then((m) => ({ default: m.DashboardPage }))
);
const SettingsPage = lazy(() =>
  import('@/components/settings/settings-page').then((m) => ({ default: m.SettingsPage }))
);
const MemoryPage = lazy(() =>
  import('@/components/memory/memory-page').then((m) => ({ default: m.MemoryPage }))
);
const HistoryPage = lazy(() =>
  import('@/components/history/history-page').then((m) => ({ default: m.HistoryPage }))
);
const HelpPage = lazy(() =>
  import('@/components/help/help-page').then((m) => ({ default: m.HelpPage }))
);

const PAGE_COMPONENTS: Record<PageId, React.ComponentType> = {
  chat: ChatPage,
  dashboard: DashboardPage,
  settings: SettingsPage,
  memory: MemoryPage,
  history: HistoryPage,
  help: HelpPage,
};

const NAV_ITEMS: { id: PageId; icon: React.ElementType; label: string }[] = [
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
  { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { id: 'memory', icon: Brain, label: 'Memory' },
  { id: 'settings', icon: Settings, label: 'Settings' },
];

function PageLoader() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-white/30">
        <Loader2 className="w-8 h-8 animate-spin" />
        <span className="text-sm">Loading...</span>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [activePage, setActivePage] = useState<PageId>('chat');
  const { theme, backendConfig, setCommandPaletteOpen, showOnboarding, setShowOnboarding } = useSettingsStore();
  const { setModels, setBackendConnected } = useAgentStore();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showQuickTour, setShowQuickTour] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      const root = document.documentElement;
      if (theme === 'dark' || theme === 'catppuccin' || theme === 'glass') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    }
  }, [theme]);

  // Show Quick Tour on first visit
  useEffect(() => {
    if (showOnboarding) {
      setShowQuickTour(true);
    }
  }, [showOnboarding]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl + / or ? to show shortcuts
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        setShowShortcuts(true);
      }
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          setShowShortcuts(true);
        }
      }
      // Ctrl + 1-4 for navigation
      if ((e.ctrlKey || e.metaKey) && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault();
        const pages: PageId[] = ['chat', 'dashboard', 'memory', 'settings'];
        const index = parseInt(e.key) - 1;
        if (pages[index]) setActivePage(pages[index]);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleConnect = useCallback(() => {
    if (!backendConfig.autoConnect) return;
    connectToBackend();
    return () => {
      disconnectFromBackend();
    };
  }, [backendConfig.autoConnect]);

  useEffect(() => {
    handleConnect();
  }, [handleConnect]);

  const PageComponent = PAGE_COMPONENTS[activePage];

  const handleNavigate = useCallback((page: PageId) => {
    setActivePage(page);
  }, []);

  return (
    <div className="h-screen w-screen flex bg-[oklch(0.06_0.01_280)] text-white overflow-hidden">
      <CommandPalette onNavigate={handleNavigate} />
      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarCollapsed ? 60 : 200 }}
        transition={{ duration: 0.2 }}
        className="h-full flex flex-col border-r border-white/[0.06] bg-white/[0.02]"
      >
        <div className="flex items-center gap-2 px-4 py-4 border-b border-white/[0.06]">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          {!sidebarCollapsed && (
            <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="font-semibold text-sm whitespace-nowrap">
              Shadow Agent
            </motion.span>
          )}
        </div>

        <nav className="flex-1 py-2 px-2 space-y-1">
          {NAV_ITEMS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => setActivePage(id)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                activePage === id
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/20'
                  : 'text-white/50 hover:text-white/70 hover:bg-white/5'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {!sidebarCollapsed && <span className="whitespace-nowrap">{label}</span>}
            </button>
          ))}
        </nav>

        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="p-3 text-white/30 hover:text-white/60 transition-colors border-t border-white/[0.06]"
        >
          <svg className={cn('w-4 h-4 transition-transform', sidebarCollapsed && 'rotate-180')} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </motion.aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 flex items-center justify-between px-4 border-b border-white/[0.06] bg-white/[0.02]">
          <h1 className="text-sm font-medium text-white/70 capitalize">{activePage}</h1>
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="px-3 py-1 text-xs text-white/40 bg-white/5 rounded-md border border-white/10 hover:bg-white/10 transition-colors"
          >
            ⌘K
          </button>
        </header>

        <main className="flex-1 min-h-0 relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={activePage}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              <Suspense fallback={<PageLoader />}>
                <PageComponent />
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  LayoutDashboard,
  History,
  Brain,
  Settings,
  Sun,
  Moon,
  Plus,
  Trash2,
  Power,
  Search,
} from 'lucide-react';
import { useSettingsStore, type ThemeMode } from '@/stores/settings-store';
import { useAgentStore } from '@/stores/agent-store';
import { cn } from '@/lib/utils';

// PageId is the same type used in page.tsx for navigation
type PageId = 'chat' | 'dashboard' | 'memory' | 'settings' | 'history';

interface CommandPaletteProps {
  onNavigate: (page: PageId) => void;
}

interface CommandItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  group: string;
  action: () => void;
  shortcut?: string;
}

export function CommandPalette({ onNavigate }: CommandPaletteProps) {
  const { commandPaletteOpen, setCommandPaletteOpen, theme, setTheme, autonomousMode, setAutonomousMode } = useSettingsStore();
  const { clearMessages } = useAgentStore();
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const commands: CommandItem[] = useMemo(() => [
    {
      id: 'nav-chat',
      label: 'Go to Chat',
      icon: <MessageSquare className="h-4 w-4" />,
      group: 'Navigation',
      action: () => { onNavigate('chat'); setCommandPaletteOpen(false); },
      shortcut: '1',
    },
    {
      id: 'nav-dashboard',
      label: 'Go to Dashboard',
      icon: <LayoutDashboard className="h-4 w-4" />,
      group: 'Navigation',
      action: () => { onNavigate('dashboard'); setCommandPaletteOpen(false); },
      shortcut: '2',
    },
    {
      id: 'nav-history',
      label: 'Go to History',
      icon: <History className="h-4 w-4" />,
      group: 'Navigation',
      action: () => { onNavigate('history'); setCommandPaletteOpen(false); },
      shortcut: '3',
    },
    {
      id: 'nav-memory',
      label: 'Go to Memory & Skills',
      icon: <Brain className="h-4 w-4" />,
      group: 'Navigation',
      action: () => { onNavigate('memory'); setCommandPaletteOpen(false); },
      shortcut: '4',
    },
    {
      id: 'nav-settings',
      label: 'Go to Settings',
      icon: <Settings className="h-4 w-4" />,
      group: 'Navigation',
      action: () => { onNavigate('settings'); setCommandPaletteOpen(false); },
      shortcut: '5',
    },
    {
      id: 'new-chat',
      label: 'New Conversation',
      icon: <Plus className="h-4 w-4" />,
      group: 'Actions',
      action: () => { clearMessages(); onNavigate('chat'); setCommandPaletteOpen(false); },
    },
    {
      id: 'clear-chat',
      label: 'Clear Current Chat',
      icon: <Trash2 className="h-4 w-4" />,
      group: 'Actions',
      action: () => { clearMessages(); setCommandPaletteOpen(false); },
    },
    {
      id: 'toggle-theme',
      label: `Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Theme`,
      icon: theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
      group: 'Actions',
      action: () => { setTheme(theme === 'dark' ? 'light' : 'dark'); setCommandPaletteOpen(false); },
    },
    {
      id: 'toggle-autonomous',
      label: `Toggle Autonomous Mode (${autonomousMode ? 'On' : 'Off'})`,
      icon: <Power className="h-4 w-4" />,
      group: 'Actions',
      action: () => { setAutonomousMode(!autonomousMode); setCommandPaletteOpen(false); },
    },
  ], [onNavigate, setCommandPaletteOpen, theme, setTheme, autonomousMode, setAutonomousMode, clearMessages]);

  const filteredCommands = useMemo(() =>
    commands.filter((cmd) =>
      cmd.label.toLowerCase().includes(search.toLowerCase())
    ),
    [commands, search]
  );

  // Reset selected index when filtered results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  // Keyboard shortcut to open/close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      if (e.key === 'Escape') {
        setCommandPaletteOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  // Keyboard navigation within the palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
      filteredCommands[selectedIndex].action();
    }
  };

  const groups = useMemo(() => [...new Set(filteredCommands.map((c) => c.group))], [filteredCommands]);

  return (
    <AnimatePresence>
      {commandPaletteOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
            onClick={() => setCommandPaletteOpen(false)}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.15 }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-full max-w-lg"
          >
            <div className="bg-[oklch(0.1_0.015_280)] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
                <Search className="h-4 w-4 text-white/30 shrink-0" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a command..."
                  className="flex-1 bg-transparent text-sm text-white/80 placeholder:text-white/20 outline-none"
                  autoFocus
                />
                <kbd className="text-[10px] font-mono text-white/20 bg-white/[0.04] px-1.5 py-0.5 rounded">
                  ESC
                </kbd>
              </div>

              <div className="max-h-72 overflow-y-auto py-2">
                {groups.map((group) => (
                  <div key={group}>
                    <p className="px-4 py-1 text-[10px] font-semibold text-white/20 uppercase tracking-wider">
                      {group}
                    </p>
                    {filteredCommands
                      .filter((c) => c.group === group)
                      .map((cmd, idx) => {
                        const globalIdx = filteredCommands.indexOf(cmd);
                        return (
                          <motion.button
                            key={cmd.id}
                            onClick={cmd.action}
                            className={cn(
                              'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                              globalIdx === selectedIndex
                                ? 'text-white/90 bg-white/[0.06]'
                                : 'text-white/60 hover:text-white/90 hover:bg-white/[0.04]'
                            )}
                          >
                            <span className="text-white/30">{cmd.icon}</span>
                            <span className="flex-1 text-left">{cmd.label}</span>
                            {cmd.shortcut && (
                              <kbd className="text-[10px] font-mono text-white/15 bg-white/[0.03] px-1.5 py-0.5 rounded">
                                ⌘{cmd.shortcut}
                              </kbd>
                            )}
                          </motion.button>
                        );
                      })}
                  </div>
                ))}

                {filteredCommands.length === 0 && (
                  <p className="text-center text-xs text-white/20 py-6">
                    No commands found
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

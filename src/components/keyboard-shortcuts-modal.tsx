'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { X, Keyboard } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const SHORTCUTS = [
  {
    category: 'General',
    items: [
      { key: 'Ctrl + K', action: 'Open command palette' },
      { key: 'Ctrl + /', action: 'Show this shortcuts menu' },
      { key: 'Escape', action: 'Close modal / Stop generation' },
    ],
  },
  {
    category: 'Chat',
    items: [
      { key: 'Ctrl + Enter', action: 'Send message' },
      { key: 'Ctrl + N', action: 'New conversation' },
      { key: 'Ctrl + Shift + O', action: 'Open history' },
    ],
  },
  {
    category: 'Navigation',
    items: [
      { key: 'Ctrl + 1', action: 'Go to Chat' },
      { key: 'Ctrl + 2', action: 'Go to Dashboard' },
      { key: 'Ctrl + 3', action: 'Go to Memory' },
      { key: 'Ctrl + ,', action: 'Go to Settings' },
    ],
  },
  {
    category: 'Voice',
    items: [
      { key: 'Ctrl + M', action: 'Toggle voice input' },
      { key: 'Ctrl + Shift + V', action: 'Voice mode (hold to speak)' },
    ],
  },
];

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl mx-4"
          >
            <Card className="bg-gradient-to-br from-[#1a1a2e] to-[#16213e] border-white/10">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-lg font-semibold text-white">
                  <Keyboard className="h-5 w-5 text-purple-400" />
                  Keyboard Shortcuts
                </CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="text-white/40 hover:text-white hover:bg-white/5"
                >
                  <X className="h-5 w-5" />
                </Button>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-2 gap-6">
                  {SHORTCUTS.map((section) => (
                    <div key={section.category}>
                      <h3 className="text-white/40 text-xs font-medium uppercase tracking-wider mb-3">
                        {section.category}
                      </h3>
                      <div className="space-y-2">
                        {section.items.map((shortcut) => (
                          <div
                            key={shortcut.key}
                            className="flex items-center justify-between py-1.5 px-2 rounded-lg bg-white/[0.03]"
                          >
                            <span className="text-white/60 text-sm">{shortcut.action}</span>
                            <kbd className="px-2 py-1 rounded bg-white/[0.06] text-white/80 text-xs font-mono">
                              {shortcut.key}
                            </kbd>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-white/30 text-xs text-center mt-6">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white/50">?</kbd> anytime to show this menu
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

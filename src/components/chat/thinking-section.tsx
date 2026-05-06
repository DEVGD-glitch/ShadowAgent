'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Brain, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ThinkingSectionProps {
  content: string;
  duration?: number;
  defaultCollapsed?: boolean;
}

export function ThinkingSection({ content, duration, defaultCollapsed = true }: ThinkingSectionProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div className="my-2">
      <motion.button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 text-xs text-white/40 hover:text-white/60 transition-colors group"
        whileHover={{ x: 2 }}
      >
        <motion.div
          animate={{ rotate: collapsed ? 0 : 90 }}
          transition={{ duration: 0.15 }}
        >
          <ChevronRight className="h-3 w-3" />
        </motion.div>
        <Brain className="h-3 w-3 text-purple-400/60" />
        <span className="font-medium">Thinking</span>
        {duration && (
          <span className="flex items-center gap-1 text-white/25">
            <Clock className="h-2.5 w-2.5" />
            {duration}ms
          </span>
        )}
      </motion.button>
      <AnimatePresence>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-1.5 ml-5 pl-3 border-l-2 border-purple-500/20 text-xs text-white/30 leading-relaxed">
              {content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

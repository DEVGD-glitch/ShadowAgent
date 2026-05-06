'use client';

import { motion } from 'framer-motion';
import { Minus, Square, X } from 'lucide-react';
import { isTauri, minimizeWindow, toggleMaximize, closeWindow } from '@/lib/tauri';
import { useState, useEffect } from 'react';

/**
 * Custom title bar for Tauri desktop mode.
 * Only renders when running inside Tauri; hidden in browser mode.
 */
export function TauriTitleBar() {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    setIsDesktop(isTauri());
  }, []);

  if (!isDesktop) return null;

  return (
    <div
      className="fixed top-0 left-0 right-0 h-9 z-[9999] flex items-center justify-between bg-[oklch(0.06_0.01_280)]/95 backdrop-blur-xl border-b border-white/[0.04]"
      data-tauri-drag-region
    >
      {/* App title / drag region */}
      <div className="flex-1 flex items-center px-4" data-tauri-drag-region>
        <span className="text-[11px] font-medium text-white/30 select-none">
          GenericAgent
        </span>
      </div>

      {/* Window controls */}
      <div className="flex items-center h-full">
        <motion.button
          onClick={minimizeWindow}
          className="h-full px-3 flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <Minus className="h-3.5 w-3.5" />
        </motion.button>
        <motion.button
          onClick={toggleMaximize}
          className="h-full px-3 flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <Square className="h-3 w-3" />
        </motion.button>
        <motion.button
          onClick={closeWindow}
          className="h-full px-3 flex items-center justify-center text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <X className="h-3.5 w-3.5" />
        </motion.button>
      </div>
    </div>
  );
}

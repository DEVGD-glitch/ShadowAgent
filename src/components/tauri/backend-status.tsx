'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Server, Wifi, WifiOff, Loader2, RotateCcw } from 'lucide-react';
import { useAgentStore } from '@/stores/agent-store';
import { isTauri, startBackend, checkBackendHealthTauri } from '@/lib/tauri';
import { useState, useEffect, useCallback } from 'react';

/**
 * Shows backend sidecar status in desktop mode.
 * Provides a reconnect button if the backend crashes.
 */
export function TauriBackendStatus() {
  const { backendConnected } = useAgentStore();
  const [isDesktop, setIsDesktop] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [hasCrashed, setHasCrashed] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    setIsDesktop(isTauri());
  }, []);

  const MAX_RETRIES = 3;

  const handleRestart = useCallback(async () => {
    setRestarting(true);
    setHasCrashed(false);
    try {
      await startBackend();
      // Wait a bit then check health
      await new Promise((r) => setTimeout(r, 3000));
      const healthy = await checkBackendHealthTauri();
      if (healthy) {
        setRetryCount(0);
        // Will auto-update via backend.ts health polling
      }
    } catch (e) {
      console.error('Failed to restart backend:', e);
    } finally {
      setRestarting(false);
    }
  }, []);

  // Listen for backend crash events
  useEffect(() => {
    if (!isDesktop) return;

    const handleCrash = () => {
      console.warn('Backend crashed event received');
      setHasCrashed(true);
    };

    window.addEventListener('backend-crashed', handleCrash);
    return () => window.removeEventListener('backend-crashed', handleCrash);
  }, [isDesktop]);

  // Auto-reconnect after crash (max 3 attempts)
  useEffect(() => {
    if (!hasCrashed || !isDesktop) return;
    if (retryCount >= MAX_RETRIES) return;

    const timer = setTimeout(() => {
      console.log(`[BackendStatus] Auto-reconnecting after crash (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
      setRetryCount((prev) => prev + 1);
      handleRestart();
    }, 5000);

    return () => clearTimeout(timer);
  }, [hasCrashed, isDesktop, handleRestart, retryCount]);

  if (!isDesktop) return null;

  // Don't show banner when connected (and not crashed)
  if (backendConnected === 'connected' && !hasCrashed) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        className="px-4 overflow-hidden"
      >
        <div className="flex items-center justify-between px-4 py-2 rounded-xl bg-yellow-500/10 border border-yellow-500/20 my-1">
          <div className="flex items-center gap-2 text-sm text-yellow-300">
            {backendConnected === 'connecting' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Connecting to backend...</span>
              </>
            ) : hasCrashed ? (
              <>
                <WifiOff className="h-4 w-4" />
                <span>Backend crashed — {retryCount >= MAX_RETRIES ? 'max retries reached' : `auto-reconnecting (${retryCount}/${MAX_RETRIES})...`}</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4" />
                <span>Backend disconnected</span>
              </>
            )}
          </div>
          <motion.button
            onClick={handleRestart}
            disabled={restarting}
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-yellow-500/20 text-yellow-300 text-xs hover:bg-yellow-500/30 transition-colors disabled:opacity-50"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {restarting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RotateCcw className="h-3 w-3" />
            )}
            {restarting ? 'Restarting...' : 'Restart Backend'}
          </motion.button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

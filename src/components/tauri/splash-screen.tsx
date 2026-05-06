'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { isTauri, initializeTauriApp, startBackend, checkBackendHealthTauri } from '@/lib/tauri';

type SplashState = 'loading' | 'ready' | 'error' | 'reconnecting';

/**
 * TauriSplashScreen — Shows a loading splash while the backend sidecar starts.
 * Only visible when running in Tauri desktop mode.
 */
export function TauriSplashScreen() {
  const [show, setShow] = useState(false);
  const [state, setState] = useState<SplashState>('loading');
  const [progress, setProgress] = useState(0);
  const [isTauriMode, setIsTauriMode] = useState(false);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const tauriDetected = isTauri();
    setIsTauriMode(tauriDetected);

    if (tauriDetected) {
      setShow(true);

      progressIntervalRef.current = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + Math.random() * 8;
        });
      }, 300);

      initializeTauriApp().then(({ backendStarted }) => {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setProgress(backendStarted ? 100 : 0);
        setState(backendStarted ? 'ready' : 'error');

        setTimeout(() => {
          setShow(false);
        }, 500);
      }).catch((err) => {
        console.error('Tauri init failed:', err);
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setState('error');
        setProgress(0);
      });
    }

    // Cleanup interval on unmount
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, []);

  if (!isTauriMode) return null;

  const statusMessages: Record<SplashState, string> = {
    loading: 'Starting GenericAgent backend...',
    ready: 'Backend ready!',
    error: 'Failed to start backend',
    reconnecting: 'Reconnecting to backend...',
  };

  const handleRetry = useCallback(async () => {
    setState('reconnecting');
    setProgress(0);
    const started = await startBackend();
    if (started) {
      // Wait for health check
      for (let i = 0; i < 10; i++) {
        const healthy = await checkBackendHealthTauri();
        if (healthy) {
          setState('ready');
          setProgress(100);
          setTimeout(() => setShow(false), 500);
          return;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    setState('error');
  }, [startBackend, checkBackendHealthTauri]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-[oklch(0.06_0.01_280)]"
        >
          <div className="flex flex-col items-center gap-8">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5 }}
              className="relative"
            >
              <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-purple-500/20 to-violet-500/20 border border-purple-500/30 flex items-center justify-center">
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                  <circle cx="24" cy="24" r="20" stroke="#8b5cf6" strokeWidth="2" fill="none" />
                  <circle cx="24" cy="24" r="12" stroke="#8b5cf6" strokeWidth="1.5" fill="none" opacity="0.6" />
                  <circle cx="24" cy="24" r="4" fill="#8b5cf6" />
                </svg>
              </div>
              <motion.div
                animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0, 0.3] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                className="absolute inset-0 rounded-2xl border border-purple-500/30"
              />
            </motion.div>

            <div className="text-center">
              <h1 className="text-2xl font-bold text-white mb-1">GenericAgent</h1>
              <p className="text-sm text-white/50">Self-Evolving AI</p>
            </div>

            <div className="w-64">
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-purple-500 to-violet-500 rounded-full"
                  style={{ width: `${progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              <p className="text-xs text-white/40 mt-3 text-center">
                {statusMessages[state]}
              </p>
            </div>

            <AnimatePresence>
              {state === 'error' && (
                <motion.button
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  onClick={handleRetry}
                  className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-lg transition-colors"
                >
                  Retry
                </motion.button>
              )}
            </AnimatePresence>

            <button
              onClick={() => setShow(false)}
              className="text-xs text-white/30 hover:text-white/50 transition-colors"
            >
              Skip — Continue without backend
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

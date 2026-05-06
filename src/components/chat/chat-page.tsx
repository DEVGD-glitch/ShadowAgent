'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { MessageList } from './message-list';
import { ChatInput } from './chat-input';
import { useAgentStore } from '@/stores/agent-store';
import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-react';

export function ChatPage() {
  const { circuitBreakerOpen, setCircuitBreaker, backendConnected } = useAgentStore();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col h-full"
    >
      {/* System Notice Banner */}
      <AnimatePresence>
        {circuitBreakerOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-4 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/20 my-2">
              <div className="flex items-center gap-2 text-sm text-red-300">
                <AlertTriangle className="h-4 w-4" />
                <span>Provider is currently unavailable due to rate limiting</span>
              </div>
              <motion.button
                onClick={async () => {
                  setCircuitBreaker(false);
                  // Test the connection by checking backend health
                  try {
                    const { checkBackendHealth } = await import('@/lib/backend');
                    const isHealthy = await checkBackendHealth();
                    if (!isHealthy) {
                      setCircuitBreaker(true);
                    }
                  } catch {
                    setCircuitBreaker(true);
                  }
                }}
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/20 text-red-300 text-xs hover:bg-red-500/30 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <RefreshCw className="h-3 w-3" />
                Retry
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Backend Disconnected Warning */}
      <AnimatePresence>
        {backendConnected === 'disconnected' && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-4 overflow-hidden"
          >
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-yellow-500/10 border border-yellow-500/20 my-2 text-sm text-yellow-300">
              <WifiOff className="h-4 w-4 shrink-0" />
              <span>Backend disconnected — running in offline mode. Start the Shadow Agent server on port 8765 to enable all features.</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages Area */}
      <MessageList />

      {/* Input Area */}
      <div className="p-4 pt-0">
        <ChatInput />
      </div>
    </motion.div>
  );
}

'use client';

import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Sparkles } from 'lucide-react';
import { useAgentStore } from '@/stores/agent-store';
import { MessageItem } from './message-item';
import { cn } from '@/lib/utils';

export function MessageList() {
  const { messages, isStreaming, status } = useAgentStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Track whether user has scrolled up
  const handleScroll = () => {
    const el = containerRef.current;
    if (el) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
      isNearBottomRef.current = nearBottom;
    }
  };

  // Auto-scroll to bottom on new messages only if near bottom
  useEffect(() => {
    if (isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto custom-scrollbar"
    >
      {messages.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="py-4">
          <AnimatePresence mode="popLayout">
            {messages.map((message, index) => (
              <MessageItem key={message.id} message={message} index={index} />
            ))}
          </AnimatePresence>

          {/* Streaming Indicator */}
          <AnimatePresence>
            {(isStreaming && status === 'thinking') && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                className="flex items-center gap-3 px-4 py-2"
              >
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/30 to-violet-600/30 border border-purple-500/20 flex items-center justify-center">
                  <Bot className="h-3.5 w-3.5 text-purple-300" />
                </div>
                <div className="flex items-center gap-1">
                  <motion.div
                    className="w-1.5 h-1.5 rounded-full bg-purple-400"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: 0 }}
                  />
                  <motion.div
                    className="w-1.5 h-1.5 rounded-full bg-purple-400"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                  />
                  <motion.div
                    className="w-1.5 h-1.5 rounded-full bg-purple-400"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center h-full">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-md px-4"
      >
        <motion.div
          className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/20 to-violet-600/20 border border-purple-500/20 flex items-center justify-center mx-auto mb-4"
          animate={{
            boxShadow: [
              '0 0 20px oklch(0.627 0.265 293 / 10%)',
              '0 0 40px oklch(0.627 0.265 293 / 20%)',
              '0 0 20px oklch(0.627 0.265 293 / 10%)',
            ],
          }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <Sparkles className="h-8 w-8 text-purple-400" />
        </motion.div>
        <h2 className="text-lg font-semibold text-white/80 mb-2">
          How can I help you today?
        </h2>
        <p className="text-sm text-white/30 leading-relaxed mb-6">
          I&apos;m GenericAgent, a self-evolving AI that can write code, search the web, manage files, and learn from our interactions.
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {[
            'Write a Python script',
            'Search the web',
            'Debug my code',
            'Analyze a screenshot',
          ].map((suggestion, i) => (
            <motion.button
              key={suggestion}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i }}
              onClick={() => {
                const event = new CustomEvent('setChatInput', { detail: suggestion });
                window.dispatchEvent(event);
              }}
              className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-white/40 hover:text-white/60 hover:bg-white/[0.06] transition-colors"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {suggestion}
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

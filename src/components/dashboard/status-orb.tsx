'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { AgentStatus } from '@/stores/agent-store';

interface StatusOrbProps {
  status: AgentStatus;
  size?: number;
}

const STATUS_GRADIENTS: Record<AgentStatus, { from: string; to: string; glow: string }> = {
  idle: { from: 'from-green-400', to: 'to-emerald-600', glow: 'shadow-green-500/30' },
  thinking: { from: 'from-yellow-400', to: 'to-amber-600', glow: 'shadow-yellow-500/30' },
  acting: { from: 'from-orange-400', to: 'to-red-500', glow: 'shadow-orange-500/30' },
  streaming: { from: 'from-blue-400', to: 'to-indigo-600', glow: 'shadow-blue-500/30' },
  error: { from: 'from-red-400', to: 'to-rose-600', glow: 'shadow-red-500/30' },
};

const STATUS_LABELS: Record<AgentStatus, string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  acting: 'Acting',
  streaming: 'Streaming',
  error: 'Error',
};

export function StatusOrb({ status, size = 120 }: StatusOrbProps) {
  const gradient = STATUS_GRADIENTS[status];

  const isActive = status === 'thinking' || status === 'streaming' || status === 'acting';

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        {/* Outer Glow Ring */}
        <motion.div
          className={cn(
            'absolute inset-0 rounded-full blur-xl opacity-40',
            `bg-gradient-to-br ${gradient.from} ${gradient.to}`
          )}
          animate={
            isActive
              ? { scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }
              : { scale: 1, opacity: 0.3 }
          }
          transition={{
            duration: 2,
            repeat: isActive ? Infinity : 0,
            ease: 'easeInOut',
          }}
          style={{ width: size, height: size }}
        />

        {/* Main Orb */}
        <motion.div
          className={cn(
            'relative rounded-full bg-gradient-to-br flex items-center justify-center',
            gradient.from,
            gradient.to,
            isActive && 'shadow-2xl',
            isActive && gradient.glow
          )}
          style={{ width: size, height: size }}
          animate={
            isActive
              ? { scale: [1, 1.05, 1] }
              : { scale: 1 }
          }
          transition={{
            duration: 1.5,
            repeat: isActive ? Infinity : 0,
            ease: 'easeInOut',
          }}
        >
          {/* Inner Highlight */}
          <motion.div
            className="absolute inset-[15%] rounded-full bg-white/10"
            animate={
              isActive
                ? { opacity: [0.1, 0.2, 0.1] }
                : { opacity: 0.1 }
            }
            transition={{
              duration: 2,
              repeat: isActive ? Infinity : 0,
            }}
          />

          {/* Center Icon */}
          <motion.span
            className="text-3xl"
            animate={
              status === 'thinking'
                ? { rotate: [0, 360] }
                : status === 'streaming'
                  ? { scale: [1, 1.1, 1] }
                  : status === 'acting'
                    ? { y: [0, -3, 0] }
                    : status === 'error'
                      ? { x: [0, -2, 2, -2, 0] }
                      : {}
            }
            transition={{
              duration: status === 'thinking' ? 4 : 0.5,
              repeat: Infinity,
              ease: 'linear',
            }}
          >
            {status === 'idle' && '😴'}
            {status === 'thinking' && '🤔'}
            {status === 'acting' && '⚡'}
            {status === 'streaming' && '💬'}
            {status === 'error' && '⚠️'}
          </motion.span>
        </motion.div>

        {/* Orbiting Dots */}
        {isActive && (
          <>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className={cn('absolute w-2 h-2 rounded-full bg-white/30', gradient.from)}
                animate={{
                  rotate: [0, 360],
                }}
                transition={{
                  duration: 3 + i,
                  repeat: Infinity,
                  ease: 'linear',
                  delay: i * 0.5,
                }}
                style={{
                  top: '50%',
                  left: '50%',
                  transformOrigin: `0 ${size / 2}px`,
                }}
              />
            ))}
          </>
        )}
      </div>

      {/* Status Label */}
      <div className="text-center">
        <motion.p
          key={status}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-semibold text-white/80"
        >
          {STATUS_LABELS[status]}
        </motion.p>
        <p className="text-xs text-white/30 mt-0.5">Agent Status</p>
      </div>
    </div>
  );
}

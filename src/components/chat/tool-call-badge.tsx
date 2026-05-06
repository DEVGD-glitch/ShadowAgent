'use client';

import { motion } from 'framer-motion';
import { Wrench, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolCall } from '@/stores/agent-store';

interface ToolCallBadgeProps {
  toolCall: ToolCall;
}

const STATUS_CONFIG = {
  pending: {
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    color: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400',
    label: 'Running',
  },
  success: {
    icon: <CheckCircle2 className="h-3 w-3" />,
    color: 'bg-green-500/10 border-green-500/20 text-green-400',
    label: 'Success',
  },
  error: {
    icon: <XCircle className="h-3 w-3" />,
    color: 'bg-red-500/10 border-red-500/20 text-red-400',
    label: 'Error',
  },
};

export function ToolCallBadge({ toolCall }: ToolCallBadgeProps) {
  const config = STATUS_CONFIG[toolCall.status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 5, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="my-1.5"
    >
      <div
        className={cn(
          'inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs font-medium',
          config.color
        )}
      >
        <Wrench className="h-3 w-3 opacity-60" />
        <span className="font-mono">{toolCall.name}</span>
        {Object.keys(toolCall.args).length > 0 && (
          <span className="opacity-50">
            {Object.entries(toolCall.args)
              .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
              .join(', ')
              .slice(0, 60)}
          </span>
        )}
        <div className="flex items-center gap-1">
          {config.icon}
          <span>{config.label}</span>
        </div>
        {toolCall.duration && (
          <span className="opacity-50">{toolCall.duration}ms</span>
        )}
      </div>
      {toolCall.result && toolCall.status !== 'pending' && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-1 ml-6 text-[11px] text-white/25 font-mono max-h-24 overflow-y-auto"
        >
          {toolCall.result.slice(0, 200)}
        </motion.div>
      )}
    </motion.div>
  );
}

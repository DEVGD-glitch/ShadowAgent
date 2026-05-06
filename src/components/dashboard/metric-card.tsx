'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; positive: boolean };
  color?: string;
  delay?: number;
}

export function MetricCard({ label, value, icon: Icon, trend, color = 'text-purple-400', delay = 0 }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05] transition-colors group"
    >
      <div className="flex items-start justify-between mb-3">
        <motion.div
          className={cn('p-2 rounded-lg bg-white/[0.04]', color)}
          whileHover={{ scale: 1.1, rotate: 5 }}
        >
          <Icon className="h-4 w-4" />
        </motion.div>
        {trend && (
          <span
            className={cn(
              'text-[10px] font-medium px-1.5 py-0.5 rounded-full',
              trend.positive
                ? 'bg-green-500/10 text-green-400'
                : 'bg-red-500/10 text-red-400'
            )}
          >
            {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </span>
        )}
      </div>
      <motion.p
        className="text-2xl font-bold text-white/90"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: delay + 0.1 }}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
      </motion.p>
      <p className="text-xs text-white/30 mt-1">{label}</p>
    </motion.div>
  );
}

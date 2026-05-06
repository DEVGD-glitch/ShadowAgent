'use client';

import { motion } from 'framer-motion';
import {
  Activity,
  Cpu,
  Zap,
  AlertTriangle,
  Monitor,
  Code2,
  Clock,
} from 'lucide-react';
import { useSettingsStore } from '@/stores/settings-store';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';

export function HealthDashboard() {
  const { health } = useSettingsStore();

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${d}d ${h}h ${m}m`;
  };

  const formatNumber = (n: number) => n.toLocaleString();

  // Compute a dynamic max for each metric to keep progress bars meaningful.
  // Instead of fixed arbitrary caps, we derive a sensible max from the current value
  // so the bar shows relative scale rather than an absolute threshold.
  const dynamicMax = (value: number, base: number) => {
    if (value <= 0) return base;
    // Round up to the next power-of-10 multiple of base
    const magnitude = Math.pow(10, Math.floor(Math.log10(Math.max(value, 1))));
    return Math.max(Math.ceil(value / magnitude) * magnitude, base);
  };

  const healthItems = [
    {
      icon: <Clock className="h-4 w-4 text-green-400" />,
      label: 'Uptime',
      value: formatUptime(health.uptime),
      progress: Math.min((health.uptime / dynamicMax(health.uptime, 3600)) * 100, 100),
      color: 'bg-green-500',
    },
    {
      icon: <Cpu className="h-4 w-4 text-purple-400" />,
      label: 'LLM Calls',
      value: formatNumber(health.llmCalls),
      progress: Math.min((health.llmCalls / dynamicMax(health.llmCalls, 100)) * 100, 100),
      color: 'bg-purple-500',
    },
    {
      icon: <Zap className="h-4 w-4 text-yellow-400" />,
      label: 'Token Usage',
      value: formatNumber(health.tokenUsage),
      progress: Math.min((health.tokenUsage / dynamicMax(health.tokenUsage, 10000)) * 100, 100),
      color: 'bg-yellow-500',
    },
    {
      icon: <AlertTriangle className="h-4 w-4 text-red-400" />,
      label: 'Error Count',
      value: formatNumber(health.errorCount),
      progress: Math.min((health.errorCount / dynamicMax(health.errorCount, 10)) * 100, 100),
      color: 'bg-red-500',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Platform Info */}
      <Card className="bg-white/[0.02] border-white/[0.06]">
        <CardContent className="p-4">
          <div className="flex items-center gap-3 mb-4">
            <Monitor className="h-4 w-4 text-purple-400" />
            <h4 className="text-sm font-semibold text-white/70">Platform Info</h4>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-white/25 mb-0.5">Platform</p>
              <p className="text-xs text-white/60 flex items-center gap-1">
                <Monitor className="h-3 w-3" />
                {health.platform}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-white/25 mb-0.5">Python Version</p>
              <p className="text-xs text-white/60 flex items-center gap-1">
                <Code2 className="h-3 w-3" />
                {health.pythonVersion}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Health Metrics */}
      <div className="space-y-3">
        {healthItems.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
          >
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {item.icon}
                    <span className="text-xs text-white/50">{item.label}</span>
                  </div>
                  <span className="text-sm font-semibold text-white/70">{item.value}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                  <motion.div
                    className={cn('h-full rounded-full', item.color)}
                    initial={{ width: 0 }}
                    animate={{ width: `${item.progress}%` }}
                    transition={{ delay: i * 0.08 + 0.3, duration: 0.8 }}
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Last Check */}
      <p className="text-[10px] text-white/15 text-center">
        Last checked: {new Date(health.lastCheck).toLocaleString()}
      </p>
    </div>
  );
}


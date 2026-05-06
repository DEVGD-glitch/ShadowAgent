'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  Zap,
  Cpu,
  Clock,
  AlertTriangle,
  HardDrive,
  Sparkles,
  Wrench,
  Activity,
  Wifi,
  WifiOff,
  RefreshCw,
} from 'lucide-react';
import { useAgentStore } from '@/stores/agent-store';
import { useSettingsStore } from '@/stores/settings-store';
import { StatusOrb } from './status-orb';
import { MetricCard } from './metric-card';
import { MemoryLayers } from './memory-layers';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getStatus, getModels, getTools, getMemoryLayers } from '@/lib/api';
import { checkBackendHealth } from '@/lib/backend';
import { cn } from '@/lib/utils';

export function DashboardPage() {
  const { status, metrics, activeTools, models, currentModel, setModels, setStatus, updateMetrics, setBackendConnected } = useAgentStore();
  const { updateHealth } = useSettingsStore();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [memoryLayersFromData, setMemoryLayersFromData] = useState<Array<{ name: string; usage: number; max: number; color: string }>>([]);

  // Fetch real data from backend
  const refreshData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [statusResult, modelsResult, toolsResult] = await Promise.allSettled([
        getStatus(),
        getModels(),
        getTools(),
      ]);

      if (statusResult.status === 'fulfilled') {
        const statusData = statusResult.value;
        setStatus(statusData.status);
        updateMetrics(statusData.metrics);
        updateHealth({
          uptime: statusData.metrics.uptime,
          llmCalls: statusData.metrics.llmCalls,
          tokenUsage: statusData.metrics.tokensUsed,
          errorCount: Math.floor(statusData.metrics.errorRate * statusData.metrics.llmCalls),
          lastCheck: Date.now(),
        });
      }

      if (modelsResult.status === 'fulfilled') {
        setModels(modelsResult.value);
      }

      // Fetch memory layers (non-critical)
      try {
        const layersData = await getMemoryLayers();
        // Transform memory layers for the MemoryLayers component
        if (Array.isArray(layersData) && layersData.length > 0) {
          setMemoryLayersFromData(
            layersData.map((layer: any) => ({
              name: layer.name || layer.level,
              usage: layer.size || 0,
              max: layer.maxSize || 100,
              color: layer.color || '#7c3aed',
            }))
          );
        }
      } catch {
        // Memory layers are non-critical, ignore
      }

      // Check if backend is connected
      const isHealthy = await checkBackendHealth();
      setBackendConnected(isHealthy ? 'connected' : 'disconnected');
    } catch (err) {
      console.warn('Failed to refresh dashboard data:', err);
    }
    setIsRefreshing(false);
  }, [setStatus, updateMetrics, setModels, updateHealth, setBackendConnected]);

  // Load data on mount
  useEffect(() => {
    refreshData();
  }, [refreshData]);

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="h-full overflow-y-auto p-6 space-y-6"
    >
      {/* Refresh Button */}
      <div className="flex justify-end">
        <motion.button
          onClick={refreshData}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/40 hover:text-white/60 hover:bg-white/[0.06] transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
        </motion.button>
      </div>

      {/* Top Section: Status Orb + Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Orb */}
        <Card className="bg-white/[0.02] border-white/[0.06]">
          <CardContent className="flex flex-col items-center justify-center py-8">
            <StatusOrb status={status} size={100} />
            <div className="mt-4 text-center">
              <p className="text-xs text-white/30">Current Model</p>
              <p className="text-sm font-medium text-white/70 mt-0.5">
                {currentModel?.name || 'None'}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Metrics Grid */}
        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-3 gap-3">
          <MetricCard
            label="Total Messages"
            value={metrics.totalMessages}
            icon={MessageSquare}
            color="text-blue-400"
            delay={0.05}
          />
          <MetricCard
            label="Tokens Used"
            value={metrics.tokensUsed.toLocaleString()}
            icon={Zap}
            color="text-yellow-400"
            delay={0.1}
          />
          <MetricCard
            label="LLM Calls"
            value={metrics.llmCalls}
            icon={Cpu}
            color="text-purple-400"
            delay={0.15}
          />
          <MetricCard
            label="Uptime"
            value={formatUptime(metrics.uptime)}
            icon={Clock}
            color="text-green-400"
            delay={0.2}
          />
          <MetricCard
            label="Error Rate"
            value={`${(metrics.errorRate * 100).toFixed(1)}%`}
            icon={AlertTriangle}
            color="text-red-400"
            delay={0.25}
            trend={undefined}
          />
          <MetricCard
            label="Memory Usage"
            value={`${metrics.memoryUsage}%`}
            icon={HardDrive}
            color="text-orange-400"
            delay={0.3}
          />
        </div>
      </div>

      {/* Bottom Section: Memory + Active Tools + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Memory Layers */}
        <Card className="bg-white/[0.02] border-white/[0.06]">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-purple-400" />
              Memory Layers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <MemoryLayers layers={memoryLayersFromData} />
          </CardContent>
        </Card>

        {/* Provider Health */}
        <Card className="bg-white/[0.02] border-white/[0.06]">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
              <Wrench className="h-4 w-4 text-yellow-400" />
              Provider Health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {models.length > 0 ? (
              models.map((model, i) => (
                <motion.div
                  key={model.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center justify-between py-1.5"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        model.health === 'healthy'
                          ? 'bg-green-500'
                          : model.health === 'degraded'
                            ? 'bg-yellow-500'
                            : model.health === 'down'
                              ? 'bg-red-500'
                              : 'bg-gray-500'
                      }`}
                    />
                    <span className="text-xs text-white/60">{model.name}</span>
                  </div>
                  <span className="text-[10px] text-white/30">{model.provider}</span>
                </motion.div>
              ))
            ) : (
              <div className="text-center py-4">
                <WifiOff className="h-6 w-6 text-white/10 mx-auto mb-2" />
                <p className="text-xs text-white/20">No models loaded</p>
                <p className="text-[10px] text-white/15">Connect to backend to load models</p>
              </div>
            )}

            {/* Active Tools */}
            <div className="pt-3 border-t border-white/[0.06]">
              <p className="text-xs text-white/30 mb-2">Active Tools</p>
              {activeTools.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {activeTools.map((tool) => (
                    <Badge
                      key={tool}
                      variant="secondary"
                      className="text-[10px] bg-purple-500/10 text-purple-300 border-purple-500/20"
                    >
                      <Wrench className="h-2.5 w-2.5 mr-1" />
                      {tool}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-[10px] text-white/20">No active tools</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="bg-white/[0.02] border-white/[0.06]">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-400" />
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { action: metrics.totalMessages > 0 ? `${metrics.totalMessages} messages sent` : 'No messages yet', time: 'Session', icon: '💬' },
                { action: `Using ${currentModel?.name || 'no model'}`, time: 'Current', icon: '🤖' },
                { action: `${models.length} models available`, time: 'Loaded', icon: '📋' },
                { action: `Memory at ${metrics.memoryUsage}%`, time: 'Status', icon: '🧠' },
                { action: `${metrics.skillsCrystallized} skills crystallized`, time: 'Learned', icon: '✨' },
                { action: `Error rate: ${(metrics.errorRate * 100).toFixed(1)}%`, time: 'Health', icon: '❤️' },
              ].map((activity, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-2 text-xs"
                >
                  <span>{activity.icon}</span>
                  <span className="text-white/50 flex-1">{activity.action}</span>
                  <span className="text-white/20">{activity.time}</span>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Skills Crystallized */}
      <Card className="bg-white/[0.02] border-white/[0.06]">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-500/10">
                <Sparkles className="h-5 w-5 text-purple-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white/70">Skills Crystallized</p>
                <p className="text-xs text-white/30">Automatically learned from interactions</p>
              </div>
            </div>
            <motion.p
              className="text-3xl font-bold text-purple-400"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.5 }}
            >
              {metrics.skillsCrystallized}
            </motion.p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

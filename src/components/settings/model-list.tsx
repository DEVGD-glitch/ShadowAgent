'use client';

import { motion } from 'framer-motion';
import { Check, Wifi, WifiOff, AlertTriangle, HelpCircle, RefreshCw } from 'lucide-react';
import { useAgentStore, type LLMModel } from '@/stores/agent-store';
import { switchModel } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

export function ModelList() {
  const { models, currentModel, setCurrentModel } = useAgentStore();

  const handleSwitch = async (model: LLMModel) => {
    if (model.id === currentModel?.id) return;
    const result = await switchModel(model.index);
    if (result.success) {
      setCurrentModel(model);
    } else {
      toast.error('Failed to switch model. The backend may be unavailable.');
    }
  };

  const HEALTH_CONFIG = {
    healthy: { icon: <Wifi className="h-3 w-3" />, color: 'text-green-400', bg: 'bg-green-500/10', label: 'Healthy' },
    degraded: { icon: <AlertTriangle className="h-3 w-3" />, color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Degraded' },
    down: { icon: <WifiOff className="h-3 w-3" />, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Down' },
    unknown: { icon: <HelpCircle className="h-3 w-3" />, color: 'text-gray-400', bg: 'bg-gray-500/10', label: 'Unknown' },
  };

  // Group models by provider
  const grouped = models.reduce<Record<string, LLMModel[]>>((acc, model) => {
    if (!acc[model.provider]) acc[model.provider] = [];
    acc[model.provider].push(model);
    return acc;
  }, {});

  if (models.length === 0) {
    return (
      <div className="text-center py-8">
        <WifiOff className="h-8 w-8 text-white/10 mx-auto mb-3" />
        <p className="text-sm text-white/30">No models loaded</p>
        <p className="text-xs text-white/20 mt-1">Connect to the backend to load available models</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([provider, providerModels], pi) => (
        <motion.div
          key={provider}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: pi * 0.1 }}
        >
          <h4 className="text-xs font-semibold text-white/30 uppercase tracking-wider mb-3">
            {provider}
          </h4>
          <div className="space-y-2">
            {providerModels.map((model, mi) => {
              const isActive = model.id === currentModel?.id;
              const health = HEALTH_CONFIG[model.health];
              return (
                <motion.div
                  key={model.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: pi * 0.1 + mi * 0.05 }}
                  onClick={() => handleSwitch(model)}
                  className={cn(
                    'flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all',
                    isActive
                      ? 'bg-purple-500/10 border-purple-500/20'
                      : 'bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.04] hover:border-white/[0.08]'
                  )}
                  whileHover={{ x: 3 }}
                  whileTap={{ scale: 0.99 }}
                >
                  {/* Radio Indicator */}
                  <div className="shrink-0">
                    {isActive ? (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="w-5 h-5 rounded-full bg-purple-500/20 flex items-center justify-center"
                      >
                        <div className="w-2.5 h-2.5 rounded-full bg-purple-400" />
                      </motion.div>
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-white/10" />
                    )}
                  </div>

                  {/* Model Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className={cn(
                        'text-sm font-medium',
                        isActive ? 'text-purple-300' : 'text-white/60'
                      )}>
                        {model.name}
                      </p>
                      {isActive && (
                        <Badge className="text-[9px] py-0 px-1.5 bg-purple-500/20 text-purple-300 border-purple-500/30">
                          Active
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Health Status */}
                  <div className={cn(
                    'flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px]',
                    health.bg,
                    health.color
                  )}>
                    {health.icon}
                    <span>{health.label}</span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

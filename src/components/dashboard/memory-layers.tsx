'use client';

import { motion } from 'framer-motion';

interface MemoryLayersProps {
  layers?: Array<{
    name: string;
    usage: number;
    max: number;
    color: string;
  }>;
}

export function MemoryLayers({ layers = [] }: MemoryLayersProps) {
  if (layers.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-xs text-white/20">No memory data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {layers.map((layer, i) => {
        const percentage = layer.max > 0 ? Math.round((layer.usage / layer.max) * 100) : 0;
        return (
          <motion.div
            key={layer.name}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="group"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span
                  className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
                  style={{ background: `${layer.color}20`, color: layer.color }}
                >
                  L{i}
                </span>
                <span className="text-xs font-medium text-white/60">{layer.name}</span>
              </div>
              <span className="text-[10px] text-white/30">
                {layer.usage}/{layer.max}
              </span>
            </div>
            <div className="h-2 rounded-full bg-white/[0.04] overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: `linear-gradient(90deg, ${layer.color}80, ${layer.color})` }}
                initial={{ width: 0 }}
                animate={{ width: `${percentage}%` }}
                transition={{ delay: i * 0.08 + 0.3, duration: 0.8, ease: 'easeOut' }}
              />
            </div>
            <p className="text-[10px] text-white/20 mt-0.5">{percentage}% full</p>
          </motion.div>
        );
      })}
    </div>
  );
}

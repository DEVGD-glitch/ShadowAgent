'use client';

import { motion } from 'framer-motion';

export function StreamingCursor() {
  return (
    <motion.span
      className="inline-block ml-0.5 text-purple-400 font-light"
      animate={{ opacity: [1, 0] }}
      transition={{
        duration: 0.8,
        repeat: Infinity,
        repeatType: 'reverse',
        ease: 'easeInOut',
      }}
    >
      ▌
    </motion.span>
  );
}

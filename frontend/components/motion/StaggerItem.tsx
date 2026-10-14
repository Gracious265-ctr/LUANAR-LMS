"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

const STAGGER_ITEM_DELAY = 0.05;

export function StaggerItem({
  children,
  className,
  __staggerIndex = 0,
}: {
  children: ReactNode;
  className?: string;
  __staggerIndex?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.22,
        ease: [0.16, 1, 0.3, 1],
        delay: __staggerIndex * STAGGER_ITEM_DELAY,
      }}
    >
      {children}
    </motion.div>
  );
}
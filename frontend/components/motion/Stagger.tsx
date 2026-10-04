"use client";

import { Children, cloneElement, isValidElement, type ReactNode } from "react";
import { motion } from "motion/react";

const MAX_STAGGER_ITEMS = 10;

type IndexableElement = React.ReactElement<{ __staggerIndex?: number }>;

export function Stagger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const items = Children.toArray(children);
  const shouldStagger = items.length > 0 && items.length <= MAX_STAGGER_ITEMS;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
    >
      {shouldStagger
        ? Children.map(items, (child, index) =>
            isValidElement(child)
              ? cloneElement(child as IndexableElement, {
                  __staggerIndex: index,
                })
              : child
          )
        : children}
    </motion.div>
  );
}
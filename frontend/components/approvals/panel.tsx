import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle",
        className
      )}
    >
      {title && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-text-primary">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function DetailRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm font-medium text-text-secondary">{label}</dt>
      <dd className="text-sm text-text-primary sm:col-span-2">{children}</dd>
    </div>
  );
}
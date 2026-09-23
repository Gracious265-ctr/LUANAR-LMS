"use client";

import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  className,
  label = "Tabs",
}: {
  tabs: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  label?: string;
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "inline-flex gap-1 rounded-lg bg-surface-muted p-1",
        className
      )}
      onKeyDown={(event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          return;
        }
        event.preventDefault();
        const index = tabs.findIndex((tab) => tab.value === value);
        let next = index;
        if (event.key === "ArrowLeft") next = Math.max(0, index - 1);
        else if (event.key === "ArrowRight")
          next = Math.min(tabs.length - 1, index + 1);
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        onChange(tabs[next].value);
        (event.currentTarget.querySelector<HTMLElement>(
          `[data-tab-value="${tabs[next].value}"]`
        ))?.focus();
      }}
    >
      {tabs.map((tab) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={selected}
            data-tab-value={tab.value}
            onClick={() => onChange(tab.value)}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
              selected
                ? "bg-surface-card text-text-primary shadow-subtle"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            {tab.label}
            {typeof tab.count === "number" && tab.count > 0 && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-semibold",
                  selected
                    ? "bg-brand-primary-subtle text-brand-primary"
                    : "bg-surface-card text-text-secondary"
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
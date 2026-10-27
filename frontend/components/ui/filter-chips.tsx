"use client";

import { cn } from "@/lib/utils";

export interface FilterChipOption<T extends string = string> {
  value: T;
  label: string;
}

/**
 * A row of mutually exclusive filter chips.
 *
 * Chips rather than a select because every option is visible at once and one
 * click is the whole interaction — the same pattern the teams and delegations
 * screens already use for their status filters. `aria-pressed` is what tells a
 * screen reader which chip is the current narrowing; the visual fill is only
 * the second, redundant signal.
 */
export function FilterChips<T extends string = string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: ReadonlyArray<FilterChipOption<T>>;
  value: T;
  onChange: (value: T) => void;
  /** Names the group, e.g. "Filter HR users by status". */
  label: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      {options.map((option) => {
        const current = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={current}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-sm px-3 py-1.5 text-xs font-medium transition-colors",
              current
                ? "bg-brand-primary text-brand-primary-foreground"
                : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

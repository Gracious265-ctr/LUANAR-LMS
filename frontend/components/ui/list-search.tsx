"use client";

import { Search, X } from "lucide-react";

import { cn } from "@/lib/utils";

import { Input } from "./input";

/**
 * The search box every list screen uses.
 *
 * Controlled rather than URL-driven: the lists that use it already hold their
 * whole dataset in the browser, so typing filters the rows immediately instead
 * of spending a navigation on each keystroke. Screens whose data comes from a
 * searchable endpoint keep their own form — this is for local narrowing.
 *
 * `label` is the accessible name, not a visible heading: the magnifier and the
 * placeholder carry the same information on screen, so a second visible label
 * would only repeat it.
 */
export function ListSearch({
  value,
  onChange,
  label,
  placeholder = "Search…",
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  /** The accessible name, e.g. "Search HR users". */
  label: string;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
        aria-hidden="true"
      />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 py-2 pl-9 pr-9 text-sm"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-text-muted transition-colors hover:text-text-primary"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

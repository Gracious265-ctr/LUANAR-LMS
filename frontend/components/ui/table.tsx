import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Data table primitives.
 *
 * These carry the styling that used to be copy-pasted into every table
 * component: `Table` owns the horizontal scroll container, `TableHead` the
 * uppercase header typography, `TableRow` the borders and hover, and
 * `TableBody` the last-row rule. So drop a manual `overflow-x-auto` wrapper
 * and the per-cell `py-3 pr-4` when converting a hand-rolled `<table>`.
 *
 * Cells get `px-4` where the hand-rolled tables used `pr-4`, so a converted
 * table gains a left gutter. Pass `className` to keep a deliberately tighter
 * cell, e.g. the `px-2` chevron column.
 *
 * Not for layout tables: `hr/document-template-preview.tsx` lays out a
 * printable A4 form with cell borders and a label column, and is left as
 * raw markup on purpose.
 */
export function Table({ className, ...props }: React.ComponentPropsWithRef<"table">) {
  return (
    <div data-slot="table-container" className="w-full overflow-x-auto">
      <table
        data-slot="table"
        className={cn("w-full text-sm text-text-secondary", className)}
        {...props}
      />
    </div>
  );
}

export function TableHeader({
  className,
  ...props
}: React.ComponentPropsWithRef<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn(
        "[&_tr]:border-b [&_tr]:border-border-default",
        className
      )}
      {...props}
    />
  );
}

export function TableBody({ className, ...props }: React.ComponentPropsWithRef<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-b-0", className)}
      {...props}
    />
  );
}

export function TableFooter({ className, ...props }: React.ComponentPropsWithRef<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t border-border-default bg-surface-muted font-medium",
        className
      )}
      {...props}
    />
  );
}

export function TableRow({ className, ...props }: React.ComponentPropsWithRef<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b border-border-default transition-colors hover:bg-surface-hover",
        className
      )}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: React.ComponentPropsWithRef<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "px-4 py-3 text-left align-middle text-xs font-medium uppercase tracking-wide text-text-muted",
        "[&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: React.ComponentPropsWithRef<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn("px-4 py-3 align-middle", "[&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  );
}

export function TableCaption({
  className,
  ...props
}: React.ComponentPropsWithRef<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-3 text-sm text-text-muted", className)}
      {...props}
    />
  );
}

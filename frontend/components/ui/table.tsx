import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Data table primitives.
 *
 * The defaults here encode the table styling that was previously copy-pasted
 * into every table component, so converting a hand-rolled `<table>` to these
 * is a visual no-op. `Table` owns the horizontal scroll container; drop any
 * manual `overflow-x-auto` wrapper when converting.
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

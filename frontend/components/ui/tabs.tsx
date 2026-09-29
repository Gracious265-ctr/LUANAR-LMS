"use client";

import { cva, type VariantProps } from "class-variance-authority";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

/**
 * Tabbed panels.
 *
 * The app has two tab treatments, so `TabsList` and `TabsTrigger` take a
 * matching `variant`:
 *  - `underline` (default): bottom-border indicator, used by the plans
 *    workspaces.
 *  - `segmented`: filled pills inside a bordered container, used by the
 *    approvals and cancellation list views.
 *
 * The variants reproduce the existing hand-rolled tab bars exactly, so a
 * conversion is a visual no-op. Pass the same `variant` to the list and its
 * triggers.
 */
const tabsListVariants = cva("inline-flex items-center", {
  variants: {
    variant: {
      underline: "gap-1 border-b border-border-default",
      segmented: "gap-1 rounded-lg border border-border-default bg-surface-card p-1",
    },
  },
  defaultVariants: { variant: "underline" },
});

const tabsTriggerVariants = cva(
  [
    "inline-flex items-center gap-1.5 font-medium whitespace-nowrap transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
    "disabled:pointer-events-none disabled:opacity-50",
  ],
  {
    variants: {
      variant: {
        underline: [
          "rounded-t-lg px-4 py-2 text-sm",
          "text-text-secondary hover:text-text-primary",
          "data-[state=active]:border-b-2 data-[state=active]:border-brand-primary data-[state=active]:text-brand-primary",
        ],
        segmented: [
          "rounded-md px-3 py-1.5 text-sm",
          "text-text-secondary hover:text-text-primary",
          "data-[state=active]:bg-brand-primary-subtle data-[state=active]:text-brand-primary",
        ],
      },
    },
    defaultVariants: { variant: "underline" },
  }
);

export function Tabs({ className, ...props }: React.ComponentPropsWithRef<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex flex-col gap-4", className)}
      {...props}
    />
  );
}

export function TabsList({
  className,
  variant,
  ...props
}: React.ComponentPropsWithRef<typeof TabsPrimitive.List> & VariantProps<typeof tabsListVariants>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  variant,
  ...props
}: React.ComponentPropsWithRef<typeof TabsPrimitive.Trigger> &
  VariantProps<typeof tabsTriggerVariants>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(tabsTriggerVariants({ variant }), className)}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("outline-none", className)}
      {...props}
    />
  );
}

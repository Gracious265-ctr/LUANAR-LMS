"use client";

import { CalendarRange } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/**
 * The Leave Plans entry, shown to everybody: every employee has plans, so this
 * is not gated the way the Approvals entry is.
 *
 * The badge counts blocks waiting for the caller's own confirmation rather than
 * approvals for them. That is the number with a deadline attached — a block
 * that is not confirmed inside its window is released — so it is the one worth
 * putting in front of somebody on every page.
 */
export function PlansNavItem({
  open,
  pendingConfirmations = 0,
}: {
  open: boolean;
  /** The caller's unconfirmed reserved blocks, when the layout read it. */
  pendingConfirmations?: number;
}) {
  const pathname = usePathname();

  const isSelected =
    pathname === "/dashboard/plans" || pathname.startsWith("/dashboard/plans/");

  return (
    <Link
      href="/dashboard/plans"
      // Collapsed, the label span is not rendered, so the icon alone would
      // leave the link with no accessible name.
      aria-label="Leave plans"
      className={cn(
        "relative flex h-11 w-full items-center rounded-md transition-colors duration-200",
        isSelected
          ? "bg-brand-primary-subtle text-brand-primary shadow-sm border-l-2 border-brand-primary"
          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
      )}
    >
      <div className="grid h-full w-12 place-content-center">
        <CalendarRange className="h-4 w-4" />
      </div>
      {open && (
        <span className="truncate text-sm font-medium transition-opacity duration-200">
          Leave Plans
        </span>
      )}
      {open && pendingConfirmations > 0 && (
        <span
          data-testid="plans-pending-confirmations"
          className="ml-auto mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-primary px-1.5 text-[11px] font-semibold leading-none text-white"
        >
          {pendingConfirmations > 99 ? "99+" : pendingConfirmations}
        </span>
      )}
    </Link>
  );
}

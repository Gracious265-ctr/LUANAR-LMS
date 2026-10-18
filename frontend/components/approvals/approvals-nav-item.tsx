"use client";

import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/**
 * The Approvals entry, shown only to somebody the server says is an approver.
 *
 * The answer arrives as a prop from the dashboard layout, which has already
 * read the caller's capabilities while rendering. It used to fetch them itself
 * from the browser after hydration, which put an extra round trip on every
 * navigation and left the badge showing a hard-coded zero whenever the parent
 * did supply the answer.
 */
export function ApprovalsNavItem({
  open,
  isApprover,
  pendingCount = 0,
}: {
  open: boolean;
  isApprover: boolean;
  /** The caller's pending count, when the layout read it. */
  pendingCount?: number;
}) {
  const pathname = usePathname();

  if (!isApprover) return null;

  const isSelected =
    pathname === "/approvals" ||
    pathname.startsWith("/approvals/");

  return (
    <Link
      href="/approvals"
      // Collapsed, the label span is not rendered, so the icon alone would
      // leave the link with no accessible name.
      aria-label="Approvals"
      className={cn(
        "relative flex h-11 w-full items-center rounded-md transition-colors duration-200",
        isSelected
          ? "bg-brand-primary-subtle text-brand-primary shadow-sm border-l-2 border-brand-primary"
          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
      )}
    >
      <div className="grid h-full w-12 place-content-center">
        <ClipboardCheck className="h-4 w-4" />
      </div>
      {open && (
        <span
          className={cn(
            "truncate text-sm font-medium transition-opacity duration-200",
            open ? "opacity-100" : "opacity-0"
          )}
        >
          Approvals
        </span>
      )}
      {open && pendingCount > 0 && (
        <span
          data-testid="approvals-pending-count"
          className="ml-auto mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-primary px-1.5 text-[11px] font-semibold leading-none text-white"
        >
          {pendingCount > 99 ? "99+" : pendingCount}
        </span>
      )}
    </Link>
  );
}
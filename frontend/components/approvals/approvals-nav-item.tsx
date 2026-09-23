"use client";

import Link from "next/link";
import { ClipboardCheck } from "lucide-react";

import { cn } from "@/lib/utils";

import { useCapabilities } from "@/lib/approvals/capabilities-context";

export function ApprovalsNavItem({
  open,
  currentPath,
}: {
  open: boolean;
  currentPath: string;
}) {
  const { capabilities } = useCapabilities();

  if (!capabilities?.is_approver) return null;

  const isSelected =
    currentPath === "/approvals" || currentPath.startsWith("/approvals/");
  const count = capabilities.pending_count;

  return (
    <Link
      href="/approvals"
      aria-label={`Approvals${count > 0 ? `, ${count} pending` : ""}`}
      className={cn(
        "relative flex h-11 w-full items-center rounded-md transition-colors duration-200",
        isSelected
          ? "bg-brand-primary-subtle text-brand-primary shadow-sm border-l-2 border-brand-primary"
          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
      )}
    >
      <div className="grid h-full w-12 shrink-0 place-content-center">
        <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
      </div>

      {open && (
        <>
          <span className="text-sm font-medium">Approvals</span>
          {count > 0 && (
            <span
              className={cn(
                "ml-auto mr-3 inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-brand-primary px-2 text-xs font-semibold text-brand-primary-foreground"
              )}
            >
              {count}
            </span>
          )}
        </>
      )}
    </Link>
  );
}
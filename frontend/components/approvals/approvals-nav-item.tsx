"use client";

import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchCapabilities } from "@/lib/approvals/service";
import { cn } from "@/lib/utils";

export function ApprovalsNavItem({ open }: { open: boolean }) {
  const pathname = usePathname();
  const [caps, setCaps] = useState<{
    is_approver: boolean;
    pending_count: number;
  } | null>(null);

  useEffect(() => {
    let live = true;
    fetchCapabilities().then((next) => {
      if (live) setCaps(next);
    });
    return () => {
      live = false;
    };
  }, [pathname]);

  if (caps !== null && !caps.is_approver) return null;

  const isSelected =
    pathname === "/dashboard/approvals" ||
    pathname.startsWith("/dashboard/approvals/");

  return (
    <Link
      href="/dashboard/approvals"
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
      {open && caps !== null && caps.pending_count > 0 && (
        <span
          data-testid="approvals-pending-count"
          className="ml-auto mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-primary px-1.5 text-[11px] font-semibold leading-none text-white"
        >
          {caps.pending_count > 99 ? "99+" : caps.pending_count}
        </span>
      )}
    </Link>
  );
}
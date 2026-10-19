import type { ComponentType } from "react";

import { FileCheck2, FileText, LayoutDashboard } from "lucide-react";

/**
 * The Documents module's own navigation.
 *
 * This is the employee-facing home of every document the viewer may read: their
 * own supporting documents and the approved leave documents minted for their
 * applications — and, for a team manager or HR, the same documents for the
 * people they cover. The sidebar offers the hub itself plus the two lists, so
 * the three destinations cannot drift from the routes they point at.
 *
 * Follows the shape Leave, Plans, Leave-Configuration, and Workflows
 * established — an item list plus a boundary predicate — so the shell only
 * learns one module-scoping pattern.
 */
export type DocumentsNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

const ROOT = "/dashboard/documents";
const SUPPORTING_ROOT = "/dashboard/documents/supporting";
const APPROVED_ROOT = "/dashboard/documents/approved";

/** Whether `pathname` is `root` itself or something beneath it. */
function under(pathname: string, root: string): boolean {
  return pathname === root || pathname.startsWith(`${root}/`);
}

/** `true` when `pathname` belongs to the Documents module. */
export function isDocumentsModule(pathname: string): boolean {
  return under(pathname, ROOT);
}

export const DOCUMENTS_NAV_ITEMS: DocumentsNavItem[] = [
  {
    label: "Dashboard",
    href: ROOT,
    icon: LayoutDashboard,
    match: (pathname) => pathname === ROOT,
  },
  {
    label: "Supporting Documents",
    href: SUPPORTING_ROOT,
    icon: FileText,
    match: (pathname) => under(pathname, SUPPORTING_ROOT),
  },
  {
    label: "Approved Documents",
    href: APPROVED_ROOT,
    icon: FileCheck2,
    match: (pathname) => under(pathname, APPROVED_ROOT),
  },
];

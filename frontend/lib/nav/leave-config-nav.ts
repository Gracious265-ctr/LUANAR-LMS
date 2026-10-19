import type { ComponentType } from "react";

import { ListChecks, Plus } from "lucide-react";

/**
 * The Leave Configuration module's own navigation (spec 3.5).
 *
 * Two items only — this is a configuration app, not somewhere anyone lives,
 * so the rail is deliberately as short as the spec's list. Follows the shape
 * the Leave and Plans modules established: an item list plus a boundary
 * predicate, so the shell only learns one module-scoping pattern.
 */
export type LeaveConfigNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

/** `true` when `pathname` belongs to the Leave Configuration module. */
export function isLeaveConfigModule(pathname: string): boolean {
  return pathname === "/leave-config" || pathname.startsWith("/leave-config/");
}

const isCreateLeaveType = (pathname: string) =>
  pathname.startsWith("/leave-config/new");

// Everything in the module that is not the create form belongs to "Leave
// Types": the list itself and a single type's edit page, which is the list's
// own row one step further on. `/new` is excluded so exactly one item is lit.
const isLeaveTypes = (pathname: string) =>
  isLeaveConfigModule(pathname) && !isCreateLeaveType(pathname);

export const LEAVE_CONFIG_NAV_ITEMS: LeaveConfigNavItem[] = [
  {
    label: "Leave Types",
    href: "/leave-config",
    icon: ListChecks,
    match: isLeaveTypes,
  },
  {
    label: "Create Leave Type",
    href: "/leave-config/new",
    icon: Plus,
    match: isCreateLeaveType,
  },
];

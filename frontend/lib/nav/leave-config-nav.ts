import type { ComponentType } from "react";

import { CalendarClock, ListChecks, Plus } from "lucide-react";

/**
 * The Leave Configuration module's own navigation (spec 3.5).
 *
 * A deliberately short rail — this is a configuration app, not somewhere
 * anyone lives: the type registry, the annual-days registry, and the create
 * form. Follows the shape the Leave and Plans modules established: an item
 * list plus a boundary predicate, so the shell only learns one module-scoping
 * pattern.
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

const isAnnualDays = (pathname: string) =>
  pathname === "/leave-config/annual-days" ||
  pathname.startsWith("/leave-config/annual-days/");

// Everything in the module that is not the create form or the annual-days
// screen belongs to "Leave Types": the list itself and a single type's edit
// page, which is the list's own row one step further on. `/new` and
// `/annual-days` are excluded so exactly one item is lit.
const isLeaveTypes = (pathname: string) =>
  isLeaveConfigModule(pathname) &&
  !isCreateLeaveType(pathname) &&
  !isAnnualDays(pathname);

export const LEAVE_CONFIG_NAV_ITEMS: LeaveConfigNavItem[] = [
  {
    label: "Leave Types",
    href: "/leave-config",
    icon: ListChecks,
    match: isLeaveTypes,
  },
  {
    label: "Annual Days",
    href: "/leave-config/annual-days",
    icon: CalendarClock,
    match: isAnnualDays,
  },
  {
    label: "Create Leave Type",
    href: "/leave-config/new",
    icon: Plus,
    match: isCreateLeaveType,
  },
];

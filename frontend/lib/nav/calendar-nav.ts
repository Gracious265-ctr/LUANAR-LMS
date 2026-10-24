import type { ComponentType } from "react";

import { CalendarCog } from "lucide-react";

/**
 * The Calendar module's own navigation (refinement unit 07 §3.3).
 *
 * One landing page with in-page tabs — financial years, holidays & events,
 * working days — and the spec is explicit that these are *not* separate
 * sidebar items per concept, the same "don't proliferate nav items" discipline
 * the Leave Plans module follows. So the rail keeps a single entry back to the
 * page and the shared launcher link; the tabs do the rest.
 *
 * Follows the shape the Leave, Plans, Leave-Configuration, Teams,
 * Documents, and Approvals modules established: an item list plus a boundary
 * predicate, so the shell only learns one module-scoping pattern. Without the
 * boundary the Calendar page falls under the HR folio and shows every HR
 * destination beside it.
 */
export type CalendarNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

const CALENDAR_ROOT = "/dashboard/hr-admin/calendar";

/** Whether `pathname` is `root` itself or something beneath it. */
function under(pathname: string, root: string): boolean {
  return pathname === root || pathname.startsWith(`${root}/`);
}

/** `true` when `pathname` belongs to the Calendar module. */
export function isCalendarModule(pathname: string): boolean {
  return under(pathname, CALENDAR_ROOT);
}

export const CALENDAR_NAV_ITEMS: CalendarNavItem[] = [
  {
    label: "Calendar",
    href: CALENDAR_ROOT,
    icon: CalendarCog,
    match: (pathname) => under(pathname, CALENDAR_ROOT),
  },
];

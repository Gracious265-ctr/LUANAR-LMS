import type { ComponentType } from "react";

import { Calendar, FileText, Home } from "lucide-react";

/**
 * The Leave module's own navigation, kept in one place so the sidebar's three
 * destinations cannot drift from the routes they point at.
 *
 * This is the first module to be scoped out of the shared rail. The shape here
 * (an item list plus a boundary predicate) is intended to be reused for the
 * other modules, so the shell only has to learn one pattern.
 */
export type LeaveNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

/** The launcher — the one destination shared by every module. */
export const ALL_APPS_HREF = "/";

/**
 * `true` when `pathname` belongs to the Leave module. The tracking page lives
 * at `/applications/[id]` (outside `/dashboard/leave`) but is still the
 * employee reading one of their own leave applications, so it is part of the
 * module: it shows the Leave rail and lights "My Applications".
 */
export function isLeaveModule(pathname: string): boolean {
  return (
    pathname === "/dashboard/leave" ||
    pathname.startsWith("/dashboard/leave/") ||
    pathname.startsWith("/applications/")
  );
}

const isLeaveIndex = (pathname: string) => pathname === "/dashboard/leave";

// Everything under the module except the bare index and the `/new` redirect
// shim belongs to "My Applications": the list, a draft's edit/review/submitted
// overlays, and the `/applications/[id]` tracking page.
const isMyApplications = (pathname: string) =>
  pathname.startsWith("/applications/") ||
  (pathname.startsWith("/dashboard/leave/") && pathname !== "/dashboard/leave/new");

export const LEAVE_NAV_ITEMS: LeaveNavItem[] = [
  { label: "Dashboard", href: "/dashboard/leave", icon: Home, match: isLeaveIndex },
  {
    label: "My Applications",
    href: "/dashboard/leave/drafts",
    icon: FileText,
    match: isMyApplications,
  },
  {
    // `/dashboard/leave/new` is a redirect shim to the compose overlay, so this
    // item is an action rather than a place: it is never left selected.
    label: "New Application",
    href: "/dashboard/leave/new",
    icon: Calendar,
    match: () => false,
  },
];

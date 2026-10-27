import type { ComponentType } from "react";

import { Calendar, FilePen, FileText, Home, Users } from "lucide-react";

/**
 * The Leave module's own navigation, kept in one place so the sidebar's
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

// Everything that has left the employee's hands: the list (which excludes
// drafts) and any application's tracking page.
const isMyApplications = (pathname: string) =>
  pathname === "/dashboard/leave/applications" ||
  pathname.startsWith("/dashboard/leave/applications/") ||
  pathname.startsWith("/applications/");

// In-progress applications, continued from the Drafts list.
const isDrafts = (pathname: string) =>
  pathname === "/dashboard/leave/drafts" ||
  pathname.startsWith("/dashboard/leave/drafts/");

// Approved leave within the viewer's scope. `isLeaveModule` already claims
// everything under `/dashboard/leave/`.
const isOnLeave = (pathname: string) =>
  pathname === "/dashboard/leave/on-leave" ||
  pathname.startsWith("/dashboard/leave/on-leave/");

export const LEAVE_NAV_ITEMS: LeaveNavItem[] = [
  { label: "Dashboard", href: "/dashboard/leave", icon: Home, match: isLeaveIndex },
  {
    label: "My Applications",
    href: "/dashboard/leave/applications",
    icon: FileText,
    match: isMyApplications,
  },
  {
    label: "Drafts",
    href: "/dashboard/leave/drafts",
    icon: FilePen,
    match: isDrafts,
  },
  {
    label: "On Leave",
    href: "/dashboard/leave/on-leave",
    icon: Users,
    match: isOnLeave,
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

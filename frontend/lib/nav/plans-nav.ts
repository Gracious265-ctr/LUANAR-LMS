import type { ComponentType } from "react";

import { CalendarCheck, Plus, Users } from "lucide-react";

/**
 * The Leave Plans module's own navigation, kept in one place so the sidebar's
 * three destinations cannot drift from the routes they point at.
 *
 * Follows the shape the Leave module established (an item list plus a boundary
 * predicate), so the shell only has to learn one module-scoping pattern.
 */
export type PlansNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

/** `true` when `pathname` belongs to the Leave Plans module. */
export function isPlansModule(pathname: string): boolean {
  return (
    pathname === "/dashboard/plans" || pathname.startsWith("/dashboard/plans/")
  );
}

// The module index and the emailed deep-link detail page both read as "My
// Plans"; only `/new` and `/team` are their own destination.
const isMyPlans = (pathname: string) =>
  pathname === "/dashboard/plans" ||
  (pathname.startsWith("/dashboard/plans/") &&
    !pathname.startsWith("/dashboard/plans/new") &&
    !pathname.startsWith("/dashboard/plans/team"));

const isCreatePlan = (pathname: string) =>
  pathname.startsWith("/dashboard/plans/new");

const isTeamPlans = (pathname: string) =>
  pathname.startsWith("/dashboard/plans/team");

export const PLANS_NAV_ITEMS: PlansNavItem[] = [
  { label: "My Plans", href: "/dashboard/plans", icon: CalendarCheck, match: isMyPlans },
  {
    label: "Create a Plan",
    href: "/dashboard/plans/new",
    icon: Plus,
    match: isCreatePlan,
  },
  { label: "Team Plans", href: "/dashboard/plans/team", icon: Users, match: isTeamPlans },
];

import type { ComponentType } from "react";

import { Building2, ShieldCheck, UserCheck, Users } from "lucide-react";

/**
 * The fields of the signed-in user the module's access decisions read.
 *
 * Declared structurally rather than imported from `api-client`: this module is
 * value-imported by the (client) sidebar, and reaching into `api-client` — even
 * for a type — drags `next/headers`' closure into a guard that forbids it. A
 * `DjangoUser` satisfies this shape, so the pages pass theirs directly.
 */
export type OrganisationViewer = {
  role: string;
  is_superuser?: boolean;
  manages_teams?: boolean;
};

/**
 * Whether `user` administers every team, the way HR does.
 *
 * HR is the role; a superuser is the bootstrap administrator and is admitted
 * the same way the backend's `IsHRRole`/`is_hr` admits them, so an installation
 * is never locked out of its own teams.
 */
export function isOrganisationAdministrator(
  user: OrganisationViewer | null | undefined
): boolean {
  if (!user) {
    return false;
  }
  return user.role === "hr" || user.is_superuser === true;
}

/**
 * Whether `user` may enter the Organisation module at all.
 *
 * HR and superusers administer the whole tree; a team manager reaches only the
 * teams they are flagged for. A manager is an ordinary `employee`, so this is
 * the one predicate the pages share instead of each restating the three roles.
 */
export function canAccessOrganisation(
  user: OrganisationViewer | null | undefined
): boolean {
  if (!user) {
    return false;
  }
  return isOrganisationAdministrator(user) || user.manages_teams === true;
}

/**
 * The Organisation module's own navigation.
 *
 * This is the organisational side of leave: the teams whose applications route
 * through a chain, and the approver roles, campuses, and assignments that chain
 * is built from. It is the app the launcher calls "Teams", reached from the
 * institutional rail's "Teams" entry, with the same one-place-to-configure idea
 * the teams, roles, and campuses screens share.
 *
 * Follows the shape the Leave, Plans, and Leave-Configuration modules
 * established — an item list plus a boundary predicate — so the shell only
 * learns one module-scoping pattern.
 */
export type OrganisationNavItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** Whether `pathname` should mark this item as the active page. */
  match: (pathname: string) => boolean;
};

const TEAMS_ROOT = "/dashboard/teams";
const CAMPUSES_ROOT = "/dashboard/hr-admin/campuses";
const ROLES_ROOT = "/dashboard/hr-admin/roles";
const APPROVERS_ROOT = "/dashboard/hr-admin/approvers";

/** Whether `pathname` is `root` itself or something beneath it. */
function under(pathname: string, root: string): boolean {
  return pathname === root || pathname.startsWith(`${root}/`);
}

/**
 * `true` when `pathname` belongs to the Organisation module.
 *
 * The module is deliberately not contiguous: its Teams land at
 * ``/dashboard/teams`` while the campuses, approver roles, and assignments it
 * administers are the HR surfaces under ``/dashboard/hr-admin``. Both sets are
 * the same module, so crossing into either shows the module rail — and, just as
 * importantly, the HR folio's own landing page at ``/dashboard/hr-admin`` is
 * *not* included, so HR keeps its full rail until they pick a module page.
 */
export function isOrganisationModule(pathname: string): boolean {
  return (
    under(pathname, TEAMS_ROOT) ||
    under(pathname, CAMPUSES_ROOT) ||
    under(pathname, ROLES_ROOT) ||
    under(pathname, APPROVERS_ROOT)
  );
}

const TEAMS_ITEM: OrganisationNavItem = {
  label: "Teams",
  href: TEAMS_ROOT,
  icon: Users,
  match: (pathname) => under(pathname, TEAMS_ROOT),
};

// Campuses, roles, and assignments are institution-wide configuration, so they
// are HR's alone; a team manager is offered only the teams they own.
const HR_ITEMS: OrganisationNavItem[] = [
  {
    label: "Campuses",
    href: CAMPUSES_ROOT,
    icon: Building2,
    match: (pathname) => under(pathname, CAMPUSES_ROOT),
  },
  {
    label: "Approver Roles",
    href: ROLES_ROOT,
    icon: ShieldCheck,
    match: (pathname) => under(pathname, ROLES_ROOT),
  },
  {
    label: "Role Assignments",
    href: APPROVERS_ROOT,
    icon: UserCheck,
    match: (pathname) => under(pathname, APPROVERS_ROOT),
  },
];

export const ORGANISATION_NAV_ITEMS: OrganisationNavItem[] = [TEAMS_ITEM, ...HR_ITEMS];

/**
 * The module's rail for this viewer: everyone in the module sees Teams, while
 * the campuses, roles, and assignments an institution's chains are built from
 * stay with HR. A team manager is an ordinary account whose only claim to the
 * module is their team, so the narrow list is exactly theirs.
 */
export function organisationNavItems({
  isHr,
}: {
  isHr: boolean;
}): OrganisationNavItem[] {
  return isHr ? ORGANISATION_NAV_ITEMS : [TEAMS_ITEM];
}

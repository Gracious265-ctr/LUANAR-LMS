"use client";

import React, { memo, useCallback, useState } from "react";
import {
  ArrowLeftRight,
  Building2,
  Calendar,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ChevronLeft,
  ChevronsRight,
  FileText,
  History,
  Home,
  KeyRound,
  LayoutGrid,
  LogOut,
  Menu,
  ShieldCheck,
  SlidersHorizontal,
  User,
  UserCheck,
  UserCog,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useIsMobile } from "@/lib/hooks/useIsMobile";
import {
  ALL_APPS_HREF,
  isLeaveModule,
  LEAVE_NAV_ITEMS,
} from "@/lib/nav/leave-nav";
import {
  DOCUMENTS_NAV_ITEMS,
  isDocumentsModule,
} from "@/lib/nav/documents-nav";
import { isPlansModule, PLANS_NAV_ITEMS } from "@/lib/nav/plans-nav";
import {
  isLeaveConfigModule,
  LEAVE_CONFIG_NAV_ITEMS,
} from "@/lib/nav/leave-config-nav";
import { isTeamsModule, teamsNavItems } from "@/lib/nav/teams-nav";
import { approvalsNavItems, isApprovalsModule } from "@/lib/nav/approvals-nav";
import { isCalendarModule, CALENDAR_NAV_ITEMS } from "@/lib/nav/calendar-nav";
import { cn } from "@/lib/utils";

import { Navbar1 } from "@/components/ui/navbar-1";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/Avatar";
import { Toaster } from "@/components/ui/toast";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogSurface,
  DialogTitle,
} from "@/components/ui/dialog";

interface User {
  id: number;
  email: string;
  role: string;
  full_name: string;
  /** The bootstrap administrator; unlocks user management. */
  is_superuser?: boolean;
  /**
   * The designated manager of at least one team; unlocks the "My Team" entry.
   * A manager is an ordinary `employee`, so the system role alone cannot say to
   * offer them the Organisation module — this can.
   */
  manages_teams?: boolean;
}

interface DashboardShellProps {
  user: User;
  /** The caller's approver access, resolved by the layout on the server. */
  isApprover: boolean;
  /** Pending approvals for the nav badge; 0 when unknown or not an approver. */
  pendingApprovals: number;
  children: React.ReactNode;
}

const ROLE_LABELS: Record<string, string> = {
  employee: "Employee",
  approver: "Approver",
  hr: "Human Resources",
};

const HR_ROLE = "hr";

const NAV_ID = "dashboard-nav";

export function DashboardShell({
  user,
  isApprover,
  pendingApprovals,
  children,
}: DashboardShellProps) {
  // Two independent states because they answer different questions. `sidebarOpen`
  // is the desktop rail's collapsed/expanded state and is meaningless on a
  // phone; `drawerOpen` is whether the phone's overlay is showing. Collapsing
  // the desktop rail must not close a drawer the user cannot see, and opening a
  // drawer must not un-collapse the rail they left collapsed.
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const isMobile = useIsMobile();

  // Whether the approver desk is available comes from the server, not from the
  // caller's system role: an approver position is held as a team membership or
  // an institution-wide holding, and either can belong to an account whose role
  // reads `employee`. The layout resolves it while rendering, so the sidebar is
  // correct in the first paint instead of appearing after hydration.
  const showHR = user.role === HR_ROLE;
  const showCover = isApprover;
  const showAdmin = user.is_superuser === true;
  // A team manager who is neither HR nor a superuser reaches their team through
  // an entry of its own; HR and superusers already have the "Teams" entry below,
  // so this must not double it up.
  const showTeamManager =
    !showHR && !showAdmin && user.manages_teams === true;

  // A drawer left open across a navigation would sit on top of the page the user
  // just asked for. Radix already handles Escape and the backdrop, and it locks
  // body scroll and traps focus while open; the route change is the one exit
  // Radix cannot see. Adjusting during render rather than in an effect closes it
  // in the same paint as the new page instead of flashing the old route's nav
  // over the new one, and avoids a second render pass.
  const [navPath, setNavPath] = useState(pathname);
  if (pathname !== navPath) {
    setNavPath(pathname);
    setDrawerOpen(false);
  }

  const handleLogout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }, [router]);

  const nav = (
    <>
      <TitleSection open user={user} onDismiss={() => setDrawerOpen(false)} />
      <NavLinks
        currentPath={pathname}
        isApprover={isApprover}
        pendingApprovals={pendingApprovals}
        showCover={showCover}
        showHR={showHR}
        showTeamManager={showTeamManager}
        showAdmin={showAdmin}
        open
      />
    </>
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      <div className="flex h-full min-h-0 w-full bg-surface-page text-text-primary">
        {/* The rail is hidden on a phone rather than rendered narrow: a 64px
            column of icons cannot be labelled, so it would need a second set of
            accessible names for no gain. The drawer carries the same nav. */}
        <div
          className={cn(
            "hidden h-full min-h-0 shrink-0 px-3 py-3 md:block",
            isMobile && "md:hidden"
          )}
        >
          <Sidebar
            open={sidebarOpen}
            setOpen={setSidebarOpen}
            currentPath={pathname}
            user={user}
            isApprover={isApprover}
            pendingApprovals={pendingApprovals}
            showCover={showCover}
            showHR={showHR}
            showTeamManager={showTeamManager}
            showAdmin={showAdmin}
          />
        </div>

        <Drawer open={drawerOpen} onOpenChange={setDrawerOpen} nav={nav} user={user} />

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Navbar1
            user={user}
            onLogout={handleLogout}
            showNavToggle
            onOpenNav={() => setDrawerOpen(true)}
            navOpen={drawerOpen}
            showAllApps
            showNotifications
            showWelcome
          />

          <main className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">{children}</main>
        </div>
      </div>

      {/* One stack for every confirmation in the app; positioned against the
          viewport, so it sits outside the scroll container. */}
      <Toaster />
    </div>
  );
}

/**
 * The phone navigation, as a Radix dialog.
 *
 * Dialog rather than a hand-rolled panel because the behaviour a slide-out menu
 * owes its user is exactly what a modal primitive already solves: a focus trap
 * so Tab cannot wander into the page behind, Escape to dismiss, `aria-modal` so
 * a screen reader stays inside, and a body scroll lock so the page cannot slide
 * under the overlay. Re-implementing that is where drawer bugs come from.
 */
const Drawer = memo(function Drawer({
  open,
  onOpenChange,
  nav,
  user,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  nav: React.ReactNode;
  user: User;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay className="md:hidden" />
        <DialogSurface
          id={NAV_ID}
          // Radix requires a Title and a Description. Both are visually hidden
          // because the nav is the content, but a screen reader still announces
          // what this surface is before the links.
          className={cn(
            "fixed inset-y-4 left-4 flex w-72 max-w-[calc(100vw-2rem)] flex-col rounded-3xl",
            "border border-border-default bg-surface-card p-2 shadow-modal md:hidden",
            "data-[state=open]:animate-in data-[state=open]:slide-in-from-left-2",
            "data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left-2",
          )}
        >
          <DialogTitle className="sr-only">
            Navigation for {user.full_name}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {ROLE_LABELS[user.role] || user.role} account.
          </DialogDescription>
          {nav}
        </DialogSurface>
      </DialogPortal>
    </Dialog>
  );
});

const Sidebar = memo(function Sidebar({
  open,
  setOpen,
  currentPath,
  user,
  isApprover,
  pendingApprovals,
  showCover,
  showHR,
  showTeamManager,
  showAdmin,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  currentPath: string;
  user: User;
  isApprover: boolean;
  pendingApprovals: number;
  showCover: boolean;
  showHR: boolean;
  showTeamManager: boolean;
  showAdmin: boolean;
}) {
  return (
    <nav
      id={NAV_ID}
      className={cn(
        "flex h-full shrink-0 flex-col rounded-3xl border shadow-md transition-[width] duration-200 ease-in-out",
        "border-border-default bg-surface-card p-2",
        open ? "w-64" : "w-16"
      )}
    >
      <TitleSection open={open} user={user} onToggle={() => setOpen(!open)} />
      <NavLinks
        currentPath={currentPath}
        isApprover={isApprover}
        pendingApprovals={pendingApprovals}
        showCover={showCover}
        showHR={showHR}
        showTeamManager={showTeamManager}
        showAdmin={showAdmin}
        open={open}
      />
    </nav>
  );
});

/**
 * The link list, shared by the desktop rail and the phone drawer.
 *
 * One list means the two surfaces cannot drift: a route added here appears in
 * both, and neither can end up offering a destination the other does not.
 * `open` carries the rail's collapsed state; the drawer always passes `true`,
 * since a drawer that collapsed its own labels would be pointless.
 */
const NavLinks = memo(function NavLinks({
  currentPath,
  isApprover,
  pendingApprovals,
  showCover,
  showHR,
  showTeamManager,
  showAdmin,
  open,
}: {
  currentPath: string;
  isApprover: boolean;
  pendingApprovals: number;
  showCover: boolean;
  showHR: boolean;
  showTeamManager: boolean;
  showAdmin: boolean;
  open: boolean;
}) {
  // The Leave, Plans, Leave-Configuration, Teams, Documents, Approvals,
  // and Calendar modules each own their own short rail: a way back to the
  // launcher, then exactly the destinations that belong to that module. Kept
  // out of the institutional rail so the two cannot leak into each other — a
  // module user never sees the HR folio, and HR never sees a truncated list.
  const moduleItems = isLeaveModule(currentPath)
    ? LEAVE_NAV_ITEMS
    : isPlansModule(currentPath)
      ? PLANS_NAV_ITEMS
      : isLeaveConfigModule(currentPath)
        ? LEAVE_CONFIG_NAV_ITEMS
        : isDocumentsModule(currentPath)
          ? DOCUMENTS_NAV_ITEMS
          : isTeamsModule(currentPath)
            ? teamsNavItems({ isHr: showHR || showAdmin })
            : isCalendarModule(currentPath)
              ? CALENDAR_NAV_ITEMS
              : isApprovalsModule(currentPath)
                ? approvalsNavItems({
                    pendingApprovals,
                    canRequestCover: showCover,
                  })
                : null;
  if (moduleItems) {
    return (
      <ModuleNavLinks currentPath={currentPath} open={open} items={moduleItems} />
    );
  }

  return (
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pb-2">
      <Option
        Icon={Home}
        title="Dashboard"
        href="/dashboard"
        currentPath={currentPath}
        open={open}
      />
      <Option
        Icon={FileText}
        title="My Applications"
        href="/dashboard/leave/drafts"
        currentPath={currentPath}
        open={open}
      />
      <Option
        Icon={Calendar}
        title="New Application"
        href="/dashboard/leave/new"
        currentPath={currentPath}
        open={open}
      />
      <Option
        Icon={CalendarClock}
        title="Leave Plans"
        href="/dashboard/plans"
        currentPath={currentPath}
        open={open}
      />
      <ApprovalsNavItem
        open={open}
        isApprover={isApprover}
        pendingCount={pendingApprovals}
      />
      {/* Teams is its own module now, not a page under HR Administration:
          HR reaches it from the rail beside the other top-level apps, and it
          owns its own route at ``/dashboard/teams``. A superuser gets the same
          entry: the backend admits them to every team, and the launcher already
          shows them the module's card. */}
      {(showHR || showAdmin) && (
        <Option
          Icon={Users}
          title="Teams"
          href="/dashboard/teams"
          currentPath={currentPath}
          open={open}
        />
      )}
      {/* A team manager is not HR, so the entry above is hidden from them; this
          is their one way in to the team they are the only person able to
          configure. */}
      {showTeamManager && (
        <Option
          Icon={Users}
          title="My Team"
          href="/dashboard/teams"
          currentPath={currentPath}
          open={open}
        />
      )}
      {showCover && (
        <Option
          Icon={UserCheck}
          title="Request Cover"
          href="/dashboard/cover"
          currentPath={currentPath}
          open={open}
        />
      )}
      {/* Everyone's own account, so it sits below the role-specific items
          rather than inside the HR group: it is the one destination that does
          not depend on what the person can do. */}
      <Option
        Icon={KeyRound}
        title="My Account"
        href="/dashboard/account"
        currentPath={currentPath}
        open={open}
      />
      {showAdmin && (
        <Option
          Icon={ShieldCheck}
          title="HR Users"
          href="/dashboard/admin/users"
          currentPath={currentPath}
          open={open}
        />
      )}
      {showHR && (
        <>
          {open && (
            <div className="px-3 pb-1 pt-3 text-xs font-medium text-text-secondary">
              Human Resources
            </div>
          )}
          <Option
            Icon={ShieldCheck}
            title="HR Administration"
            href="/dashboard/hr-admin"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={User}
            title="Employees"
            href="/dashboard/hr-admin/employees"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={Building2}
            title="Campuses"
            href="/dashboard/hr-admin/campuses"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={UserCheck}
            title="Approvers"
            href="/dashboard/hr-admin/approvers"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={CalendarRange}
            title="Entitlements"
            href="/dashboard/hr-admin/entitlements"
            currentPath={currentPath}
            open={open}
          />
          {/* Leave types became their own module (unit 06): the HR folio keeps
              the way in, and the rail swaps to the module's own two items the
              moment you cross into it. */}
          <Option
            Icon={SlidersHorizontal}
            title="Leave Types"
            href="/leave-config"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={UserCog}
            title="Roles"
            href="/dashboard/hr-admin/roles"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={CalendarDays}
            title="Calendar"
            href="/dashboard/hr-admin/calendar"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={UserCheck}
            title="Delegations"
            href="/dashboard/hr-admin/delegations"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={ArrowLeftRight}
            title="Reassignments"
            href="/dashboard/hr-admin/reassignments"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={FileText}
            title="Document Template"
            href="/dashboard/hr-admin/leave-document-template"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={History}
            title="Audit View"
            href="/dashboard/hr-admin/audit"
            currentPath={currentPath}
            open={open}
          />
        </>
      )}
    </div>
  );
});

/**
 * The rail shared by the self-contained modules (Leave, Plans): a way back to
 * the launcher, then exactly the destinations that belong to the module.
 */
const ModuleNavLinks = memo(function ModuleNavLinks({
  currentPath,
  open,
  items,
}: {
  currentPath: string;
  open: boolean;
  items: readonly {
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    match: (pathname: string) => boolean;
    badge?: number;
  }[];
}) {
  return (
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pb-2">
      {items.map((item) => (
        <Option
          key={item.href}
          Icon={item.icon}
          title={item.label}
          href={item.href}
          currentPath={currentPath}
          match={item.match}
          badge={item.badge}
          open={open}
        />
      ))}
    </div>
  );
});

/** The single path out of a module, back to the launcher. */


const Option = memo(function Option({
  Icon,
  title,
  href,
  currentPath,
  open,
  match,
  badge,
}: {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  href: string;
  currentPath: string;
  open: boolean;
  /** Overrides the default exact-path match when a section owns sub-routes. */
  match?: (pathname: string) => boolean;
  /** A count to surface beside the item, e.g. decisions waiting on the caller. */
  badge?: number;
}) {
  const isSelected = match ? match(currentPath) : currentPath === href;

  return (
    <Link
      href={href}
      // Collapsed, the label span is not rendered, so the icon alone would
      // leave the link with no accessible name.
      aria-label={title}
      // Announced only for module-scoped items (those that pass `match`), so the
      // institutional rail's markup stays exactly as it was.
      aria-current={match && isSelected ? "page" : undefined}
      className={cn(
        "relative flex h-11 w-full items-center rounded-md transition-colors duration-200",
        isSelected
          ? "bg-brand-primary-subtle text-brand-primary shadow-sm border-l-2 border-brand-primary"
          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
      )}
    >
      <div className="grid h-full w-12 place-content-center">
        <Icon className="h-4 w-4" />
      </div>

      {open && (
        <span
          className={cn(
            "text-sm font-medium transition-opacity duration-200",
            open ? "opacity-100" : "opacity-0"
          )}
        >
          {title}
        </span>
      )}

      {open && badge !== undefined && badge > 0 && (
        <span
          data-testid="module-nav-badge"
          className="ml-auto mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-primary px-1.5 text-[11px] font-semibold leading-none text-white"
        >
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </Link>
  );
});

const TitleSection = memo(function TitleSection({
  open,
  user,
  onToggle,
  onDismiss,
}: {
  open: boolean;
  user: User;
  /** Omitted in the drawer, which has no rail to collapse. */
  onToggle?: () => void;
  /** Supplied in the drawer to offer an explicit way out. */
  onDismiss?: () => void;
}) {
  return (
    <div className="mb-6 shrink-0 border-b border-border-default pb-4">
      {open ? (
        <div className="flex items-center justify-between rounded-md p-2 transition-colors hover:bg-surface-hover">
          <div className="flex items-center gap-3">
            <div className="grid size-10 shrink-0 place-content-center rounded-lg bg-brand-primary text-brand-primary-foreground font-medium text-sm">
              L
            </div>

            <div>
              <span className="block text-sm font-semibold text-text-primary">
                {user.full_name}
              </span>
              <span className="block text-xs text-text-muted">
                {ROLE_LABELS[user.role] || user.role}
              </span>
            </div>
          </div>

          {onDismiss ? (
            <Button
              type="button"
              onClick={onDismiss}
              aria-label="Close navigation"
              title="Close navigation"
              variant="ghost"
              size="icon"
              className="h-auto w-auto p-1.5"
            >
              <X className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onToggle}
              aria-label="Hide sidebar"
              title="Hide sidebar"
              variant="ghost"
              size="icon"
              className="h-auto w-auto p-1.5"
            >
              <ChevronsRight className="h-4 w-4 rotate-180" />
            </Button>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center py-1">
          <Button
            type="button"
            onClick={onToggle}
            aria-label="Show sidebar"
            title="Show sidebar"
            variant="ghost"
            size="icon"
            className="size-9"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
});

const Header = memo(function Header({
  user,
  onLogout,
  onOpenNav,
  navOpen,
}: {
  user: User;
  onLogout: () => void;
  onOpenNav: () => void;
  /** Mirrored onto the trigger's `aria-expanded`; the trigger is unmounted
   *  visually while open, but the attribute must not lie when it is not. */
  navOpen: boolean;
}) {
  return (
    <header className="z-header flex items-center justify-between gap-3 border-b border-border-default bg-surface-card px-4 py-3 sm:px-6 sm:py-4">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          aria-expanded={navOpen}
          aria-controls={NAV_ID}
          title="Open navigation"
          variant="ghost"
          size="icon"
          className="size-10 shrink-0 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <Link
          href={ALL_APPS_HREF}
          aria-label="All apps"
          className="inline-flex items-center gap-2 rounded-sm px-2 py-1 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary focus-ring sm:px-3"
        >
          <LayoutGrid className="h-4 w-4" />
          <span className="hidden sm:inline">All Apps</span>
        </Link>

        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold tracking-tight text-text-primary sm:text-xl">
            Leave Management
          </h1>
          <p className="truncate text-sm text-text-secondary">
            Welcome back, {user.full_name}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3 sm:gap-4">
        {/* The name is already in the subheading directly above it, so on a
            phone the duplicate is dropped rather than truncated mid-word. */}
        <div className="hidden items-center gap-3 sm:flex">
          <div className="text-right">
            <p className="text-sm font-medium text-text-primary">{user.full_name}</p>
            <p className="text-xs text-text-muted">{ROLE_LABELS[user.role] || user.role}</p>
          </div>
          <Avatar name={user.full_name} userId={user.id} size="lg" />
        </div>

        {/* Sits beside sign-out rather than in the rail: on a phone the rail is
            a drawer, so a rail-hosted control is only reachable after opening
            it, and the header renders at every breakpoint. */}
        <NotificationBell />

        <ThemeToggle />

        <Button
          onClick={onLogout}
          aria-label="Sign out"
          variant="secondary"
          size="icon"
          className="size-10"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
});
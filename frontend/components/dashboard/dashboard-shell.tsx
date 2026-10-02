"use client";

import React, { memo, useCallback, useState } from "react";
import {
  ArrowLeftRight,
  Calendar,
  CalendarDays,
  CalendarRange,
  ChevronsRight,
  ClipboardList,
  FileText,
  History,
  Home,
  KeyRound,
  LogOut,
  Menu,
  NotebookTabs,
  ShieldCheck,
  Tags,
  User,
  UserCheck,
  UserCog,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useIsMobile } from "@/lib/hooks/useIsMobile";
import { cn } from "@/lib/utils";

import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";
import { PlansNavItem } from "@/components/plans/plans-nav-item";
import { Button } from "@/components/ui/button";
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
}

interface DashboardShellProps {
  user: User;
  /** The caller's approver access, resolved by the layout on the server. */
  isApprover: boolean;
  /** Pending approvals for the nav badge; 0 when unknown or not an approver. */
  pendingApprovals: number;
  /** The caller's reserved blocks awaiting confirmation, for the plans badge. */
  planPendingConfirmations?: number;
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
  planPendingConfirmations,
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
        planPendingConfirmations={planPendingConfirmations}
        showCover={showCover}
        showHR={showHR}
        open
      />
    </>
  );

  return (
    <div className="flex h-screen">
      <div className="flex w-full bg-surface-page text-text-primary">
        {/* The rail is hidden on a phone rather than rendered narrow: a 64px
            column of icons cannot be labelled, so it would need a second set of
            accessible names for no gain. The drawer carries the same nav. */}
        <div className={cn("hidden shrink-0 md:block", isMobile && "md:hidden")}>
          <Sidebar
            open={sidebarOpen}
            setOpen={setSidebarOpen}
            currentPath={pathname}
            user={user}
            isApprover={isApprover}
            pendingApprovals={pendingApprovals}
            planPendingConfirmations={planPendingConfirmations}
            showCover={showCover}
            showHR={showHR}
          />
        </div>

        <Drawer open={drawerOpen} onOpenChange={setDrawerOpen} nav={nav} user={user} />

        <div className="flex-1 flex flex-col overflow-hidden">
          <Header
            user={user}
            onLogout={handleLogout}
            onOpenNav={() => setDrawerOpen(true)}
            navOpen={drawerOpen}
          />
          <main className="flex-1 overflow-auto p-4 sm:p-6">{children}</main>
        </div>
      </div>
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
            "fixed inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col md:hidden",
            "border-r border-border-default bg-surface-card p-2 shadow-modal",
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
  planPendingConfirmations,
  showCover,
  showHR,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  currentPath: string;
  user: User;
  isApprover: boolean;
  pendingApprovals: number;
  planPendingConfirmations?: number;
  showCover: boolean;
  showHR: boolean;
}) {
  return (
    <nav
      id={NAV_ID}
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r transition-[width] duration-200 ease-in-out",
        "border-border-default bg-surface-card p-2",
        open ? "w-64" : "w-16"
      )}
    >
      <TitleSection open={open} user={user} onToggle={() => setOpen(!open)} />
      <NavLinks
        currentPath={currentPath}
        isApprover={isApprover}
        pendingApprovals={pendingApprovals}
        planPendingConfirmations={planPendingConfirmations}
        showCover={showCover}
        showHR={showHR}
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
  planPendingConfirmations,
  showCover,
  showHR,
  open,
}: {
  currentPath: string;
  isApprover: boolean;
  pendingApprovals: number;
  planPendingConfirmations?: number;
  showCover: boolean;
  showHR: boolean;
  open: boolean;
}) {
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
      <PlansNavItem open={open} pendingConfirmations={planPendingConfirmations} />
      <ApprovalsNavItem
        open={open}
        isApprover={isApprover}
        pendingCount={pendingApprovals}
      />
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
            Icon={CalendarRange}
            title="Entitlements"
            href="/dashboard/hr-admin/entitlements"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={ClipboardList}
            title="Leave Rules"
            href="/dashboard/hr-admin/leave-rules"
            currentPath={currentPath}
            open={open}
          />
          <Option
            Icon={Users}
            title="Teams"
            href="/dashboard/hr-admin/teams"
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
            Icon={Tags}
            title="Leave Types"
            href="/dashboard/hr-admin/leave-types"
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
            Icon={NotebookTabs}
            title="Leave Day Plans"
            href="/dashboard/hr-admin/plans"
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

const Option = memo(function Option({
  Icon,
  title,
  href,
  currentPath,
  open,
}: {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  href: string;
  currentPath: string;
  open: boolean;
}) {
  const isSelected = currentPath === href;

  return (
    <Link
      href={href}
      // Collapsed, the label span is not rendered, so the icon alone would
      // leave the link with no accessible name.
      aria-label={title}
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
          <div className="w-9 h-9 rounded-full bg-brand-primary flex items-center justify-center text-brand-primary-foreground font-medium text-sm">
            {user.full_name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .toUpperCase()
              .slice(0, 2)}
          </div>
        </div>

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
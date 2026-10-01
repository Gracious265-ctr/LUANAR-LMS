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
  NotebookTabs,
  ShieldCheck,
  Tags,
  User,
  UserCheck,
  UserCog,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";

import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";
import { PlansNavItem } from "@/components/plans/plans-nav-item";
import { Button } from "@/components/ui/button";

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

export function DashboardShell({
  user,
  isApprover,
  pendingApprovals,
  planPendingConfirmations,
  children,
}: DashboardShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  // Whether the approver desk is available comes from the server, not from the
  // caller's system role: an approver position is held as a team membership or
  // an institution-wide holding, and either can belong to an account whose role
  // reads `employee`. The layout resolves it while rendering, so the sidebar is
  // correct in the first paint instead of appearing after hydration.
  const showHR = user.role === HR_ROLE;
  const showCover = isApprover;

  const handleLogout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }, [router]);

  return (
    <div className="flex h-screen">
      <div className="flex w-full bg-surface-page text-text-primary">
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

        <div className="flex-1 flex flex-col overflow-hidden">
          <Header user={user} onLogout={handleLogout} />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}

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
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r transition-[width] duration-200 ease-in-out",
        "border-border-default bg-surface-card shadow-sm p-2",
        open ? "w-64" : "w-16"
      )}
    >
      <TitleSection open={open} user={user} onToggle={() => setOpen(!open)} />

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

    </nav>
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
}: {
  open: boolean;
  user: User;
  onToggle: () => void;
}) {
  return (
    <div className="mb-6 shrink-0 border-b border-border-default pb-4">
      {open ? (
        <div className="flex items-center justify-between rounded-md p-2 transition-colors hover:bg-surface-hover">
          <div className="flex items-center gap-3">
            <div className="grid size-10 shrink-0 place-content-center rounded-lg bg-brand-primary text-brand-primary-foreground font-medium text-sm shadow-sm">
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

          <Button type="button" onClick={onToggle} aria-label="Hide sidebar" title="Hide sidebar" variant="ghost" size="icon" className="h-auto w-auto p-1.5">
            <ChevronsRight className="h-4 w-4 rotate-180" />
          </Button>
        </div>
      ) : (
        <div className="flex flex-col items-center py-1">
          <Button type="button" onClick={onToggle} aria-label="Show sidebar" title="Show sidebar" variant="ghost" size="icon" className="size-9">
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
}: {
  user: User;
  onLogout: () => void;
}) {
  return (
    <header className="flex items-center justify-between px-6 py-4 bg-surface-card border-b border-border-default shadow-subtle">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-text-primary">Leave Management</h1>
        <p className="text-sm text-text-secondary">Welcome back, {user.full_name}</p>
      </div>
      <div className="flex items-center gap-4">
        <Button onClick={onLogout} aria-label="Sign out" variant="secondary" size="icon" className="size-10 rounded-lg">
          <LogOut className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-3">
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
      </div>
    </header>
  );
});
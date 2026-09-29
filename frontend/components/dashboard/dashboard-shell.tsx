"use client";

import React, { memo, useCallback, useState } from "react";
import {
  ArrowLeftRight,
  Building2,
  Calendar,
  CalendarCheck2,
  CalendarDays,
  CalendarRange,
  ChevronsRight,
  ClipboardList,
  FileText,
  History,
  Home,
  LogOut,
  ShieldCheck,
  Tags,
  User,
  UserCheck,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";

import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";

interface User {
  id: number;
  email: string;
  role: string;
  full_name: string;
}

interface DashboardShellProps {
  user: User;
  children: React.ReactNode;
}

const ROLE_LABELS: Record<string, string> = {
  employee: "Employee",
  supervisor: "Supervisor",
  hod: "Head of Department",
  dean: "Dean",
  registrar: "Registrar",
  dvc: "Deputy Vice-Chancellor",
  hr: "Human Resources",
};

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];
const HOD_AND_ABOVE = ["hod", "dean", "registrar", "dvc"];
const HR_ROLE = "hr";

export function DashboardShell({ user, children }: DashboardShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const showApprovals = APPROVER_ROLES.includes(user.role);
  const showDepartment = HOD_AND_ABOVE.includes(user.role);
  const showHR = user.role === HR_ROLE;
  // HR may also hold a delegation, matching the backend's approver-or-HR rule
  // for the cover endpoints, even though it is not in APPROVER_ROLES.
  const showCover = showApprovals || showHR;

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
          showApprovals={showApprovals}
          showDepartment={showDepartment}
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
  showApprovals,
  showDepartment,
  showCover,
  showHR,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  currentPath: string;
  user: User;
  showApprovals: boolean;
  showDepartment: boolean;
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
        <Option
          Icon={CalendarCheck2}
          title="Plans"
          href="/dashboard/plans"
          currentPath={currentPath}
          open={open}
        />
        {showApprovals && <ApprovalsNavItem open={open} />}
        {showCover && (
          <Option
            Icon={UserCheck}
            title="Request Cover"
            href="/dashboard/cover"
            currentPath={currentPath}
            open={open}
          />
        )}
        {showDepartment && (
          <Option
            Icon={Building2}
            title="Department"
            href="/dashboard/department"
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
              Icon={Workflow}
              title="Workflows"
              href="/dashboard/hr-admin/workflows"
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
              Icon={History}
              title="Audit View"
              href="/dashboard/hr-admin/audit"
              currentPath={currentPath}
              open={open}
            />
            <Option
              Icon={CalendarCheck2}
              title="Plan Settings"
              href="/dashboard/plans/settings"
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

          <button
            type="button"
            onClick={onToggle}
            aria-label="Hide sidebar"
            title="Hide sidebar"
            className="rounded-md p-1.5 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
          >
            <ChevronsRight className="h-4 w-4 rotate-180" />
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center py-1">
          <button
            type="button"
            onClick={onToggle}
            aria-label="Show sidebar"
            title="Show sidebar"
            className="grid size-9 place-content-center rounded-md text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
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
        <button
          onClick={onLogout}
          aria-label="Sign out"
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-surface-card text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
        >
          <LogOut className="h-4 w-4" />
        </button>
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
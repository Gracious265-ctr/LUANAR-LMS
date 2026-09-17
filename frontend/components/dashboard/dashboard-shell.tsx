"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Bell,
  Calendar,
  ChevronDown,
  ChevronsRight,
  FileText,
  Home,
  LogOut,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

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

function getSelectedTitle(pathname: string): string {
  if (pathname === "/dashboard") return "Dashboard";
  if (pathname.startsWith("/dashboard/leave/drafts")) return "My Applications";
  if (pathname.startsWith("/dashboard/leave")) return "New Application";
  if (pathname.startsWith("/dashboard/approvals")) return "Approvals";
  if (pathname.startsWith("/dashboard/department")) return "Department";
  if (pathname.startsWith("/dashboard/hr-admin")) return "HR Administration";
  if (pathname.startsWith("/dashboard/settings")) return "Settings";
  return "Dashboard";
}

export function DashboardShell({ user, children }: DashboardShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDark, setIsDark] = useState(false);
  const pathname = usePathname();

  const showApprovals = APPROVER_ROLES.includes(user.role);
  const showDepartment = HOD_AND_ABOVE.includes(user.role);
  const showHR = user.role === HR_ROLE;

  useEffect(() => {
    const stored = localStorage.getItem("luanar-dark-mode");
    if (stored !== null) {
      setIsDark(stored === "true");
    } else {
      setIsDark(window.matchMedia("(prefers-color-scheme: dark)").matches);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("luanar-dark-mode", String(isDark));
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  return (
    <div className="flex h-screen">
      <div className="flex w-full bg-surface-page text-text-primary">
        <Sidebar
          open={sidebarOpen}
          setOpen={setSidebarOpen}
          pathname={pathname}
          user={user}
          showApprovals={showApprovals}
          showDepartment={showDepartment}
          showHR={showHR}
        />

        <div className="flex-1 flex flex-col overflow-hidden">
          <Header
            user={user}
            isDark={isDark}
            setIsDark={setIsDark}
          />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}

function Sidebar({
  open,
  setOpen,
  pathname,
  user,
  showApprovals,
  showDepartment,
  showHR,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  pathname: string;
  user: User;
  showApprovals: boolean;
  showDepartment: boolean;
  showHR: boolean;
}) {
  const selected = getSelectedTitle(pathname);

  return (
    <nav
      className={cn(
        "sticky top-0 h-screen shrink-0 border-r transition-all duration-300 ease-in-out",
        "border-border-default bg-surface-card shadow-sm p-2",
        open ? "w-64" : "w-16"
      )}
    >
      <TitleSection open={open} user={user} />

      <div className="space-y-1 mb-8">
        <Option
          Icon={Home}
          title="Dashboard"
          href="/dashboard"
          selected={selected}
          open={open}
        />
        <Option
          Icon={FileText}
          title="My Applications"
          href="/dashboard/leave/drafts"
          selected={selected}
          open={open}
        />
        <Option
          Icon={Calendar}
          title="New Application"
          href="/dashboard/leave/new"
          selected={selected}
          open={open}
        />
        {showApprovals && (
          <Option
            Icon={ShieldCheck}
            title="Approvals"
            href="/dashboard/approvals"
            selected={selected}
            open={open}
          />
        )}
        {showDepartment && (
          <Option
            Icon={Users}
            title="Department"
            href="/dashboard/department"
            selected={selected}
            open={open}
          />
        )}
        {showHR && (
          <Option
            Icon={Users}
            title="HR Administration"
            href="/dashboard/hr-admin"
            selected={selected}
            open={open}
          />
        )}
      </div>

      {open && (
        <div className="border-t border-border-default pt-4 space-y-1">
          <div className="px-3 py-2 text-xs font-medium text-text-muted uppercase tracking-wide">
            Account
          </div>
          <Option
            Icon={Settings}
            title="Settings"
            href="/dashboard/settings"
            selected={selected}
            open={open}
          />
        </div>
      )}

      <ToggleClose open={open} setOpen={setOpen} />
    </nav>
  );
}

function Option({
  Icon,
  title,
  href,
  selected,
  open,
}: {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  href: string;
  selected: string;
  open: boolean;
}) {
  const isSelected = selected === title;

  return (
    <Link
      href={href}
      className={cn(
        "relative flex h-11 w-full items-center rounded-md transition-all duration-200",
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
}

function TitleSection({ open, user }: { open: boolean; user: User }) {
  return (
    <div className="mb-6 border-b border-border-default pb-4">
      <div className="flex cursor-pointer items-center justify-between rounded-md p-2 transition-colors hover:bg-surface-hover">
        <div className="flex items-center gap-3">
          <div className="grid size-10 shrink-0 place-content-center rounded-lg bg-brand-primary text-brand-primary-foreground font-bold text-sm shadow-sm">
            L
          </div>

          {open && (
            <div className={cn("transition-opacity duration-200", open ? "opacity-100" : "opacity-0")}>
              <div className="flex items-center gap-2">
                <div>
                  <span className="block text-sm font-semibold text-text-primary">
                    {user.full_name}
                  </span>
                  <span className="block text-xs text-text-muted">
                    {ROLE_LABELS[user.role] || user.role}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
        {open && (
          <ChevronDown className="h-4 w-4 text-text-muted" />
        )}
      </div>
    </div>
  );
}

function ToggleClose({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => setOpen(!open)}
      className="absolute bottom-0 left-0 right-0 border-t border-border-default transition-colors hover:bg-surface-hover"
    >
      <div className="flex items-center p-3">
        <div className="grid size-10 place-content-center">
          <ChevronsRight
            className={cn(
              "h-4 w-4 transition-transform duration-300 text-text-muted",
              open ? "rotate-180" : ""
            )}
          />
        </div>
        {open && (
          <span
            className={cn(
              "text-sm font-medium text-text-secondary transition-opacity duration-200",
              open ? "opacity-100" : "opacity-0"
            )}
          >
            Hide
          </span>
        )}
      </div>
    </button>
  );
}

function Header({
  user,
  isDark,
  setIsDark,
}: {
  user: User;
  isDark: boolean;
  setIsDark: (v: boolean) => void;
}) {
  return (
    <header className="flex items-center justify-between px-6 py-4 bg-surface-card  shadow-subtle">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Leave Management</h1>
        <p className="text-sm text-text-secondary">Welcome back, {user.full_name}</p>
      </div>
      <div className="flex items-center gap-4">
        <button className="relative p-2 rounded-lg bg-surface-card border border-border-default text-text-secondary hover:text-text-primary transition-colors">
          <Bell className="h-5 w-5" />
          <span className="absolute -top-1 -right-1 h-3 w-3 bg-status-rejected rounded-full" />
        </button>
        <button
          onClick={() => setIsDark(!isDark)}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-surface-card text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
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
}

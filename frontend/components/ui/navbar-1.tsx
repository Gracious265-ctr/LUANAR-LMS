"use client";

import * as React from "react";
import { memo, useState } from "react";
import { GraduationCap, LayoutGrid, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogSurface,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { PasswordChangeForm } from "@/components/account/password-change-form";
import { ThemeToggle } from "@/components/theme-toggle";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { cn } from "@/lib/utils";

const ROLE_LABELS: Record<string, string> = {
  employee: "Employee",
  approver: "Approver",
  hr: "Human Resources",
};

const ALL_APPS_HREF = "/";

interface NavbarUser {
  id: number;
  email: string;
  role: string;
  full_name: string;
  is_superuser?: boolean;
  manages_teams?: boolean;
}

interface Navbar1Props {
  user?: NavbarUser;
  onLogout?: () => void;
  showNavToggle?: boolean;
  onOpenNav?: () => void;
  navOpen?: boolean;
  showAllApps?: boolean;
  showNotifications?: boolean;
  showWelcome?: boolean;
  className?: string;
}

const Navbar1 = memo(function Navbar1({
  user,
  onLogout,
  showNavToggle = false,
  onOpenNav,
  navOpen = false,
  showAllApps = true,
  showNotifications,
  showWelcome = false,
  className,
}: Navbar1Props) {
  const pathname = usePathname();
  return (
    <AppNavbar
      user={user}
      onLogout={onLogout}
      showNavToggle={showNavToggle}
      onOpenNav={onOpenNav}
      navOpen={navOpen}
      showAllApps={showAllApps && pathname !== "/"}
      showNotifications={showNotifications ?? pathname === "/"}
      showWelcome={showWelcome}
      className={className}
    />
  );
});

function AppNavbar({
  user,
  onLogout,
  showNavToggle = false,
  onOpenNav,
  navOpen = false,
  showAllApps = true,
  showNotifications = false,
  showWelcome = false,
  className,
}: Pick<
  Navbar1Props,
  | "user"
  | "onLogout"
  | "showNavToggle"
  | "onOpenNav"
  | "navOpen"
  | "showAllApps"
  | "showNotifications"
  | "showWelcome"
  | "className"
>) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [passwordChangeOpen, setPasswordChangeOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  const handleLogout = () => {
    setMenuOpen(false);
    onLogout?.();
  };

  return (
    <header className={cn("z-header w-full px-4 pb-3 pt-6 sm:px-6", className)}>
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-2 rounded-full border border-border-default bg-surface-card px-3 py-3 shadow-md sm:gap-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          {showNavToggle && onOpenNav && (
            <Button
              type="button"
              onClick={onOpenNav}
              aria-label="Open navigation"
              aria-expanded={navOpen}
              aria-controls="dashboard-nav"
              title="Open navigation"
              variant="ghost"
              size="icon"
              className="size-10 shrink-0 md:hidden"
            >
              <Menu className="size-5" aria-hidden="true" />
            </Button>
          )}
          <Link
            href="/"
            aria-label="LUANAR Leave Management System"
            className="flex min-w-0 items-center gap-2 rounded-full focus-ring sm:gap-3"
          >
            <motion.span
              initial={reduceMotion ? false : { scale: 0.85 }}
              animate={{ scale: 1 }}
              whileHover={reduceMotion ? undefined : { rotate: 8 }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-primary text-brand-primary-foreground"
              aria-hidden="true"
            >
              <GraduationCap className="size-5" />
            </motion.span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-text-primary sm:text-base">
                LUANAR
              </span>
              <span className="hidden text-xs text-text-secondary sm:block">
                Leave Management System
              </span>
            </span>
          </Link>
        </div>

        <div className="flex shrink-0 items-center">
          {showAllApps && (
            <Link
              href={ALL_APPS_HREF}
              aria-label="All Apps"
              className="inline-flex size-10 items-center justify-center gap-2 rounded-full bg-surface-hover text-sm font-medium text-text-primary transition-colors hover:bg-surface-active focus-ring sm:w-auto sm:px-4"
            >
              <LayoutGrid className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">All Apps</span>
            </Link>
          )}
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
          {user && (
            <Popover open={profileOpen} onOpenChange={setProfileOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  aria-label={`Open profile for ${user.full_name}`}
                  className="hidden items-center gap-3 rounded-full p-1 text-left transition-colors hover:bg-surface-hover focus-ring md:flex"
                >
                  <span className="max-w-40 text-right">
                    {showWelcome && (
                      <span className="block text-xs text-text-muted">
                        Welcome back
                      </span>
                    )}
                    <span className="block truncate text-sm font-medium text-text-primary">
                      {user.full_name}
                    </span>
                    <span className="block text-xs text-text-muted">
                      {ROLE_LABELS[user.role] || user.role}
                    </span>
                  </span>
                  <Avatar name={user.full_name} userId={user.id} />
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-80 rounded-xl p-0 shadow-lg">
                <div className="flex items-center gap-3 border-b border-border-default p-4">
                  <Avatar name={user.full_name} userId={user.id} size="lg" />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-text-primary">
                      {user.full_name}
                    </p>
                    <p className="truncate text-sm text-text-secondary">
                      {user.email}
                    </p>
                    <p className="text-xs text-text-muted">
                      {ROLE_LABELS[user.role] || user.role}
                    </p>
                  </div>
                </div>
                <div className="p-3">
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full justify-start"
                    onClick={() => {
                      setProfileOpen(false);
                      setPasswordChangeOpen(true);
                    }}
                  >
                    Change password
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          )}

          {showNotifications && <NotificationBell />}

          <ThemeToggle />

          {onLogout && (
            <Button
              type="button"
              onClick={onLogout}
              aria-label="Sign out"
              title="Sign out"
              variant="secondary"
              size="icon"
              className="hidden size-10 sm:inline-flex"
            >
              <LogOut className="size-4" aria-hidden="true" />
            </Button>
          )}

          <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
            <DialogTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-10 sm:hidden"
                aria-label="Open account menu"
                title="Open account menu"
              >
                {user ? (
                  <Avatar
                    name={user.full_name}
                    userId={user.id}
                    className="size-8"
                  />
                ) : (
                  <Menu className="size-5" aria-hidden="true" />
                )}
              </Button>
            </DialogTrigger>
            <DialogPortal>
              <DialogOverlay className="sm:hidden" />
              <DialogSurface
                className={cn(
                  "fixed inset-0 flex flex-col bg-surface-card p-6 shadow-modal sm:hidden",
                  "data-[state=open]:animate-in data-[state=open]:slide-in-from-right-2",
                  "data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right-2",
                  "motion-reduce:animate-none"
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <DialogTitle className="text-lg font-semibold text-text-primary">
                      Account
                    </DialogTitle>
                    <DialogDescription className="mt-1">
                      Account and appearance settings.
                    </DialogDescription>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Close account menu"
                    onClick={() => setMenuOpen(false)}
                    className="size-10 shrink-0"
                  >
                    <X className="size-5" aria-hidden="true" />
                  </Button>
                </div>

                {user && (
                  <div className="mt-8 flex items-center gap-3 rounded-xl bg-surface-muted p-4">
                    <Avatar name={user.full_name} userId={user.id} size="lg" />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-text-primary">
                        {user.full_name}
                      </p>
                      <p className="truncate text-sm text-text-secondary">
                        {user.email}
                      </p>
                      <p className="text-xs text-text-muted">
                        {ROLE_LABELS[user.role] || user.role}
                      </p>
                    </div>
                  </div>
                )}

                <div className="mt-6 flex flex-col gap-3">
                  {user && (
                    <Button
                      type="button"
                      variant="secondary"
                      className="min-h-12 w-full justify-start"
                      onClick={() => {
                        setMenuOpen(false);
                        setPasswordChangeOpen(true);
                      }}
                    >
                      Change password
                    </Button>
                  )}
                  <div className="flex items-center justify-between rounded-xl border border-border-default px-4 py-2">
                    <span className="text-sm font-medium text-text-primary">
                      Appearance
                    </span>
                    <ThemeToggle />
                  </div>

                  {onLogout && (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={handleLogout}
                      className="min-h-12 w-full justify-center"
                    >
                      <LogOut className="size-4" aria-hidden="true" />
                      Sign out
                    </Button>
                  )}
                </div>
              </DialogSurface>
            </DialogPortal>
          </Dialog>
        </div>
      </div>
      <Dialog open={passwordChangeOpen} onOpenChange={setPasswordChangeOpen}>
        <DialogContent
          scrollable
          className="max-h-[calc(100dvh-2rem)] max-w-2xl"
          scrollClassName="p-4 sm:p-6"
        >
          <DialogTitle className="sr-only">Change your password</DialogTitle>
          <DialogDescription className="sr-only">
            Enter your current password and choose a new password.
          </DialogDescription>
          <PasswordChangeForm />
        </DialogContent>
      </Dialog>
    </header>
  );
}

export { Navbar1 };

"use client";

import Image from "next/image";
import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/toast";
import { ThemeToggle } from "@/components/theme-toggle";
import type { DjangoUser } from "@/lib/api-client";

/**
 * The launcher's own shell.
 *
 * Deliberately not `DashboardShell`: the launcher is the entry point to every
 * app, so wrapping it in the leave module's sidebar would present one app's
 * navigation before the visitor has chosen an app. This keeps only the chrome
 * that belongs to the account itself — identity, theme, sign-out.
 */
const ROLE_LABELS: Record<string, string> = {
  employee: "Employee",
  approver: "Approver",
  hr: "Human Resources",
};

export function LauncherShell({
  user,
  children,
}: {
  user: DjangoUser;
  children: React.ReactNode;
}) {
  const router = useRouter();

  const handleLogout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-border-default bg-surface-card">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Image
              src="/logo.webp"
              alt="LUANAR"
              width={112}
              height={112}
              priority
              className="h-9 w-auto"
            />
            <span className="text-lg font-semibold tracking-tight text-text-primary">
              LUANAR Leave Management
            </span>
          </div>

          <div className="flex shrink-0 items-center gap-3 sm:gap-4">
            <div className="hidden items-center gap-3 sm:flex">
              <div className="text-right">
                <p className="text-sm font-medium text-text-primary">
                  {user.full_name}
                </p>
                <p className="text-xs text-text-muted">
                  {ROLE_LABELS[user.role] || user.role}
                </p>
              </div>
              <Avatar name={user.full_name} userId={user.id} size="md" />
            </div>

            <Button
              onClick={handleLogout}
              aria-label="Sign out"
              variant="secondary"
              size="icon"
              className="size-10"
            >
              <LogOut className="h-4 w-4" />
            </Button>

            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <Toaster />
    </div>
  );
}

"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { Navbar1 } from "@/components/ui/navbar-1";
import { Toaster } from "@/components/ui/toast";
import type { DjangoUser } from "@/lib/api-client";

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
      <Navbar1 user={user} onLogout={handleLogout} showAllApps={true} />
      <main className="flex-1">{children}</main>
      <Toaster />
    </div>
  );
}


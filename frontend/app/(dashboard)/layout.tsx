import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

/**
 * Auth guard for everything behind the sign-in wall. Each child renders its
 * own shell: the legacy `/dashboard/**` tree uses `DashboardShell`
 * (`dashboard/layout.tsx`) and each restructured module root renders a
 * module-scoped `ModuleShell` from its own layout.
 */
export default async function DashboardGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return <>{children}</>;
}

import { redirect } from "next/navigation";

import { LauncherShell } from "@/components/launcher/launcher-shell";
import { getCurrentUser } from "@/lib/auth";

export default async function LauncherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return <LauncherShell user={user}>{children}</LauncherShell>;
}

"use client";

import { Calendar, FileEdit } from "lucide-react";
import { ModuleShell, type NavItem } from "@/components/module-shell";

const navItems: NavItem[] = [
  { href: "/leave", label: "My Leave", icon: Calendar },
  { href: "/leave/drafts", label: "Drafts", icon: FileEdit },
  { href: "/leave/new", label: "New Application", icon: FileEdit },
];

export default function LeaveLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ModuleShell navItems={navItems} moduleName="Leave">
      {children}
    </ModuleShell>
  );
}

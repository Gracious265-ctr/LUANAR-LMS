"use client";

import { FileStack } from "lucide-react";
import { ModuleShell, type NavItem } from "@/components/module-shell";

const navItems: NavItem[] = [
  { href: "/documents", label: "Documents", icon: FileStack },
];

export default function DocumentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ModuleShell navItems={navItems} moduleName="Documents">
      {children}
    </ModuleShell>
  );
}

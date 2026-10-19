"use client";

import {
  Building2,
  ShieldCheck,
  UserCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

import { ModuleShell, type NavItem } from "@/components/module-shell";

export type ServerNavItem = {
  href: string;
  label: string;
  iconName: "Users" | "Building2" | "ShieldCheck" | "UserCheck";
};

const iconMap: Record<ServerNavItem["iconName"], LucideIcon> = {
  Users,
  Building2,
  ShieldCheck,
  UserCheck,
};

export function OrganisationLayoutClient({
  children,
  navItems,
}: {
  children: React.ReactNode;
  navItems: ServerNavItem[];
}) {
  const clientNavItems: NavItem[] = navItems.map((item) => ({
    href: item.href,
    label: item.label,
    icon: iconMap[item.iconName as keyof typeof iconMap],
  }));

  return (
    <ModuleShell navItems={clientNavItems} moduleName="Organisation">
      {children}
    </ModuleShell>
  );
}

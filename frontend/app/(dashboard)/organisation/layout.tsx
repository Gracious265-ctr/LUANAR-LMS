import { Building2, Users } from "lucide-react";
import { ModuleShell, type NavItem } from "@/components/module-shell";

const navItems: NavItem[] = [
  { href: "/org", label: "Organization", icon: Building2 },
  { href: "/teams", label: "Teams", icon: Users },
];

export default function OrgLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ModuleShell navItems={navItems} moduleName="Organization">
      {children}
    </ModuleShell>
  );
}

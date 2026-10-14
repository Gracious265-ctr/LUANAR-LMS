import { Users, Settings } from "lucide-react";
import { ModuleShell, type NavItem } from "@/components/module-shell";

const navItems: NavItem[] = [
  { href: "/hr-admin", label: "HR Dashboard", icon: Settings },
  { href: "/hr-admin/employees", label: "Employees", icon: Users },
];

export default function HRAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ModuleShell navItems={navItems} moduleName="HR Administration">
      {children}
    </ModuleShell>
  );
}

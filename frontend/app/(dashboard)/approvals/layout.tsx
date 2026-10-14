import { CheckCircle } from "lucide-react";
import { ModuleShell, type NavItem } from "@/components/module-shell";

const navItems: NavItem[] = [
  { href: "/approvals", label: "Approvals Queue", icon: CheckCircle },
];

export default function ApprovalsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ModuleShell navItems={navItems} moduleName="Approvals">
      {children}
    </ModuleShell>
  );
}

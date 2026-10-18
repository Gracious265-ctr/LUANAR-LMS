import { getCurrentUser } from "@/lib/auth";
import { OrganisationLayoutClient, type ServerNavItem } from "./layout-client";

export default async function OrganisationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  const isHr = user?.role === "hr";

  const navItems: ServerNavItem[] = [
    { href: "/organisation/teams", label: "Teams", iconName: "Users" as const },
    ...(isHr
      ? ([
          {
            href: "/organisation/campuses",
            label: "Campuses",
            iconName: "Building2" as const,
          },
          {
            href: "/organisation/roles",
            label: "Approver Roles",
            iconName: "ShieldCheck" as const,
          },
          {
            href: "/organisation/approvers",
            label: "Role Assignments",
            iconName: "UserCheck" as const,
          },
        ] as ServerNavItem[])
      : []),
  ];

  return (
    <OrganisationLayoutClient navItems={navItems}>
      {children}
    </OrganisationLayoutClient>
  );
}

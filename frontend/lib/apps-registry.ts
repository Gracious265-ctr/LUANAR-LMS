import { Calendar, ShieldCheck, Building2, FileStack, Users } from "lucide-react";

export const APPS_REGISTRY = {
  leave: {
    name: "Leave Applications",
    description: "Submit and track your leave requests",
    icon: Calendar,
    route: "/dashboard/leave",
  },
  approvals: {
    name: "Approvals",
    description: "Review and decide on leave requests assigned to you",
    icon: ShieldCheck,
    route: "/dashboard/approvals",
  },
  org: {
    name: "Organization",
    description: "Manage units, approvers, and teams",
    icon: Building2,
    route: "/dashboard/hr-admin/teams",
  },
  documents: {
    name: "Documents",
    description: "Manage supporting documents",
    icon: FileStack,
    route: "/dashboard/hr-admin/leave-document-template",
  },
  "hr-admin": {
    name: "HR Administration",
    description: "Manage employees, grades, and leave rules",
    icon: Users,
    route: "/dashboard/hr-admin",
  },
} as const;

export type AppKey = keyof typeof APPS_REGISTRY;

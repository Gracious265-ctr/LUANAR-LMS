import { Calendar, ShieldCheck, Building2, FileStack, Users } from "lucide-react";

// Each app now points at its own module root; the legacy `/dashboard/**`
// pages are kept working through `next.config.ts` redirects.
export const APPS_REGISTRY = {
  leave: {
    name: "Leave Applications",
    description: "Submit and track your leave requests",
    icon: Calendar,
    route: "/leave",
  },
  approvals: {
    name: "Approvals",
    description: "Review and decide on leave requests assigned to you",
    icon: ShieldCheck,
    route: "/approvals",
  },
  organisation: {
    name: "Organisation",
    description: "Manage units, approvers, and teams",
    icon: Building2,
    route: "/organisation",
  },
  documents: {
    name: "Documents",
    description: "Manage supporting documents",
    icon: FileStack,
    route: "/documents",
  },
  "hr-admin": {
    name: "HR Administration",
    description: "Manage employees, grades, and leave rules",
    icon: Users,
    route: "/hr-admin",
  },
} as const;

export type AppKey = keyof typeof APPS_REGISTRY;

import {
  Calendar,
  CalendarClock,
  ShieldCheck,
  Building2,
  FileStack,
  SlidersHorizontal,
} from "lucide-react";

export const APPS_REGISTRY = {
  leave: {
    name: "Leave Applications",
    description: "Submit and track your leave requests",
    icon: Calendar,
    route: "/dashboard/leave",
  },
  plans: {
    name: "Leave Plans",
    description: "Plan your upcoming leave ahead of time",
    icon: CalendarClock,
    route: "/dashboard/plans",
  },
  approvals: {
    name: "Approvals",
    description: "Review and decide on leave requests assigned to you",
    icon: ShieldCheck,
    route: "/dashboard/approvals",
  },
  org: {
    name: "Teams",
    description: "Manage teams, campuses, approver roles, and their approval chains",
    icon: Building2,
    route: "/dashboard/teams",
  },
  documents: {
    name: "Documents",
    description: "Find your supporting and approved leave documents",
    icon: FileStack,
    route: "/dashboard/documents",
  },
  "leave-config": {
    name: "Leave Configuration",
    description: "Manage leave types and their rules",
    icon: SlidersHorizontal,
    route: "/leave-config",
  },
} as const;

export type AppKey = keyof typeof APPS_REGISTRY;

/**
 * The HR setup spine, as the backend reports it.
 *
 * Completion is derived from live data on the server, never stored, so the hub
 * renders the same truth an existing install already satisfies — nothing here
 * asks HR to redo configuration that is already in place.
 *
 * This module is imported by the client-side :file:`SetupHub`, so it must stay
 * pure: the server fetchers live in the sibling :mod:`setup-server`.
 */
export type SetupStepKey =
  | "financial_year"
  | "leave_types"
  | "entitlements"
  | "roles"
  | "teams";

export interface SetupStep {
  done: boolean;
  count: number;
}

export interface SetupStatus {
  steps: Record<SetupStepKey, SetupStep>;
  complete: boolean;
}

export interface SetupTemplateSection {
  name: string;
  approver_role: string;
}

export interface SetupTemplate {
  key: string;
  label: string;
  description: string;
  sections: SetupTemplateSection[];
}

export interface SetupTemplatesResponse {
  templates: SetupTemplate[];
}

export interface ApplyResult {
  created: Record<string, number>;
  skipped: Record<string, number>;
  total_created: number;
  dry_run: boolean;
}

/** The ordered path HR walks, with where each step is configured by hand. */
export const SETUP_STEPS: {
  key: SetupStepKey;
  title: string;
  description: string;
  href: string;
}[] = [
  {
    key: "financial_year",
    title: "Open a financial year",
    description:
      "Leave is validated against the active 1 July – 30 June financial year.",
    href: "/dashboard/hr-admin/calendar",
  },
  {
    key: "leave_types",
    title: "Add the leave types",
    description: "The categories staff can apply for, such as annual or maternity.",
    href: "/dashboard/hr-admin/leave-types",
  },
  {
    key: "entitlements",
    title: "Set grade entitlements",
    description: "How many annual leave days each salary grade is granted.",
    href: "/dashboard/hr-admin/entitlements",
  },
  {
    key: "roles",
    title: "Define approver roles",
    description: "The positions a workflow step can name, such as Supervisor or HOD.",
    href: "/dashboard/hr-admin/roles",
  },
  {
    key: "teams",
    title: "Build a team and activate it",
    description:
      "Group staff, staff the approval chain, then put the team into force.",
    href: "/dashboard/hr-admin/teams",
  },
];

/** Human labels for the object keys the preset reports in ``created``. */
export const PRESET_OBJECT_LABELS: Record<string, string> = {
  financial_year: "Financial year",
  leave_types: "Leave type",
  leave_rules: "Leave rule",
  entitlements: "Entitlement band",
  roles: "Approver role",
};

export function presetObjectLabel(key: string): string {
  return PRESET_OBJECT_LABELS[key] ?? key;
}

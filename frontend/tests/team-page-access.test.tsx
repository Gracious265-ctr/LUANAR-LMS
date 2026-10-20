import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TeamPage from "@/app/(dashboard)/dashboard/teams/[id]/page";
import { getCurrentUser } from "@/lib/auth";
import { listAllEmployees } from "@/lib/employees";
import type { ApproverRole } from "@/lib/approver-roles";
import {
  listApproverRoles,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles";
import {
  getTeam,
  listTeamMemberCandidates,
  listTeamWorkflows,
} from "@/lib/teams";

vi.mock("next/navigation", () => ({ redirect: vi.fn(), notFound: vi.fn() }));
vi.mock("@/lib/auth", () => ({ getCurrentUser: vi.fn() }));
vi.mock("@/lib/teams", () => ({
  getTeam: vi.fn(),
  listTeamMemberCandidates: vi.fn(),
  listTeamWorkflows: vi.fn(),
  teamCategoryBadgeClass: () => "",
  teamCategoryLabel: (category: string) => category,
  teamStatusBadgeClass: () => "",
  teamStatusLabel: (status: string) => status,
}));
vi.mock("@/lib/employees", () => ({ listAllEmployees: vi.fn() }));
vi.mock("@/lib/approver-roles", () => ({
  listApproverRoles: vi.fn(),
  listRoleAssignments: vi.fn(),
  listCampusRoleAssignments: vi.fn(),
  listTeamRoleAssignments: vi.fn(),
}));
// The data-heavy panels fetch on mount; their own tests cover them, so render
// placeholders here and assert only which of them the page offers.
vi.mock("@/components/hr/team-lifecycle-actions", () => ({
  TeamLifecycleActions: () => <div data-testid="lifecycle" />,
}));
vi.mock("@/components/hr/team-member-list", () => ({
  TeamMemberList: () => <div data-testid="step-list" />,
}));
vi.mock("@/components/hr/team-members-panel", () => ({
  TeamMembersPanel: ({ candidates }: { candidates: unknown[] }) => (
    <div data-testid="members-panel" data-candidates={candidates.length} />
  ),
}));
vi.mock("@/components/hr/wide-holding-panel", () => ({
  WideHoldingPanel: () => <div data-testid="wide-panel" />,
}));
vi.mock("@/components/motion/FadeIn", () => ({
  FadeIn: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const team = {
  id: 1,
  name: "Registry team",
  code: "registry-team",
  description: "",
  category: "administration",
  campus: null,
  campus_name: "",
  workflows: [],
  status: "active",
  effective_from: null,
  effective_to: null,
  is_effective: true,
  stage_roles: [],
  member_count: 0,
  members: [],
  sections: [],
  created_at: "",
  updated_at: "",
};

const role = (overrides: Partial<ApproverRole>): ApproverRole =>
  ({
    id: 1,
    code: "hod",
    label: "Head of Department",
    is_active: true,
    is_institution_wide: false,
    ...overrides,
  }) as ApproverRole;

function asHr() {
  vi.mocked(getCurrentUser).mockResolvedValue({
    id: 1,
    email: "hr@luanar",
    role: "hr",
    full_name: "Hilda HR",
  });
}

function asManager() {
  vi.mocked(getCurrentUser).mockResolvedValue({
    id: 2,
    email: "manager@luanar",
    role: "employee",
    full_name: "Moses Manager",
    manages_teams: true,
  });
}

async function renderPage(searchParams: Record<string, string> = {}) {
  render(
    await TeamPage({
      params: Promise.resolve({ id: "1" }),
      searchParams: Promise.resolve(searchParams),
    })
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getTeam).mockResolvedValue(team);
  vi.mocked(listTeamWorkflows).mockResolvedValue([]);
  vi.mocked(listTeamMemberCandidates).mockResolvedValue([]);
  vi.mocked(listAllEmployees).mockResolvedValue([]);
  vi.mocked(listApproverRoles).mockResolvedValue([role({})]);
  vi.mocked(listTeamRoleAssignments).mockResolvedValue([]);
  vi.mocked(listRoleAssignments).mockResolvedValue([]);
  vi.mocked(listCampusRoleAssignments).mockResolvedValue([]);
});

describe("team page tabs by role", () => {
  it("offers HR the overview and the team-wide approvers, and no step or roster management", async () => {
    asHr();
    await renderPage();

    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Approvers" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Approval steps" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Members" })
    ).not.toBeInTheDocument();
  });

  it("does not offer HR a link to build a new chain", async () => {
    asHr();
    await renderPage();

    expect(
      screen.queryByRole("link", { name: "New workflow" })
    ).not.toBeInTheDocument();
  });

  it("offers a manager the overview, steps, and members, but not the team-wide approvers", async () => {
    asManager();
    await renderPage();

    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Approval steps" })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Members" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Approvers" })
    ).not.toBeInTheDocument();
  });

  it("offers a manager a link to build a new chain", async () => {
    asManager();
    await renderPage();

    expect(
      screen.getByRole("link", { name: "New workflow" })
    ).toBeInTheDocument();
  });

  it("hands the roster picker the candidates the manager read", async () => {
    // The read that fills the picker must reach it. It used to go through a
    // browser-only proxy with a bare relative `fetch`, which carries no
    // Authorization header from a Server Component: the 401 was swallowed into
    // an empty list and the picker simply said there was nobody to add.
    vi.mocked(listTeamMemberCandidates).mockResolvedValue([
      { id: 7, full_name: "Chikondi Phiri", email: "c@luanar", designation: "" },
    ]);
    asManager();
    await renderPage({ tab: "members" });

    expect(screen.getByTestId("members-panel")).toHaveAttribute(
      "data-candidates",
      "1"
    );
  });

  it("does not read candidates for HR, who has no roster to fill", async () => {
    asHr();
    await renderPage({ tab: "members" });

    expect(listTeamMemberCandidates).not.toHaveBeenCalled();
  });
});

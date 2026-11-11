import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamMembersPanel } from "@/components/hr/team-members-panel";
import type { TeamMemberSummary } from "@/lib/team-members";
import { listTeamMembers, removeTeamMember } from "@/lib/team-members-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh }),
}));

vi.mock("@/lib/team-members-client", () => ({
  listTeamMembers: vi.fn(),
  addTeamMembers: vi.fn(),
  removeTeamMember: vi.fn(),
  getWorkflowMemberPool: vi.fn(),
  removeWorkflowMember: vi.fn(),
}));

function makeMember(overrides: Partial<TeamMemberSummary> = {}): TeamMemberSummary {
  return {
    id: 21,
    user: 21,
    full_name: "Ruth Member",
    email: "ruth@test.luanar",
    designation: "Lecturer",
    category: "academic",
    faculty: "Agriculture",
    grade: "G",
    is_active: true,
    is_section_approver: false,
    team_role: null,
    workflow_memberships: [],
    workflow_count: 0,
    ...overrides,
  };
}

const everyone = makeMember();
const approver = makeMember({
  id: 22,
  user: 22,
  full_name: "Alice Approver",
  email: "alice@test.luanar",
  is_section_approver: true,
});
const holder = makeMember({
  id: 23,
  user: 23,
  full_name: "Bob Holder",
  email: "bob@test.luanar",
  team_role: "supervisor",
});
const routed = makeMember({
  id: 24,
  user: 24,
  full_name: "Carol Routed",
  email: "carol@test.luanar",
  workflow_count: 1,
  workflow_memberships: [{ workflow_id: 1, workflow_name: "Academic approval" }],
});

const team = { id: 4, name: "Bunda College Faculty" };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listTeamMembers).mockResolvedValue([
    everyone,
    approver,
    holder,
    routed,
  ]);
});

describe("TeamMembersPanel", () => {
  it("loads and lists the team's roster", async () => {
    render(<TeamMembersPanel team={team} />);

    await screen.findByText("Ruth Member");
    expect(screen.getByText("Alice Approver")).toBeInTheDocument();
    expect(screen.getByText("Bob Holder")).toBeInTheDocument();
    expect(screen.getByText("Carol Routed")).toBeInTheDocument();
    expect(listTeamMembers).toHaveBeenCalledWith(4);
  });

  it("says so plainly when the team has nobody on it", async () => {
    vi.mocked(listTeamMembers).mockResolvedValue([]);
    render(<TeamMembersPanel team={team} />);

    expect(
      await screen.findByText(/Nobody's leave routes through this team yet/)
    ).toBeInTheDocument();
  });

  it("sends the manager to the add page rather than opening a dialog", async () => {
    render(<TeamMembersPanel team={team} canManage />);
    await screen.findByText("Ruth Member");

    const add = screen.getByRole("link", { name: "Add team members" });
    expect(add).toHaveAttribute("href", "/dashboard/teams/4/members/add");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers the add page from the empty state, so an empty team has a next step", async () => {
    vi.mocked(listTeamMembers).mockResolvedValue([]);
    render(<TeamMembersPanel team={team} canManage />);

    const add = await screen.findByRole("link", { name: "Add team members" });
    expect(add).toHaveAttribute("href", "/dashboard/teams/4/members/add");
  });

  it("filters the roster to workflow members and searches by name", async () => {
    render(<TeamMembersPanel team={team} />);
    await screen.findByText("Ruth Member");

    fireEvent.change(screen.getByLabelText("Filter members"), {
      target: { value: "workflow" },
    });
    expect(screen.getByText("Carol Routed")).toBeInTheDocument();
    expect(screen.queryByText("Ruth Member")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search members"), {
      target: { value: "alice" },
    });
    expect(
      screen.queryByText(/No members match this search/)
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter members"), {
      target: { value: "all" },
    });
    expect(screen.getByText("Alice Approver")).toBeInTheDocument();
  });

  it("shows the backend's reason when a removal is refused", async () => {
    vi.mocked(removeTeamMember).mockRejectedValue(
      new Error(
        "Ruth Member still holds an open approver period on the Supervisor step."
      )
    );
    render(<TeamMembersPanel team={team} canManage />);
    await screen.findByText("Ruth Member");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Ruth Member from Bunda College Faculty",
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    expect(
      await screen.findByText(/still holds an open approver period/)
    ).toBeInTheDocument();
  });

  it("offers one add link when the roster is empty, not two", async () => {
    // The header action and the empty-state action point at the same page, so
    // rendering both put two identical links on the first screen a manager of a
    // new team sees.
    vi.mocked(listTeamMembers).mockResolvedValue([]);

    render(<TeamMembersPanel team={team} canManage />);

    expect(
      await screen.findByText(/Nobody's leave routes through this team yet/)
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "Add team members" })
    ).toHaveLength(1);
  });

  it("offers a non-manager the roster read-only", async () => {
    render(<TeamMembersPanel team={team} />);
    await screen.findByText("Ruth Member");

    expect(
      screen.queryByRole("link", { name: "Add team members" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Remove Ruth Member from Bunda College Faculty",
      })
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Only this team's designated manager can change its roster/)
    ).toBeInTheDocument();
  });
});

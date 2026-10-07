import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamMembersPanel } from "@/components/hr/team-members-panel";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { TeamMemberSummary } from "@/lib/team-members";
import {
  addTeamMember,
  listTeamMembers,
  removeTeamMember,
} from "@/lib/team-members-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh }),
}));

vi.mock("@/lib/team-members-client", () => ({
  listTeamMembers: vi.fn(),
  addTeamMember: vi.fn(),
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

const unassigned = makeEmployee({
  // A record's id (the profile pk) is deliberately different from its user_id
  // (the account it belongs to): the add picker writes a user id, and a test
  // that let them coincide could not tell the two apart.
  id: 30,
  user_id: 99,
  full_name: "Sam Candidate",
  designation: "Assistant",
  team: null,
  team_name: "",
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
    render(<TeamMembersPanel team={team} candidates={[]} />);

    await screen.findByText("Ruth Member");
    expect(screen.getByText("Alice Approver")).toBeInTheDocument();
    expect(screen.getByText("Bob Holder")).toBeInTheDocument();
    expect(screen.getByText("Carol Routed")).toBeInTheDocument();
    expect(listTeamMembers).toHaveBeenCalledWith(4);
  });

  it("says so plainly when the team has nobody on it", async () => {
    vi.mocked(listTeamMembers).mockResolvedValue([]);
    render(<TeamMembersPanel team={team} candidates={[]} />);

    expect(
      await screen.findByText(/Nobody's leave routes through this team yet/)
    ).toBeInTheDocument();
  });

  it("filters the roster to workflow members and searches by name", async () => {
    render(<TeamMembersPanel team={team} candidates={[]} />);
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

  it("adds an unassigned employee to the team", async () => {
    vi.mocked(addTeamMember).mockResolvedValue([...[]]);
    render(<TeamMembersPanel team={team} candidates={[unassigned]} />);
    await screen.findByText("Ruth Member");

    fireEvent.change(screen.getByLabelText("Employee to add to this team"), {
      target: { value: "99" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add to team" }));

    await waitFor(() => expect(addTeamMember).toHaveBeenCalledWith(4, 99));
    expect(refresh).toHaveBeenCalled();
  });

  it("shows the backend's reason when a removal is refused", async () => {
    vi.mocked(removeTeamMember).mockRejectedValue(
      new Error(
        "Ruth Member still holds an open approver period on the Supervisor step."
      )
    );
    render(<TeamMembersPanel team={team} candidates={[]} />);
    await screen.findByText("Ruth Member");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Ruth Member from Bunda College Faculty",
      })
    );

    expect(
      await screen.findByText(/still holds an open approver period/)
    ).toBeInTheDocument();
  });

  it("offers only the scoped candidates in the add picker and says so", async () => {
    render(<TeamMembersPanel team={team} candidates={[unassigned]} />);
    await screen.findByText("Ruth Member");

    expect(
      screen.getByRole("option", { name: /Sam Candidate/ })
    ).toBeInTheDocument();
    // The picker's promise is scoped by the team's category and by who is
    // already its wide approver. The server read those filters (the panel is
    // handed the filtered candidates), and the copy names the scope rather
    // than implying the whole directory is on offer.
    expect(
      screen.getByText(/who match this team's category are offered here/)
    ).toBeInTheDocument();
  });
});
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { TeamMemberList } from "@/components/hr/team-member-list";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { Team } from "@/lib/teams";
import { addTeamMember, removeTeamMember } from "@/lib/teams-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, addTeamMember: vi.fn(), removeTeamMember: vi.fn() };
});

function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 4,
    name: "Bunda College Faculty",
    code: "bunda-faculty",
    description: "",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    is_active: true,
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "hod", label: "Head of Department" },
    ],
    member_count: 1,
    members: [
      {
        id: 9,
        team: 4,
        user: 3,
        user_name: "Jane Dean",
        role: "supervisor",
        role_label: "Supervisor",
        created_at: "2026-01-01T00:00:00Z",
      },
    ],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const people = [
  makeEmployee({ id: 3, user_id: 3, full_name: "Jane Dean" }),
  makeEmployee({ id: 5, user_id: 5, full_name: "Bob HOD" }),
  makeEmployee({ id: 8, user_id: 8, full_name: "Sam Staff" }),
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamMemberList", () => {
  it("warns when a team has nobody on it", () => {
    render(
      <TeamMemberList team={makeTeam({ members: [], member_count: 0 })} employees={people} />
    );

    expect(
      screen.getByText(
        "Nobody is on this team yet. An application routed here would have nobody to approve it."
      )
    ).toBeInTheDocument();
  });

  it("lists each member with the role they hold", () => {
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.getByText("as Supervisor")).toBeInTheDocument();
  });

  it("offers exactly the roles the team's workflow names", () => {
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    fireEvent.click(screen.getByRole("button", { name: "Add a member" }));

    const roleSelect = screen.getByLabelText(
      "The role they hold on Bunda College Faculty"
    );
    expect(
      Array.from(roleSelect.querySelectorAll("option")).map(
        (option) => option.textContent
      )
    ).toEqual(["As…", "Supervisor", "Head of Department"]);
  });

  it("adds a member by code and refreshes", async () => {
    vi.mocked(addTeamMember).mockResolvedValue({
      id: 10,
      team: 4,
      user: 5,
      user_name: "Bob HOD",
      role: "hod",
      role_label: "Head of Department",
      created_at: "2026-01-01T00:00:00Z",
    });
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    fireEvent.click(screen.getByRole("button", { name: "Add a member" }));
    fireEvent.change(
      screen.getByLabelText("Add a member to Bunda College Faculty"),
      { target: { value: "5" } }
    );
    fireEvent.change(
      screen.getByLabelText("The role they hold on Bunda College Faculty"),
      { target: { value: "hod" } }
    );
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(addTeamMember).toHaveBeenCalledWith({ team: 4, user: 5, role: "hod" })
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("explains a refusal instead of silently failing", async () => {
    vi.mocked(addTeamMember).mockRejectedValue(
      new Error('role: The team already has a Supervisor — Jane Dean.')
    );
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    fireEvent.click(screen.getByRole("button", { name: "Add a member" }));
    fireEvent.change(
      screen.getByLabelText("Add a member to Bunda College Faculty"),
      { target: { value: "8" } }
    );
    fireEvent.change(
      screen.getByLabelText("The role they hold on Bunda College Faculty"),
      { target: { value: "supervisor" } }
    );
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText(
        "role: The team already has a Supervisor — Jane Dean."
      )
    ).toBeInTheDocument();
  });

  it("removes a member and refreshes", async () => {
    vi.mocked(removeTeamMember).mockResolvedValue(undefined);
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Remove Jane Dean from this team" })
    );

    await waitFor(() => expect(removeTeamMember).toHaveBeenCalledWith(9));
    expect(refresh).toHaveBeenCalled();
  });

  it("says there is nobody to staff when the workflow names no roles", () => {
    render(
      <TeamMemberList team={makeTeam({ stage_roles: [] })} employees={people} />
    );

    expect(
      screen.getByText(/workflow names no approver roles/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add a member" })
    ).not.toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { TeamMemberList } from "@/components/hr/team-member-list";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { Team } from "@/lib/teams";
import {
  addSectionMember,
  listSectionMembers,
  removeSectionMember,
} from "@/lib/section-members-client";
import type { SectionMember } from "@/lib/workflows";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/section-members-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/section-members-client")>();
  return {
    ...actual,
    listSectionMembers: vi.fn(),
    listSectionMemberHistory: vi.fn(async () => []),
    addSectionMember: vi.fn(),
    removeSectionMember: vi.fn(),
  };
});

const SECTION_NAMES: Record<number, string> = {
  1: "Direct supervisor",
  2: "Department head",
};

function makeSectionMember(
  memberId: number,
  sectionId: number,
  user: number,
  name: string
): SectionMember {
  return {
    id: memberId,
    section: sectionId,
    section_name: SECTION_NAMES[sectionId],
    section_order: sectionId,
    workflow: 1,
    approver_role: sectionId === 1 ? "supervisor" : "hod",
    approver_role_label: sectionId === 1 ? "Supervisor" : "Head of Department",
    user,
    user_name: name,
    user_email: `${name.toLowerCase().replace(/\s+/g, ".")}@luanar.ac.mw`,
    effective_from: "2026-01-01",
    effective_to: null,
    is_effective: true,
    created_at: "2026-01-01T00:00:00Z",
  };
}

function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 4,
    name: "Bunda College Faculty",
    code: "bunda-faculty",
    description: "",
    department: "",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    status: "active",
    effective_from: "2026-01-01",
    effective_to: null,
    is_effective: true,
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "hod", label: "Head of Department" },
    ],
    member_count: 1,
    members: [],
    sections: [
      {
        id: 1,
        name: "Direct supervisor",
        order: 1,
        is_active: true,
        approver_role: "supervisor",
        approver_role_label: "Supervisor",
        member_count: 1,
        members: [],
      },
      {
        id: 2,
        name: "Department head",
        order: 2,
        is_active: true,
        approver_role: "hod",
        approver_role_label: "Head of Department",
        member_count: 1,
        members: [],
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

const jane = makeSectionMember(9, 1, 3, "Jane Dean");
const bob = makeSectionMember(10, 2, 5, "Bob HOD");

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listSectionMembers).mockImplementation(async (section) =>
    section === 1 ? [jane] : [bob]
  );
});

describe("TeamMemberList", () => {
  it("renders the sections the team's workflow asks for, with their members", async () => {
    render(<TeamMemberList team={makeTeam()} employees={people} />);

    expect(await screen.findByText("Supervisor")).toBeInTheDocument();
    expect(screen.getByText("Head of Department")).toBeInTheDocument();
    expect(await screen.findByText("Jane Dean")).toBeInTheDocument();
    expect(screen.getByText("Bob HOD")).toBeInTheDocument();
  });

  it("adds a member to a section by id and refreshes", async () => {
    vi.mocked(addSectionMember).mockResolvedValue(undefined as never);
    render(<TeamMemberList team={makeTeam()} employees={people} />);
    await screen.findByText("Jane Dean");

    const section1 = screen.getByRole("group", {
      name: "Section 1: Direct supervisor",
    });
    fireEvent.click(
      within(section1).getByRole("button", { name: "Add a member" })
    );
    fireEvent.change(
      screen.getByLabelText("Add a member to Direct supervisor"),
      { target: { value: "8" } }
    );
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    // No start date was given, so the membership begins today rather than on
    // some invented date: an absent date is not "sometime".
    await waitFor(() =>
      expect(addSectionMember).toHaveBeenCalledWith(1, 8, undefined)
    );
    expect(listSectionMembers).toHaveBeenCalledWith(1);
    expect(refresh).toHaveBeenCalled();
  });

  it("explains a refusal instead of silently failing", async () => {
    vi.mocked(addSectionMember).mockRejectedValue(
      new Error("user: Jane Dean is not an active user.")
    );
    render(<TeamMemberList team={makeTeam()} employees={people} />);
    await screen.findByText("Jane Dean");

    const section1 = screen.getByRole("group", {
      name: "Section 1: Direct supervisor",
    });
    fireEvent.click(
      within(section1).getByRole("button", { name: "Add a member" })
    );
    fireEvent.change(
      screen.getByLabelText("Add a member to Direct supervisor"),
      { target: { value: "8" } }
    );
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText("user: Jane Dean is not an active user.")
    ).toBeInTheDocument();
  });

  it("removes a member from a section and refreshes", async () => {
    vi.mocked(removeSectionMember).mockResolvedValue(undefined as never);
    render(<TeamMemberList team={makeTeam()} employees={people} />);
    await screen.findByText("Jane Dean");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Jane Dean from Direct supervisor",
      })
    );

    await waitFor(() => expect(removeSectionMember).toHaveBeenCalledWith(9));
    expect(listSectionMembers).toHaveBeenCalledWith(1);
    expect(refresh).toHaveBeenCalled();
  });

  it("says there is nobody to staff when the team has no steps", () => {
    render(
      <TeamMemberList
        team={makeTeam({ sections: [] })}
        employees={people}
      />
    );

    expect(screen.getByText(/no approval steps/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add a member" })
    ).not.toBeInTheDocument();
  });
});
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { TeamMemberList } from "@/components/hr/team-member-list";
import type { EligibleApprover, Team } from "@/lib/teams";
import {
  addSectionMember,
  listSectionMemberHistory,
  listSectionMembers,
  removeSectionMember,
} from "@/lib/section-members-client";
import { listEligibleApprovers } from "@/lib/teams-client";
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

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, listEligibleApprovers: vi.fn() };
});

const SECTION_NAMES: Record<number, string> = {
  1: "Direct supervisor",
  2: "Team leader",
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
    approver_role: sectionId === 1 ? "supervisor" : "lead",
    approver_role_label: sectionId === 1 ? "Supervisor" : "Team Leader",
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
    category: "academic",
    campus: null,
    campus_name: "",
    workflow: 1,
    workflow_name: "Academic approval",
    workflows: [],
    status: "active",
    effective_from: "2026-01-01",
    effective_to: null,
    is_effective: true,
    is_team_manager: false,
    manager_user: null,
    manager_name: "",
    stage_roles: [
      { id: 1, code: "supervisor", label: "Supervisor" },
      { id: 2, code: "lead", label: "Team Leader" },
    ],
    member_count: 2,
    roster_count: 0,
    members: [],
    sections: [
      {
        id: 1,
        name: "Direct supervisor",
        order: 1,
        is_active: true,
        approver_role: "supervisor",
        approver_role_label: "Supervisor",
        approver: {
          id: 3,
          user_name: "Jane Dean",
          user_email: "jane.dean@luanar.ac.mw",
        },
        resolution: "staffed",
      },
      {
        id: 2,
        name: "Team leader",
        order: 2,
        is_active: true,
        approver_role: "lead",
        approver_role_label: "Team Leader",
        approver: null,
        resolution: "unresolved",
      },
    ],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const janeApprover: EligibleApprover = {
  id: 3,
  full_name: "Jane Dean",
  email: "jane.dean@luanar.ac.mw",
  designation: "Dean",
};

const sam: EligibleApprover = {
  id: 8,
  full_name: "Sam Staff",
  email: "sam.staff@luanar.ac.mw",
  designation: "Officer",
};

const jane = makeSectionMember(9, 1, 3, "Jane Dean");
const bob = makeSectionMember(10, 2, 5, "Bob Lead");

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listSectionMembers).mockImplementation(async (section) =>
    section === 1 ? [jane] : [bob]
  );
  vi.mocked(listEligibleApprovers).mockResolvedValue([janeApprover, sam]);
});

describe("TeamMemberList", () => {
  it("shows each step's single approver and who may replace them", async () => {
    render(<TeamMemberList team={makeTeam()} />);

    expect(await screen.findByText("Supervisor")).toBeInTheDocument();
    expect(screen.getByText("Team Leader")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Approver for Direct supervisor" })
    ).toHaveValue("3");
    // The second step has nobody appointed yet, but the people who could hold
    // it are offered.
    expect(
      screen.getByRole("combobox", { name: "Approver for Team leader" })
    ).toHaveValue("");
    expect(
      within(
        screen.getByRole("group", { name: "Section 2: Team leader" })
      ).getByRole("option", { name: /Sam Staff/ })
    ).toBeInTheDocument();

    // Eligibility is the team, so the list is asked for by team id — scoped to
    // the chain the team routes through, so people already serving one of its
    // other chains are not offered. Offering anybody the team does not have
    // would be offering somebody the write then refuses.
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1, 1);
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 2, 1);
  });

  it("appoints one person to a step by id and refreshes", async () => {
    vi.mocked(addSectionMember).mockResolvedValue(undefined as never);
    render(<TeamMemberList team={makeTeam()} />);
    await screen.findByText("Supervisor");

    fireEvent.change(
      screen.getByRole("combobox", { name: "Approver for Direct supervisor" }),
      { target: { value: "8" } }
    );

    await waitFor(() => expect(addSectionMember).toHaveBeenCalledWith(1, 8));
    expect(refresh).toHaveBeenCalled();
  });

  it("explains a refusal instead of silently failing", async () => {
    vi.mocked(addSectionMember).mockRejectedValue(
      new Error("user: Sam Staff already holds another role on this team.")
    );
    render(<TeamMemberList team={makeTeam()} />);
    await screen.findByText("Supervisor");

    fireEvent.change(
      screen.getByRole("combobox", { name: "Approver for Team leader" }),
      { target: { value: "8" } }
    );

    expect(
      await screen.findByText(
        "user: Sam Staff already holds another role on this team."
      )
    ).toBeInTheDocument();
  });

  it("removes the current approver and refreshes", async () => {
    vi.mocked(removeSectionMember).mockResolvedValue(undefined as never);
    render(<TeamMemberList team={makeTeam()} />);
    await screen.findByText("Supervisor");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Jane Dean from Direct supervisor",
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() => expect(removeSectionMember).toHaveBeenCalledWith(9));
    expect(refresh).toHaveBeenCalled();
  });

  it("fetches who held the step before only when asked", async () => {
    render(<TeamMemberList team={makeTeam()} />);
    await screen.findByText("Supervisor");

    expect(listSectionMemberHistory).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Show past approvers of Direct supervisor",
      })
    );

    await waitFor(() =>
      expect(listSectionMemberHistory).toHaveBeenCalledWith(1)
    );
  });

  it("says there is nobody to appoint when the team has no steps", () => {
    render(<TeamMemberList team={makeTeam({ sections: [] })} />);

    expect(screen.getByText(/no approval steps/i)).toBeInTheDocument();
  });

  it("says a step nobody on the team can hold has nobody to appoint", async () => {
    vi.mocked(listEligibleApprovers).mockResolvedValue([]);
    render(<TeamMemberList team={makeTeam()} />);

    expect(
      await screen.findByText(/Nobody on this team holds this role yet/)
    ).toBeInTheDocument();
  });
});
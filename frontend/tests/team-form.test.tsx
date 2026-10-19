import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Campus, EligibleApprover, Team, TeamSection } from "@/lib/teams";
import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import {
  createTeam,
  listEligibleApprovers,
  updateTeam,
} from "@/lib/teams-client";
import { createApproverRole } from "@/lib/approver-roles-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return {
    ...actual,
    createTeam: vi.fn(),
    updateTeam: vi.fn(),
    listEligibleApprovers: vi.fn(),
  };
});

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return { ...actual, createApproverRole: vi.fn() };
});

const campuses: Campus[] = [
  makeCampus(),
  makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" }),
];

const roles: ApproverRole[] = [
  {
    id: 1,
    code: "supervisor",
    label: "Supervisor",
    description: "",
    is_active: true,
    history_scope: "team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: true,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    code: "lead",
    label: "Team Leader",
    description: "",
    is_active: true,
    history_scope: "team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: true,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const jane: EligibleApprover = {
  id: 3,
  full_name: "Jane Dean",
  email: "jane.dean@test.luanar",
  designation: "Dean",
};
const bob: EligibleApprover = {
  id: 5,
  full_name: "Bob Lead",
  email: "bob.lead@test.luanar",
  designation: "Team Leader",
};

/**
 * The people the create form may name as a team's manager: active employees of
 * the team's own category who hold no wide approver role.
 */
const maryManager = makeEmployee({
  user_id: 21,
  full_name: "Mary Manager",
  category: "administration",
});
const adaAcademic = makeEmployee({
  user_id: 22,
  full_name: "Ada Academic",
  category: "academic",
});

/**
 * The manager step, which every create walks through before it saves.
 *
 * The role is the first team-scoped role in the fixture above; the person is a
 * category match so the picker would actually offer them.
 */
function chooseManager(person = maryManager) {
  fireEvent.change(screen.getByLabelText("Manager role"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("Manager"), {
    target: { value: String(person.user_id) },
  });
}

/** A step as the API reports it, so tests do not restate the flattened fields. */
function makeSection(overrides: Partial<TeamSection> = {}): TeamSection {
  return { ...makeTeam().sections[0], ...overrides };
}

function mockCandidates(byRole: Record<number, EligibleApprover[]>) {
  vi.mocked(listEligibleApprovers).mockImplementation(
    async (_team: number, role?: number) =>
      role === undefined ? [] : byRole[role] ?? []
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockCandidates({ 1: [jane], 2: [bob] });
});

/**
 * A team being edited, so the approver picker has a team to be scoped by.
 *
 * Eligibility is answered by the team, so the create form has no roster to offer
 * and the pickers below are exercised against a team that already exists.
 */
function existingTeam(overrides: Partial<Team> = {}): Team {
  return makeTeam({
    name: "Registry",
    description: "",
    // Administration by default: these tests are about the chain, not the
    // campus rule, and an academic team with no campus is refused on save.
    category: "administration",
    campus: null,
    status: "active",
    is_effective: true,
    sections: [],
    ...overrides,
  });
}

/** The step at `position` (1-based, as it is labelled on screen). */
function step(position: number) {
  return within(screen.getByRole("group", { name: `Step ${position}` }));
}

describe("TeamForm", () => {
  it("creates a team from its details and a manager, and lands on its Members tab so employees are added before the workflow is configured", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} roles={roles} employees={[maryManager]} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // Creating asks only what the team is, then who runs it. The chain is not
    // part of creation: the team becomes a draft and is shown with its roster
    // next, so an approver — who has to be one of the team's employees — can be
    // named honestly once the workflow is configured from the team's page.
    expect(
      screen.queryByRole("button", { name: "Continue to approval steps" })
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to the manager" })
    );

    chooseManager();
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Registry" })
      )
    );
    expect(vi.mocked(createTeam).mock.calls[0][0]).not.toHaveProperty(
      "new_workflow"
    );
    // A team is scoped by itself and its campus, and handed to a manager, so
    // that is all this sends. The key list is exact rather than a spot check,
    // because the backend refuses a field it does not have: a stray key is a
    // save that fails, not a wrong value on screen.
    expect(Object.keys(vi.mocked(createTeam).mock.calls[0][0]).sort()).toEqual([
      "campus",
      "category",
      "description",
      "effective_from",
      "effective_to",
      "manager",
      "name",
    ]);
    expect(vi.mocked(createTeam).mock.calls[0][0].manager).toEqual({
      role: 1,
      user: 21,
    });
    expect(push).toHaveBeenCalledWith("/dashboard/teams/4?tab=members");
    expect(refresh).toHaveBeenCalled();
  });

  it("refuses to save a chain whose step names no single approver", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={existingTeam({ sections: [makeSection()] })}
        campuses={campuses}
        roles={roles}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText(
        "Name the one person who decides at every step, or save the team as a draft."
      )
    ).toBeInTheDocument();
    expect(updateTeam).not.toHaveBeenCalled();
  });

  it("scopes the approver picker to the team, and clears it when the role changes", async () => {
    render(
      <TeamForm team={existingTeam()} campuses={campuses} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    // Eligibility is the team: nobody who is not on it can be appointed here,
    // so the list is asked for by the team's own id.
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1);

    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("3");

    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "lead" },
    });
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Bob Lead/ })).toBeInTheDocument()
    );
    // The person chosen for the previous role is likely not eligible for the new
    // one, so the choice is cleared rather than sent and refused.
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("");
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 2);
  });

  it("prefills an existing team's details and its one approver per step", async () => {
    render(
      <TeamForm
        team={existingTeam({
          category: "academic",
          campus: 2,
          campus_name: "Bunda Campus",
          workflow: 2,
          workflow_name: "Administrative approval",
          sections: [
            makeSection({
              id: 7,
              name: "Supervisor approval",
              approver_role: "supervisor",
              approver: {
                id: 3,
                user_name: "Jane Dean",
                user_email: "jane.dean@test.luanar",
              },
            }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    // An edit opens on the steps page, because that is where the work is.
    expect(
      screen.getByRole("heading", { name: "Who approves for this team" })
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Step 1 role")).toHaveValue("supervisor");
    // The approver the step already had, once its people have been fetched.
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("3")
    );
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("sends the edited chain with its approver, so an edit does not unappoint a step", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={existingTeam({
          sections: [
            makeSection({
              name: "Supervisor approval",
              approver_role: "supervisor",
              approver: {
                id: 3,
                user_name: "Jane Dean",
                user_email: "jane.dean@test.luanar",
              },
            }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          new_workflow: {
            sections: [
              {
                name: "Supervisor",
                approver_role: "supervisor",
                approver: 3,
              },
            ],
          },
        })
      )
    );
    expect(createTeam).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/dashboard/teams/4");
  });

  it("reorders the steps by what is shown rather than by the order they were added", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm team={existingTeam()} campuses={campuses} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 2 role"), {
      target: { value: "lead" },
    });
    await waitFor(() =>
      expect(step(2).getByRole("option", { name: /Bob Lead/ })).toBeInTheDocument()
    );
    fireEvent.change(step(2).getByLabelText("Step 2 approver"), {
      target: { value: "5" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Move step 2 up" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({ approver_role: "lead", approver: 5 }),
              expect.objectContaining({ approver_role: "supervisor", approver: 3 }),
            ],
          }),
        })
      )
    );
  });

  it("sends the chosen campus as an id, and only for an academic team", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[maryManager, adaAcademic]}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // The campus select is the visible half of the rule: it is disabled until
    // the team is said to be academic, because an administration team does not
    // sit at a campus at all.
    expect(screen.getByLabelText("Campus")).toBeDisabled();
    fireEvent.click(
      screen.getByRole("radio", { name: /academic/i })
    );
    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "1" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to the manager" })
    );
    // An academic team's manager is an academic employee, so the picker offers
    // only the half of the institution the write will accept.
    chooseManager(adaAcademic);
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ campus: 1, category: "academic" })
      )
    );
  });

  it("refuses an academic team with no campus, rather than saving one without one", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(<TeamForm campuses={campuses} roles={roles} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("radio", { name: /academic/i }));
    // The campus rule is answered on the details page, so the manager step is
    // never reached with a team the save would refuse.
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to the manager" })
    );

    expect(
      await screen.findByText(/An academic team sits at a campus/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Manager role")).not.toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("sends an administration team with no campus, as institution-wide", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm campuses={campuses} roles={roles} employees={[maryManager]} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    // The default category is administration, and the campus is cleared rather
    // than left at whatever an earlier screen might have held.
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to the manager" })
    );
    chooseManager();
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          category: "administration",
          campus: null,
        })
      )
    );
  });

  it("says so when the roles could not be loaded, rather than offering a blank step", () => {
    render(
      <TeamForm
        team={existingTeam()}
        campuses={campuses}
        roles={[]}
        rolesError="Unable to load approver roles, so the approval steps cannot be described."
      />
    );

    expect(
      screen.getByText(
        "Unable to load approver roles, so the approval steps cannot be described."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add step" })).toBeDisabled();
  });

  it("shows why the backend refused the team and stays on the manager step", async () => {
    vi.mocked(createTeam).mockRejectedValue(
      new Error("A team with that name already exists.")
    );
    render(
      <TeamForm campuses={campuses} roles={roles} employees={[maryManager]} />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to the manager" })
    );
    chooseManager();
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      await screen.findByText("A team with that name already exists.")
    ).toBeInTheDocument();
    // The refusal names what was wrong with the write, and the chosen manager
    // is still on screen so it can be corrected rather than re-entered.
    expect(screen.getByLabelText("Manager")).toHaveValue("21");
    expect(push).not.toHaveBeenCalled();
  });

  it("creates an approver role while describing a step and offers it", async () => {
    const created: ApproverRole = {
      id: 9,
      code: "registrar",
      label: "Registrar",
      description: "",
      is_active: true,
      history_scope: "all",
      handles_cancellation: false,
      is_institution_wide: true,
      is_in_use: false,
      usage: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(createApproverRole).mockResolvedValue(created);
    render(
      <TeamForm team={existingTeam()} campuses={campuses} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByLabelText("New role name"), {
      target: { value: "Registrar" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save role" }));

    await waitFor(() =>
      expect(createApproverRole).toHaveBeenCalledWith({ label: "Registrar" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(screen.getByRole("option", { name: "Registrar" })).toBeInTheDocument();
  });

  it("appoints the single institution-wide holder automatically when its role is chosen", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const holder: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [holder] });
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        team={existingTeam()}
        campuses={campuses}
        roles={[...roles, registrar]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "registrar" },
    });

    // Selecting the role is the instruction: the one holder is filled in
    // without HR touching the picker, which could not have offered them first.
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("11")
    );
    expect(
      screen.getByText(/Its holder approves automatically/)
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({
                name: "Registrar",
                approver_role: "registrar",
                approver: 11,
              }),
            ],
          }),
        })
      )
    );
  });

  it("appoints a step whose role was already loaded, without asking again", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const holder: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [holder] });
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        team={existingTeam()}
        campuses={campuses}
        roles={[registrar, ...roles]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("11")
    );

    // A second step takes the same role. Its people were already asked for, so
    // nothing is fetched again — the step must still be appointed rather than
    // waiting on a request that will never be made.
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(step(2).getByLabelText("Step 2 approver")).toHaveValue("11")
    );
    expect(
      vi
        .mocked(listEligibleApprovers)
        .mock.calls.filter(([, role]) => role === 9)
    ).toHaveLength(1);

    // ...and the repeat is refused on save. The backend enforces the same rule as
    // a constraint on the workflow; catching it here names the role, where a
    // database error naming a constraint would not.
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Two steps both use the Registrar role/
    );
    expect(updateTeam).not.toHaveBeenCalled();
  });

  it("refuses to save one person on two steps", async () => {
    mockCandidates({ 1: [jane], 2: [jane] });
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm team={existingTeam()} campuses={campuses} roles={roles} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    // Two different roles, one person: the roles are unique, so this is caught
    // by the approver rule rather than the role one.
    fireEvent.change(screen.getByLabelText("Step 2 role"), {
      target: { value: "lead" },
    });
    await waitFor(() =>
      expect(step(1).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "3" },
    });
    await waitFor(() =>
      expect(step(2).getByRole("option", { name: /Jane Dean/ })).toBeInTheDocument()
    );
    fireEvent.change(step(2).getByLabelText("Step 2 approver"), {
      target: { value: "3" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Jane Dean decides more than one step/
    );
    expect(updateTeam).not.toHaveBeenCalled();
  });

  it("leaves an institution-wide step to HR when several hold the role", async () => {
    const registrar: ApproverRole = {
      ...roles[0],
      id: 9,
      code: "registrar",
      label: "Registrar",
      is_institution_wide: true,
    };
    const first: EligibleApprover = {
      id: 11,
      full_name: "Rita Registrar",
      email: "rita.registrar@test.luanar",
      designation: "Registrar",
    };
    const second: EligibleApprover = {
      id: 12,
      full_name: "Rex Registrar",
      email: "rex.registrar@test.luanar",
      designation: "Deputy Registrar",
    };
    mockCandidates({ 1: [jane], 2: [bob], 9: [first, second] });
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());

    render(
      <TeamForm
        team={existingTeam()}
        campuses={campuses}
        roles={[...roles, registrar]}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 1 role"), {
      target: { value: "registrar" },
    });

    await waitFor(() =>
      expect(
        step(1).getByRole("option", { name: /Rita Registrar/ })
      ).toBeInTheDocument()
    );
    expect(
      step(1).getByRole("option", { name: /Rex Registrar/ })
    ).toBeInTheDocument();
    // Several holders is a real choice, so nothing is decided for HR.
    expect(step(1).getByLabelText("Step 1 approver")).toHaveValue("");

    fireEvent.change(step(1).getByLabelText("Step 1 approver"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({
                approver_role: "registrar",
                approver: 12,
              }),
            ],
          }),
        })
      )
    );
  });
});

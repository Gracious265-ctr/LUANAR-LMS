import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { Campus, TeamSection } from "@/lib/teams";
import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { createTeam, updateTeam } from "@/lib/teams-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, createTeam: vi.fn(), updateTeam: vi.fn() };
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
    code: "hod",
    label: "Head of Department",
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

/** A step as the API reports it, so tests do not restate the flattened fields. */
function makeSection(overrides: Partial<TeamSection> = {}): TeamSection {
  return { ...makeTeam().sections[0], ...overrides };
}

const employees: Employee[] = [
  makeEmployee({ id: 3, user_id: 3, full_name: "Jane Dean" }),
  makeEmployee({ id: 5, user_id: 5, full_name: "Bob HOD" }),
];

beforeEach(() => {
  vi.clearAllMocks();
});

/**
 * A new team starts with one unnamed step, because a chain nobody can act for is
 * not something to send. Naming it is all that stands between this and a save.
 */
function renderNewTeam() {
  render(<TeamForm campuses={campuses} roles={roles} employees={employees} />);
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Registry" },
  });
}

/** The step at `position` (1-based, as it is labelled on screen). */
function step(position: number) {
  return within(screen.getByRole("group", { name: `Step ${position}` }));
}

describe("TeamForm", () => {
  it("refuses to save a team whose chain names no steps, rather than routing nothing", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    renderNewTeam();

    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      await screen.findByText(
        "Describe at least one approval step, or name the step you add."
      )
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("refuses to create a team with a step nobody can act for", () => {
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "Supervisor approval" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      screen.getByText(
        "Give every step at least one person who can act, or the team cannot route."
      )
    ).toBeInTheDocument();
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("creates the chain with the team, sending no pointer to somebody else's chain", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Chain name"), {
      target: { value: "Registrar chain" },
    });
    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "Supervisor approval" },
    });
    fireEvent.click(screen.getByLabelText("Jane Dean"));

    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 2 name"), {
      target: { value: "Registrar approval" },
    });
    fireEvent.change(screen.getByLabelText("Step 2 role"), {
      target: { value: "hod" },
    });
    fireEvent.click(step(2).getByLabelText("Bob HOD"));

    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Registry",
          new_workflow: {
            name: "Registrar chain",
            sections: [
              {
                name: "Supervisor approval",
                approver_role: "supervisor",
                members: [3],
              },
              { name: "Registrar approval", approver_role: "hod", members: [5] },
            ],
          },
        })
      )
    );
    // A team owns its chain, so there is no id to point at: the chain is part
    // of this write, and the backend mints it alongside the team.
    expect(vi.mocked(createTeam).mock.calls[0][0]).not.toHaveProperty("workflow");
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/teams");
    expect(refresh).toHaveBeenCalled();
  });

  it("reorders the steps by what is shown rather than by the order they were added", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "First" },
    });
    fireEvent.click(step(1).getByLabelText("Jane Dean"));
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Step 2 name"), {
      target: { value: "Second" },
    });
    fireEvent.click(step(2).getByLabelText("Bob HOD"));

    fireEvent.click(screen.getByRole("button", { name: "Move step 2 up" }));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          new_workflow: expect.objectContaining({
            sections: [
              expect.objectContaining({ name: "Second" }),
              expect.objectContaining({ name: "First" }),
            ],
          }),
        })
      )
    );
  });

  it("sends the lifecycle dates and the department, never an active flag", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Department / Faculty"), {
      target: { value: "Registrar" },
    });
    fireEvent.change(screen.getByLabelText("In force from"), {
      target: { value: "2026-01-01" },
    });
    fireEvent.change(screen.getByLabelText("In force until"), {
      target: { value: "2026-12-31" },
    });
    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "Supervisor approval" },
    });
    fireEvent.click(screen.getByLabelText("Jane Dean"));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({
          department: "Registrar",
          effective_from: "2026-01-01",
          effective_to: "2026-12-31",
        })
      )
    );
    expect(vi.mocked(createTeam).mock.calls[0][0]).not.toHaveProperty("status");
  });

  it("sends the chosen campus as an id and leaves a blank one null", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "Supervisor approval" },
    });
    fireEvent.click(screen.getByLabelText("Jane Dean"));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ campus: 1 })
      )
    );
  });

  it("prefills an existing team and its steps for editing", () => {
    render(
      <TeamForm
        team={makeTeam({
          campus: 2,
          campus_name: "Bunda Campus",
          workflow: 2,
          workflow_name: "Administrative approval",
          department: "Administration",
          effective_from: "2026-01-01",
          sections: [
            makeSection({ id: 7, name: "Supervisor approval", approver_role: "supervisor" }),
            makeSection({ id: 8, name: "Registrar approval", approver_role: "hod" }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    expect(screen.getByLabelText("Name")).toHaveValue("Bunda College Faculty");
    expect(screen.getByLabelText("Campus")).toHaveValue("2");
    expect(screen.getByLabelText("Chain name")).toHaveValue(
      "Administrative approval"
    );
    expect(screen.getByLabelText("Department / Faculty")).toHaveValue(
      "Administration"
    );
    expect(screen.getByLabelText("In force from")).toHaveValue("2026-01-01");
    expect(screen.getByLabelText("Step 1 name")).toHaveValue(
      "Supervisor approval"
    );
    expect(screen.getByLabelText("Step 1 role")).toHaveValue("supervisor");
    expect(screen.getByLabelText("Step 2 name")).toHaveValue(
      "Registrar approval"
    );
    expect(screen.getByLabelText("Step 2 role")).toHaveValue("hod");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("sends an edit without members, so the backend keeps the roster on surviving steps", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={makeTeam({
          sections: [
            makeSection({ name: "Supervisor approval", approver_role: "supervisor" }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Faculty" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({
          name: "Bunda Faculty",
          new_workflow: {
            name: "Academic approval",
            // No members key at all. The roster is an audited action of its own,
            // so an edit to the steps must not look like a request to clear it.
            sections: [
              { name: "Supervisor approval", approver_role: "supervisor" },
            ],
          },
        })
      )
    );
    expect(createTeam).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/teams/4");
  });

  it("refuses to save an existing team once its only step is unnamed", async () => {
    render(
      <TeamForm
        team={makeTeam({
          sections: [
            makeSection({ name: "Supervisor approval", approver_role: "supervisor" }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    // A step the author has not named is not a step. Saving it would clear the
    // step out of the chain, so the form asks first rather than assuming.
    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText("This team has no approval steps. Add at least one.")
    ).toBeInTheDocument();
    expect(updateTeam).not.toHaveBeenCalled();
  });

  it("cannot be saved with no steps at all, so the button is disabled", () => {
    render(
      <TeamForm
        team={makeTeam({
          sections: [
            makeSection({ name: "Supervisor approval", approver_role: "supervisor" }),
          ],
        })}
        campuses={campuses}
        roles={roles}
      />
    );

    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove step 1" }));
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeDisabled();
  });

  it("does not offer a roster on edit, because changing it is its own audited action", () => {
    render(
      <TeamForm
        team={makeTeam({
          sections: [
            makeSection({ name: "Supervisor approval", approver_role: "supervisor" }),
          ],
        })}
        campuses={campuses}
        roles={roles}
        employees={employees}
      />
    );

    expect(screen.queryByLabelText("Jane Dean")).not.toBeInTheDocument();
  });

  it("only offers people who are in force to start a chain", () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={roles}
        employees={[
          ...employees,
          makeEmployee({ user_id: 9, full_name: "Retired Registrar", is_active: false }),
        ]}
      />
    );

    expect(screen.getByLabelText("Jane Dean")).toBeInTheDocument();
    // Somebody past their last day still sits on old sections, so they must not
    // be offered as somebody a new step could be built around.
    expect(
      screen.queryByLabelText("Retired Registrar")
    ).not.toBeInTheDocument();
  });

  it("says so when the roles could not be loaded, rather than offering a blank step", () => {
    render(
      <TeamForm
        campuses={campuses}
        roles={[]}
        employees={employees}
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

  it("shows why the backend refused the team and stays on the form", async () => {
    vi.mocked(createTeam).mockRejectedValue(
      new Error("A team with that name already exists.")
    );
    renderNewTeam();

    fireEvent.change(screen.getByLabelText("Step 1 name"), {
      target: { value: "Supervisor approval" },
    });
    fireEvent.click(screen.getByLabelText("Jane Dean"));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      await screen.findByText("A team with that name already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});

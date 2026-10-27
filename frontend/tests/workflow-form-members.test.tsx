import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowForm } from "@/components/hr/workflow-form";
import { makeTeam } from "@/lib/teams/__fixtures__";
import type { WorkflowMemberPool } from "@/lib/team-members";
import { getWorkflowMemberPool } from "@/lib/team-members-client";
import {
  createOrReuseApproverRole,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles-client";
import { listEligibleApprovers } from "@/lib/teams-client";
import type { EligibleApprover } from "@/lib/teams";
import type { Workflow, WorkflowSection } from "@/lib/workflows";
import { createWorkflow, updateWorkflow } from "@/lib/workflows-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/team-members-client", () => ({
  listTeamMembers: vi.fn(),
  addTeamMembers: vi.fn(),
  removeTeamMember: vi.fn(),
  getWorkflowMemberPool: vi.fn(),
  removeWorkflowMember: vi.fn(),
}));

vi.mock("@/lib/workflows-client", () => ({
  createWorkflow: vi.fn(),
  updateWorkflow: vi.fn(),
}));

vi.mock("@/lib/teams-client", () => ({
  listEligibleApprovers: vi.fn(),
}));

vi.mock("@/lib/approver-roles-client", () => ({
  listRoleAssignments: vi.fn(),
  listTeamRoleAssignments: vi.fn(),
  listCampusRoleAssignments: vi.fn(),
  createOrReuseApproverRole: vi.fn(),
}));

const roles = [
  {
    id: 1,
    code: "supervisor",
    label: "Supervisor",
    description: "",
    is_active: true,
    history_scope: "section" as const,
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: false,
    usage: [],
    created_at: "",
    updated_at: "",
  },
];

const team = makeTeam({ id: 4, name: "Bunda College Faculty" });

function makePool(
  overrides: Partial<WorkflowMemberPool> = {}
): WorkflowMemberPool {
  return {
    team: { id: 4, name: "Bunda College Faculty", code: "bunda-faculty" },
    workflow: null,
    available: [
      {
        id: 31,
        user: 31,
        full_name: "Ruth Member",
        email: "ruth@test.luanar",
        designation: "Lecturer",
        category: "academic",
        faculty: "Agriculture",
        grade: "G",
        is_active: true,
      },
      {
        id: 32,
        user: 32,
        full_name: "Sam Candidate",
        email: "sam@test.luanar",
        designation: "Assistant",
        category: "administration",
        faculty: "",
        grade: "A",
        is_active: true,
      },
    ],
    current: [],
    assigned_elsewhere: [],
    ...overrides,
  };
}

function makeElsewherePool(): WorkflowMemberPool {
  return makePool({
    available: [],
    assigned_elsewhere: [
      {
        id: 33,
        user: 33,
        full_name: "Alan Elsewhere",
        email: "alan@test.luanar",
        designation: "Officer",
        category: "administration",
        faculty: "Faculty of Social Sciences",
        grade: "C",
        is_active: true,
        workflow_id: 9,
        workflow_name: "Registry Operations workflow",
        kind: "member",
      },
      {
        id: 34,
        user: 34,
        full_name: "Bea Approver",
        email: "bea@test.luanar",
        designation: "HOD",
        category: "academic",
        faculty: "Agriculture",
        grade: "D",
        is_active: true,
        workflow_id: 9,
        workflow_name: "Registry Operations workflow",
        kind: "step",
      },
    ],
  });
}

function makeWorkflow(overrides: Partial<Workflow> = {}): Workflow {
  return {
    id: 1,
    name: "Academic approval",
    team: 4,
    team_name: "Bunda College Faculty",
    effective_from: null,
    effective_to: null,
    is_active: true,
    state: "standby",
    is_routing: false,
    section_count: 1,
    sections: [],
    members: [],
    ...overrides,
  };
}

/** One concrete step, for fixtures whose page one has to be valid. */
function makeSection(
  overrides: Partial<WorkflowSection> = {}
): WorkflowSection {
  return {
    id: 7,
    name: "Supervisor",
    order: 1,
    is_active: true,
    approver_role: "supervisor",
    approver_role_label: "Supervisor",
    approver: null,
    approver_name: null,
    resolution: {
      source: "section",
      automatic: false,
      user: null,
      user_name: null,
      label: "Not appointed",
    },
    description: "",
    members: [],
    member_count: 0,
    memberships: [],
    ...overrides,
  };
}

/** A chain carries its own name; the form refuses a blank one on save. */
function fillName(value = "Academic approval") {
  fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
    target: { value },
  });
}

/**
 * Walks from step configuration to the member page.
 *
 * The form validates the name and the steps before it moves on, so every test
 * that wants the member list has to describe a valid chain first.
 */
function continueToMembers() {
  fireEvent.click(screen.getByRole("button", { name: "Continue to members" }));
}

/**
 * Puts the first offerable person on the chain.
 *
 * A workflow only saves once somebody is on it, so every test that submits
 * from the member page has to add a member first. Adding is a single decision
 * made in a picker, so this walks through the dialog rather than clicking a row.
 */
async function addFirstMember() {
  fireEvent.click(
    await screen.findByRole("button", { name: "Add employees" })
  );
  const dialog = await screen.findByRole("dialog");
  fireEvent.click(
    within(dialog).getByRole("checkbox", { name: "Ruth Member" })
  );
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Add 1 member" })
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listEligibleApprovers).mockResolvedValue([]);
  vi.mocked(listRoleAssignments).mockResolvedValue([]);
  vi.mocked(listTeamRoleAssignments).mockResolvedValue([]);
  vi.mocked(listCampusRoleAssignments).mockResolvedValue([]);
});

describe("WorkflowForm members section", () => {
  it("loads the eligibility pool and offers addable team members", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());

    render(
      <WorkflowForm team={team} roles={roles} />
    );

    // Step configuration comes first; the member pool is only shown once the
    // chain has a name and a step.
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();

    const progress = within(
      screen.getByRole("group", { name: "Form progress" })
    );
    expect(progress.getByText("Steps").closest("li")).toHaveAttribute(
      "data-state",
      "completed"
    );
    expect(progress.getByText("Members").closest("li")).toHaveAttribute(
      "data-state",
      "current"
    );

    expect(screen.getByText("Loading members...")).toBeInTheDocument();

    await screen.findByRole("button", { name: "Add employees" });
    expect(getWorkflowMemberPool).toHaveBeenCalledWith(4, undefined);
    expect(
      screen.getByRole("button", { name: "Add employees" })
    ).toBeInTheDocument();
  });

  it("adds several members in one selection", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());

    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();
    await screen.findByRole("button", { name: "Add employees" });

    fireEvent.click(screen.getByRole("button", { name: "Add employees" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Select all shown" })
    );
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Add 2 members" })
    );

    expect(screen.getByText("On this chain (2)")).toBeInTheDocument();
    expect(screen.getByText("Ruth Member")).toBeInTheDocument();
    expect(screen.getByText("Sam Candidate")).toBeInTheDocument();
  });

  it("pre-fills the current members of an edited workflow", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(
      makePool({
        workflow: { id: 1, name: "Academic approval", state: "standby", is_active: true, is_routing: false },
        current: [
          {
            id: 31,
            user: 31,
            full_name: "Ruth Member",
            email: "ruth@test.luanar",
            designation: "Lecturer",
            category: "academic",
            faculty: "Agriculture",
            grade: "G",
            is_active: true,
          },
        ],
      })
    );

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          sections: [makeSection()],
          members: [
            {
              id: 1,
              workflow: 1,
              workflow_name: "Academic approval",
              user: 31,
              user_name: "Ruth Member",
              user_email: "ruth@test.luanar",
              designation: "Lecturer",
              team: 4,
              team_name: "Bunda College Faculty",
              added_by: 1,
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        })}
      />
    );

    // The chain already has a name and a step, so page one is valid as it is.
    continueToMembers();

    expect(
      await screen.findByText(/On this chain/)
    ).toBeInTheDocument();
    expect(screen.getByText("Ruth Member")).toBeInTheDocument();
    expect(getWorkflowMemberPool).toHaveBeenCalledWith(4, 1);
  });

  it("adds and removes a member and submits the chosen ids", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(
      screen.getByRole("button", { name: "Add step" })
    );
    continueToMembers();
    await screen.findByRole("button", { name: "Add employees" });

    await addFirstMember();
    expect(screen.getByText(/On this chain/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({ members: [31], team: 4 })
      )
    );
    // It lands on the team's workflow list under /dashboard, which is where the
    // report actually lives: /organisation/teams/... is not a route.
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/dashboard/teams/4/workflows")
    );
  });

  it("will not save a chain with nobody on it", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());

    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();
    await screen.findByRole("button", { name: "Add employees" });

    expect(
      screen.getByRole("button", { name: "Create workflow" })
    ).toBeDisabled();
    expect(
      screen.getByText("Add at least one member to save this chain.")
    ).toBeInTheDocument();

    // Nothing writes through the form: not an implicit submit, and not a click
    // that jsdom still delivers to the disabled button.
    fireEvent.submit(
      screen.getByRole("button", { name: "Create workflow" }).closest("form")!
    );
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    expect(createWorkflow).not.toHaveBeenCalled();
    expect(screen.getByText("Normal workflow members")).toBeInTheDocument();
  });

  it("ignores the second click of a double-click on save", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();
    await addFirstMember();

    const save = screen.getByRole("button", { name: "Create workflow" });

    // A click that belongs to a double-click arrives here with detail 2. That
    // is not consent to save, and must not write the chain.
    fireEvent.click(save, { detail: 2 });
    expect(createWorkflow).not.toHaveBeenCalled();

    // A deliberate single click still saves.
    fireEvent.click(save, { detail: 1 });
    await waitFor(() => expect(createWorkflow).toHaveBeenCalledTimes(1));
  });

  it("ignores a second click that lands where Continue was", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(
      makePool({
        workflow: {
          id: 1,
          name: "Academic approval",
          state: "standby",
          is_active: true,
          is_routing: false,
        },
        current: [
          {
            id: 31,
            user: 31,
            full_name: "Ruth Member",
            email: "ruth@test.luanar",
            designation: "Lecturer",
            category: "academic",
            faculty: "Agriculture",
            grade: "G",
            is_active: true,
          },
        ],
      })
    );
    vi.mocked(updateWorkflow).mockResolvedValue(makeWorkflow());

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          sections: [makeSection()],
          members: [
            {
              id: 1,
              workflow: 1,
              workflow_name: "Academic approval",
              user: 31,
              user_name: "Ruth Member",
              user_email: "ruth@test.luanar",
              designation: "Lecturer",
              team: 4,
              team_name: "Bunda College Faculty",
              added_by: 1,
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        })}
      />
    );

    // A real pointer click on Continue, at the point the button occupies.
    fireEvent.click(screen.getByRole("button", { name: "Continue to members" }), {
      detail: 1,
      clientX: 416,
      clientY: 871,
    });

    const save = screen.getByRole("button", { name: "Save workflow" });

    // The member page replaces the steps page under the same pointer, so the
    // next click is at the old spot — now on Save. It belongs to the gesture
    // that opened the page, not to a decision to write it, even though the
    // browser reports it as an ordinary single click.
    fireEvent.click(save, { detail: 1, clientX: 416, clientY: 871 });
    expect(updateWorkflow).not.toHaveBeenCalled();
    expect(createWorkflow).not.toHaveBeenCalled();

    // Choosing save means moving to it and clicking there.
    fireEvent.click(save, { detail: 1, clientX: 700, clientY: 900 });
    await waitFor(() => expect(updateWorkflow).toHaveBeenCalledTimes(1));
  });

  it("saves once the pointer has moved away from Continue", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(
      makePool({
        workflow: {
          id: 1,
          name: "Academic approval",
          state: "standby",
          is_active: true,
          is_routing: false,
        },
        current: [
          {
            id: 31,
            user: 31,
            full_name: "Ruth Member",
            email: "ruth@test.luanar",
            designation: "Lecturer",
            category: "academic",
            faculty: "Agriculture",
            grade: "G",
            is_active: true,
          },
        ],
      })
    );
    vi.mocked(updateWorkflow).mockResolvedValue(makeWorkflow());

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          sections: [makeSection()],
          members: [
            {
              id: 1,
              workflow: 1,
              workflow_name: "Academic approval",
              user: 31,
              user_name: "Ruth Member",
              user_email: "ruth@test.luanar",
              designation: "Lecturer",
              team: 4,
              team_name: "Bunda College Faculty",
              added_by: 1,
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        })}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Continue to members" }), {
      detail: 1,
      clientX: 416,
      clientY: 871,
    });

    const save = screen.getByRole("button", { name: "Save workflow" });
    // Save sits almost exactly where Continue was, so the only thing that
    // separates a stray repeat click from a decision is the pointer travelling
    // to the button: once it has, the click is a fresh choice and must write.
    window.dispatchEvent(
      new MouseEvent("pointermove", { clientX: 900, clientY: 600 })
    );

    fireEvent.click(save, { detail: 1, clientX: 416, clientY: 871 });
    await waitFor(() => expect(updateWorkflow).toHaveBeenCalledTimes(1));
  });

  it("keeps people on another chain behind a list button", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makeElsewherePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();

    // The list is a statement about people who cannot join, so it waits behind
    // a button instead of taking space beside the people who can.
    const listButton = await screen.findByRole("button", {
      name: "View 2 employees already on another chain",
    });
    expect(screen.queryByText("Alan Elsewhere")).not.toBeInTheDocument();
    expect(screen.queryByText("Bea Approver")).not.toBeInTheDocument();

    // Neither a normal member nor a step approver of another chain may join
    // this one, so there is no add action and the chain cannot be saved with
    // nobody on it.
    expect(
      screen.queryByRole("button", { name: "Move here" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add" })
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/On this chain/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create workflow" })
    ).toBeDisabled();

    fireEvent.click(listButton);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Already on another chain")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/one chain of Bunda College Faculty at a time/)
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Alan Elsewhere")).toBeInTheDocument();
    expect(within(dialog).getByText("Bea Approver")).toBeInTheDocument();
    expect(
      within(dialog).getByText("Officer · alan@test.luanar")
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("On Registry Operations workflow")
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Approves a step on Registry Operations workflow")
    ).toBeInTheDocument();
    // Reading the list is not a way to add somebody from it.
    expect(
      within(dialog).queryByRole("button", { name: "Add" })
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByRole("button", { name: "Move here" })
    ).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Close list" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(screen.queryByText("Alan Elsewhere")).not.toBeInTheDocument();
  });
});

describe("WorkflowForm page split", () => {
  it("refuses to show the member page until the steps are complete", () => {
    render(<WorkflowForm team={team} roles={roles} />);

    // Nothing is described yet, so there is no chain for members to join.
    fillName();
    continueToMembers();

    expect(
      screen.getByText("Add at least one step, then continue to members.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Normal workflow members")).not.toBeInTheDocument();
    const progress = within(
      screen.getByRole("group", { name: "Form progress" })
    );
    expect(progress.getByText("Steps").closest("li")).toHaveAttribute(
      "data-state",
      "current"
    );
  });

  it("opens the member page without writing the chain", () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    const next = screen.getByRole("button", { name: "Continue to members" });
    // A plain button, so the browser cannot turn the click into a form submit
    // (Enter, autofill, or the default button of the form).
    expect(next).toHaveAttribute("type", "button");

    fireEvent.click(next);

    // Continuing is a page change, not a write: no step, name or member list
    // leaves the browser until the member page's own save is clicked.
    expect(screen.getByText("Normal workflow members")).toBeInTheDocument();
    expect(createWorkflow).not.toHaveBeenCalled();
    expect(updateWorkflow).not.toHaveBeenCalled();
    // The forwarded action is gone once the page has moved, so a second click
    // in the same place cannot repeat it.
    expect(
      screen.queryByRole("button", { name: "Continue to members" })
    ).not.toBeInTheDocument();
  });

  it("puts the write action away from where Continue was", () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();

    const save = screen.getByRole("button", { name: "Create workflow" });
    const back = screen.getByRole("button", { name: "Back to steps" });
    const cancel = screen.getByRole("button", { name: "Cancel" });

    // The leading action where Continue was is the harmless way back, not the
    // write: a click that repeats the Continue gesture lands on "Back to
    // steps" and never saves. The write sits after both secondary actions, in
    // a group of its own.
    expect(back.parentElement).toBe(cancel.parentElement);
    expect(save.parentElement).not.toBe(back.parentElement);
    expect(
      back.compareDocumentPosition(cancel) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      cancel.compareDocumentPosition(save) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();

    fireEvent.click(back);
    expect(createWorkflow).not.toHaveBeenCalled();
    expect(updateWorkflow).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
  });

  it("does not reuse the Continue button as the save button", () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    const next = screen.getByRole("button", { name: "Continue to members" });
    next.focus();
    expect(document.activeElement).toBe(next);

    fireEvent.click(next);

    // The action rows are keyed, so React mounts a fresh button rather than
    // turning the focused Continue into a focused save. Otherwise a keystroke
    // meant for the page that just closed could write the chain.
    const save = screen.getByRole("button", { name: "Create workflow" });
    expect(save).not.toBe(next);
    expect(document.activeElement).not.toBe(save);
    expect(createWorkflow).not.toHaveBeenCalled();
  });

  it("does not save an edited chain's steps from Continue", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({ sections: [makeSection()] })}
      />
    );

    continueToMembers();

    expect(screen.getByText("Normal workflow members")).toBeInTheDocument();
    // Re-saving an edit must PATCH, and only the member page's save does that.
    expect(updateWorkflow).not.toHaveBeenCalled();
    expect(createWorkflow).not.toHaveBeenCalled();
  });

  it("goes back to the steps from the member page", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    continueToMembers();

    expect(screen.getByText("Normal workflow members")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back to steps" }));
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveValue(
      "Academic approval"
    );
  });

  it("advances from the name field on Enter rather than saving the chain", () => {
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    fireEvent.keyDown(screen.getByRole("textbox", { name: "Name" }), {
      key: "Enter",
    });

    expect(screen.getByText("Normal workflow members")).toBeInTheDocument();
    expect(createWorkflow).not.toHaveBeenCalled();
  });
});

describe("WorkflowForm approver picker", () => {
  const sam: EligibleApprover = {
    id: 32,
    full_name: "Sam Candidate",
    email: "sam@test.luanar",
    designation: "Assistant",
  };
  const ruth: EligibleApprover = {
    id: 31,
    full_name: "Ruth Member",
    email: "ruth@test.luanar",
    designation: "Lecturer",
  };

  it("loads candidates scoped to the role and a new chain, and submits the chosen approver", async () => {
    vi.mocked(listEligibleApprovers).mockResolvedValue([sam, ruth]);
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByRole("combobox", { name: /approver/i });
    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1, "new");

    fireEvent.change(
      screen.getByRole("combobox", { name: /approver/i }),
      { target: { value: "32" } }
    );
    fillName();
    continueToMembers();
    await addFirstMember();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: expect.arrayContaining([
            expect.objectContaining({ approver: 32 }),
          ]),
        })
      )
    );
  });

  it("pre-fills the current approver of an edited chain and scopes candidates to it", async () => {
    vi.mocked(listEligibleApprovers).mockResolvedValue([ruth]);

    render(
      <WorkflowForm
        team={team}
        roles={roles}
        workflow={makeWorkflow({
          sections: [
            {
              id: 7,
              name: "Supervisor",
              order: 1,
              is_active: true,
              approver_role: "supervisor",
              approver_role_label: "Supervisor",
              approver: 31,
              approver_name: "Ruth Member",
              resolution: {
                source: "section",
                automatic: false,
                user: 31,
                user_name: "Ruth Member",
                label: "Ruth Member",
              },
              description: "",
              members: [],
              member_count: 0,
              memberships: [],
            },
          ],
        })}
      />
    );

    expect(listEligibleApprovers).toHaveBeenCalledWith(4, 1, 1);
    const select = await screen.findByRole("combobox", {
      name: /approver/i,
    });
    expect((select as HTMLSelectElement).value).toBe("31");
    expect(
      screen.getByRole("option", { name: "Ruth Member" })
    ).toBeInTheDocument();
  });
});

describe("WorkflowForm institution-wide auto-appointment", () => {
  const adminTeam = makeTeam({
    id: 4,
    name: "ICT Team",
    category: "administration",
  });

  const wideRoles = [
    ...roles,
    {
      id: 2,
      code: "registrar",
      label: "Registrar",
      description: "",
      is_active: true,
      history_scope: "section" as const,
      handles_cancellation: false,
      is_institution_wide: true,
      is_in_use: false,
      usage: [],
      created_at: "",
      updated_at: "",
    },
  ];

  const dingo = { id: 40, full_name: "Dingo Dean", email: "", designation: "" };

  it("locks the approver of an institution-wide step to its holder and submits that id", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={adminTeam} roles={wideRoles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    await screen.findByText("Dingo Dean");
    expect(
      screen.queryByText("Locked to the institution-wide holder of this role.")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    continueToMembers();
    await addFirstMember();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: expect.arrayContaining([
            expect.objectContaining({ approver: 40 }),
          ]),
        })
      )
    );
  });

  it("leaves an institution-wide step unstaffed when no single holder exists", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
      {
        id: 10,
        user: 41,
        user_name: "Pat Principal",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);

    render(<WorkflowForm team={adminTeam} roles={wideRoles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    const select = await screen.findByRole("combobox", {
      name: "Approver",
    });
    expect((select as HTMLSelectElement).value).toBe("");
  });

  it("does not fill an institution-wide step on an academic team", async () => {
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([dingo]);

    render(
      <WorkflowForm
        team={makeTeam({ id: 4, category: "academic" })}
        roles={wideRoles}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(
      screen.getByRole("combobox", { name: "Role" }),
      { target: { value: "registrar" } }
    );

    const select = await screen.findByRole("combobox", {
      name: "Approver",
    });
    expect((select as HTMLSelectElement).value).toBe("");
  });
});

describe("WorkflowForm wide approver locking", () => {
  const academicTeam = makeTeam({ id: 4, campus: 3, category: "academic" });

  function teamHolding(user: number, name: string) {
    return {
      id: 20,
      team: 4,
      role: 1,
      user,
      user_name: name,
      role_label: "Supervisor",
      is_team_manager: false,
      created_at: "",
    };
  }

  function campusHolding(user: number, name: string) {
    return {
      id: 21,
      campus: 3,
      role: 1,
      user,
      user_name: name,
      role_label: "Supervisor",
      created_at: "",
    };
  }

  it("locks a step to its team-wide holder and submits that person", async () => {
    vi.mocked(listTeamRoleAssignments).mockResolvedValue([
      teamHolding(50, "Tina Team"),
    ]);
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Tina Team");
    expect(listTeamRoleAssignments).toHaveBeenCalledWith(4);
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    continueToMembers();
    await addFirstMember();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: 50 }],
        })
      )
    );
  });

  it("falls back to the campus-wide holder when the team has none", async () => {
    vi.mocked(listCampusRoleAssignments).mockResolvedValue([
      campusHolding(51, "Cara Campus"),
    ]);
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Cara Campus");
    expect(listCampusRoleAssignments).toHaveBeenCalledWith(3);
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();

    fillName();
    continueToMembers();
    await addFirstMember();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: 51 }],
        })
      )
    );
  });

  it("prefers the team-wide holder over the campus-wide one", async () => {
    vi.mocked(listTeamRoleAssignments).mockResolvedValue([
      teamHolding(50, "Tina Team"),
    ]);
    vi.mocked(listCampusRoleAssignments).mockResolvedValue([
      campusHolding(51, "Cara Campus"),
    ]);

    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await screen.findByText("Tina Team");
    expect(screen.queryByText("Cara Campus")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "Approver" })
    ).not.toBeInTheDocument();
  });

  it("keeps the picker when the role has no wide holder", async () => {
    render(<WorkflowForm team={academicTeam} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    await waitFor(() => expect(listTeamRoleAssignments).toHaveBeenCalled());
    expect(
      screen.getByRole("combobox", { name: "Approver" })
    ).toBeInTheDocument();
  });

  it("does not read campus holdings for a team with no campus", async () => {
    render(<WorkflowForm team={makeTeam({ campus: null })} roles={roles} />);

    await waitFor(() => expect(listTeamRoleAssignments).toHaveBeenCalled());
    expect(listCampusRoleAssignments).not.toHaveBeenCalled();
  });
});

describe("WorkflowForm step roles", () => {
  const registrar = {
    ...roles[0],
    id: 2,
    code: "registrar",
    label: "Registrar",
  };

  it("starts a new step on a role no other step uses", () => {
    render(<WorkflowForm team={team} roles={[roles[0], registrar]} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    // The second step would otherwise open on the role step one already took,
    // which the form refuses as a duplicate before it can move on.
    const roleSelects = screen.getAllByRole("combobox", { name: "Role" });
    expect((roleSelects[0] as HTMLSelectElement).value).toBe("supervisor");
    expect((roleSelects[1] as HTMLSelectElement).value).toBe("registrar");

    // Taking the role a step already holds is still refused in the picker.
    expect(
      screen.getByRole("option", { name: "Supervisor — used in step 1" })
    ).toBeDisabled();
  });

  it("stops adding steps once every role is on one", () => {
    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    // One role, one step: another step could only repeat the role, so there is
    // nothing valid to add until a role is created.
    expect(screen.getByRole("button", { name: "Add step" })).toBeDisabled();
    expect(
      screen.getByText(
        "Every role is already on a step. Use “New role” to add another."
      )
    ).toBeInTheDocument();
  });
});

describe("WorkflowForm page-one submit guard", () => {
  it("leaves an implicit submit on the steps page inert", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    // Enter in a field or select can submit the form even though page one has
    // no save button. Only a click on Continue moves on, so an implicit submit
    // neither saves nor jumps past a page the viewer chose to stay on.
    fireEvent.submit(
      screen.getByRole("textbox", { name: "Name" }).closest("form")!
    );

    expect(createWorkflow).not.toHaveBeenCalled();
    expect(
      screen.queryByText("Normal workflow members")
    ).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
  });

  it("names and focuses the missing name when continuing", () => {
    render(<WorkflowForm team={team} roles={roles} />);
    continueToMembers();

    expect(
      screen.getByText("Give this chain a name before continuing.")
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveFocus();
    expect(
      screen.queryByText("Normal workflow members")
    ).not.toBeInTheDocument();
  });

  it("points at Add step when no step has been described", () => {
    render(<WorkflowForm team={team} roles={roles} />);
    fillName();
    continueToMembers();

    expect(
      screen.getByText("Add at least one step, then continue to members.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add step" })).toHaveFocus();
  });

  it("still responds when no approver roles are available", () => {
    render(<WorkflowForm team={team} roles={[]} />);
    fillName();
    continueToMembers();

    expect(
      screen.getByText(/No approver roles are available/)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New role" })).toHaveFocus();
  });
});

describe("WorkflowForm step naming", () => {
  it("takes the step name from its role and offers no name box", async () => {
    vi.mocked(getWorkflowMemberPool).mockResolvedValue(makePool());
    vi.mocked(createWorkflow).mockResolvedValue(makeWorkflow());

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));

    // There is no step-name control at all: the step is named by the role it
    // selects, and the payload carries no name.
    expect(screen.queryByText("Step name")).not.toBeInTheDocument();

    fillName();
    continueToMembers();
    await addFirstMember();
    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));

    await waitFor(() =>
      expect(createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: [{ order: 1, approver_role: "supervisor", approver: null }],
        })
      )
    );
  });

  it("locks an institution-wide step to its holder without a name box", async () => {
    const wideRoles = [
      ...roles,
      {
        ...roles[0],
        id: 2,
        code: "registrar",
        label: "Registrar",
        is_institution_wide: true,
      },
    ];
    vi.mocked(listRoleAssignments).mockResolvedValue([
      {
        id: 9,
        user: 40,
        user_name: "Dingo Dean",
        role: 2,
        role_label: "Registrar",
        created_at: "",
      },
    ]);
    vi.mocked(listEligibleApprovers).mockResolvedValue([
      { id: 40, full_name: "Dingo Dean", email: "", designation: "" },
    ]);

    render(
      <WorkflowForm
        team={makeTeam({ id: 4, category: "administration" })}
        roles={wideRoles}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Role" }), {
      target: { value: "registrar" },
    });

    await screen.findByText("Dingo Dean");
    expect(screen.queryByText("Step name")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Locked to the institution-wide holder of this role.")
    ).not.toBeInTheDocument();
  });
});

describe("WorkflowForm new role card", () => {
  const createdRole = {
    ...roles[0],
    id: 9,
    code: "examinations-officer",
    label: "Examinations Officer",
  };

  it("adds a role by name and makes it selectable on a step", async () => {
    vi.mocked(createOrReuseApproverRole).mockResolvedValue({
      role: createdRole,
      created: true,
    });

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Role name" }), {
      target: { value: "Examinations Officer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    await waitFor(() =>
      expect(createOrReuseApproverRole).toHaveBeenCalledWith(
        "Examinations Officer"
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    expect(
      await screen.findByRole("option", { name: "Examinations Officer" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Added Examinations Officer.")
    ).toBeInTheDocument();
  });

  it("reuses the existing role instead of claiming a duplicate was made", async () => {
    vi.mocked(createOrReuseApproverRole).mockResolvedValue({
      role: createdRole,
      created: false,
    });

    render(<WorkflowForm team={team} roles={roles} />);
    fireEvent.click(screen.getByRole("button", { name: "New role" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Role name" }), {
      target: { value: "examinations officer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    expect(
      await screen.findByText(/already exists — using it/i)
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    // Folded into the list once, not appended twice.
    expect(
      screen.getAllByRole("option", { name: "Examinations Officer" })
    ).toHaveLength(1);
  });
});
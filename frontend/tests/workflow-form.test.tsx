import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkflowForm } from "@/components/hr/workflow-form";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Workflow } from "@/lib/workflows";

function makeRole(overrides: Partial<ApproverRole> = {}): ApproverRole {
  return {
    id: 1,
    code: "supervisor",
    label: "Supervisor",
    description: "",
    is_active: true,
    history_scope: "all",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: false,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/** The roles HR has defined, including one this build's code never named. */
const roles: ApproverRole[] = [
  makeRole(),
  makeRole({ id: 2, code: "hod", label: "Head of Department" }),
  makeRole({ id: 3, code: "chief_auditor", label: "Chief Auditor" }),
];

const workflow: Workflow = {
  id: 1,
  name: "Academic approval",
  employee_category: "academic",
  department: "Faculty of Science",
  effective_from: "2026-09-01",
  is_active: true,
  state: "active",
  stages: [
    { id: 1, order: 1, approver_role: "supervisor", approver_role_label: "Supervisor" },
    { id: 2, order: 2, approver_role: "hod", approver_role_label: "Head of Department" },
  ],
};

function roleOptions(select: HTMLElement): string[] {
  return Array.from(select.querySelectorAll("option")).map(
    (option) => option.getAttribute("value") ?? ""
  );
}

describe("WorkflowForm", () => {
  it("renders workflow fields for a new workflow", () => {
    render(<WorkflowForm roles={roles} />);

    expect(screen.getByLabelText("Workflow name")).toBeInTheDocument();
    expect(screen.getByLabelText("Employee category")).toBeInTheDocument();
    expect(screen.getByLabelText("Department / Faculty")).toBeInTheDocument();
    expect(screen.getByText("Approval stages")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add stage" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create workflow" })
    ).toBeInTheDocument();
  });

  it("offers an Any category option and both categories", () => {
    render(<WorkflowForm roles={roles} />);

    const select = screen.getByLabelText("Employee category");
    const options = Array.from(
      select.querySelectorAll("option")
    ).map((option) => option.textContent);
    expect(options).toEqual(["Any category", "Academic", "Administration"]);
  });

  it("offers exactly the roles HR has defined, with no built-in extras", () => {
    render(<WorkflowForm roles={roles} />);

    // A role this build has no code for is offered like any other, and nothing
    // appears that HR did not create.
    expect(roleOptions(screen.getByLabelText("Stage 1 approver"))).toEqual([
      "supervisor",
      "hod",
      "chief_auditor",
    ]);
  });

  it("prefills values when editing an existing workflow", () => {
    render(<WorkflowForm workflow={workflow} roles={roles} />);

    expect(screen.getByLabelText("Workflow name")).toHaveValue(
      "Academic approval"
    );
    expect(screen.getByLabelText("Employee category")).toHaveValue("academic");
    expect(screen.getByLabelText("Department / Faculty")).toHaveValue(
      "Faculty of Science"
    );
    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("supervisor");
    expect(screen.getByLabelText("Stage 2 approver")).toHaveValue("hod");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("hides the active checkbox while the workflow is a draft", () => {
    render(<WorkflowForm roles={roles} />);

    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.queryByLabelText("Active")).not.toBeInTheDocument();
  });

  it("shows the active checkbox once an effective date is set", () => {
    render(<WorkflowForm roles={roles} />);

    fireEvent.change(screen.getByLabelText("Effective from"), {
      target: { value: "2026-12-01" },
    });
    expect(screen.getByLabelText("Active")).toBeInTheDocument();
  });

  it("prefills the effective date and active state when editing", () => {
    render(<WorkflowForm workflow={workflow} roles={roles} />);

    expect(screen.getByLabelText("Effective from")).toHaveValue(
      "2026-09-01"
    );
    expect(screen.getByLabelText("Active")).toBeChecked();
  });

  it("starts a new workflow with one stage, seeded with the first role", () => {
    render(<WorkflowForm roles={roles} />);

    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("supervisor");
    expect(screen.queryByLabelText("Stage 2 approver")).not.toBeInTheDocument();
  });

  it("adds a stage and reorders with move controls", () => {
    render(<WorkflowForm roles={roles} />);

    fireEvent.click(screen.getByRole("button", { name: "Add stage" }));
    expect(screen.getByLabelText("Stage 2 approver")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Stage 2 approver"), {
      target: { value: "chief_auditor" },
    });
    expect(screen.getByLabelText("Stage 2 approver")).toHaveValue(
      "chief_auditor"
    );

    fireEvent.click(screen.getByRole("button", { name: "Move stage 2 up" }));
    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue(
      "chief_auditor"
    );
    expect(screen.getByLabelText("Stage 2 approver")).toHaveValue("supervisor");
  });

  it("removes a stage with its remove control", () => {
    render(<WorkflowForm workflow={workflow} roles={roles} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove stage 1" }));
    expect(screen.queryByLabelText("Stage 2 approver")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("hod");
  });

  it("disables move-up on the first stage and move-down on the last", () => {
    render(<WorkflowForm workflow={workflow} roles={roles} />);

    expect(
      screen.getByRole("button", { name: "Move stage 1 up" })
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Move stage 2 down" })
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Move stage 2 up" })
    ).not.toBeDisabled();
  });

  it("keeps a retired role on a saved stage selectable, flagged as inactive", () => {
    const retired: ApproverRole[] = [roles[0]];
    render(
      <WorkflowForm
        workflow={{
          ...workflow,
          stages: [
            { id: 1, order: 1, approver_role: "hod", approver_role_label: "Head of Department" },
          ],
        }}
        roles={retired}
      />
    );

    const select = screen.getByLabelText("Stage 1 approver");
    // The value is preserved rather than snapping to whatever role is still
    // active, so saving without a deliberate change cannot reroute a chain.
    expect(select).toHaveValue("hod");
    expect(
      screen.getByRole("option", { name: "hod (no longer active)" })
    ).toBeInTheDocument();
  });

  it("refuses to render a usable form when the roles could not be loaded", () => {
    render(
      <WorkflowForm
        roles={[]}
        rolesError="Unable to load approver roles, so a stage cannot be given an approver."
      />
    );

    expect(
      screen.getByText(
        "Unable to load approver roles, so a stage cannot be given an approver."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add stage" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create workflow" })).toBeDisabled();
  });

  it("provides a cancel link back to the workflows index", () => {
    render(<WorkflowForm roles={roles} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/workflows"
    );
  });
});

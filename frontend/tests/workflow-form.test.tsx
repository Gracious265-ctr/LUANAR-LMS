import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkflowForm } from "@/components/hr/workflow-form";
import type { Workflow } from "@/lib/workflows";

const workflow: Workflow = {
  id: 1,
  name: "Academic approval",
  employee_category: "academic",
  department: "Faculty of Science",
  effective_from: "2026-09-01",
  is_active: true,
  state: "active",
  stages: [
    { id: 1, order: 1, approver_role: "supervisor" },
    { id: 2, order: 2, approver_role: "hod" },
  ],
};

describe("WorkflowForm", () => {
  it("renders workflow fields for a new workflow", () => {
    render(<WorkflowForm />);

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
    render(<WorkflowForm />);

    const select = screen.getByLabelText("Employee category");
    const options = Array.from(
      select.querySelectorAll("option")
    ).map((option) => option.textContent);
    expect(options).toEqual(["Any category", "Academic", "Administration"]);
  });

  it("prefills values when editing an existing workflow", () => {
    render(<WorkflowForm workflow={workflow} />);

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
    render(<WorkflowForm />);

    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.queryByLabelText("Active")).not.toBeInTheDocument();
  });

  it("shows the active checkbox once an effective date is set", () => {
    render(<WorkflowForm />);

    fireEvent.change(screen.getByLabelText("Effective from"), {
      target: { value: "2026-12-01" },
    });
    expect(screen.getByLabelText("Active")).toBeInTheDocument();
  });

  it("prefills the effective date and active state when editing", () => {
    render(<WorkflowForm workflow={workflow} />);

    expect(screen.getByLabelText("Effective from")).toHaveValue(
      "2026-09-01"
    );
    expect(screen.getByLabelText("Active")).toBeChecked();
  });

  it("starts a new workflow with one stage by default", () => {
    render(<WorkflowForm />);

    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("supervisor");
    expect(screen.queryByLabelText("Stage 2 approver")).not.toBeInTheDocument();
  });

  it("adds a stage and reorders with move controls", () => {
    render(<WorkflowForm />);

    fireEvent.click(screen.getByRole("button", { name: "Add stage" }));
    expect(screen.getByLabelText("Stage 2 approver")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Stage 2 approver"), {
      target: { value: "hod" },
    });
    expect(screen.getByLabelText("Stage 2 approver")).toHaveValue("hod");

    fireEvent.click(screen.getByRole("button", { name: "Move stage 2 up" }));
    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("hod");
    expect(screen.getByLabelText("Stage 2 approver")).toHaveValue("supervisor");
  });

  it("removes a stage with its remove control", () => {
    render(<WorkflowForm workflow={workflow} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove stage 1" }));
    expect(screen.queryByLabelText("Stage 2 approver")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Stage 1 approver")).toHaveValue("hod");
  });

  it("disables move-up on the first stage and move-down on the last", () => {
    render(<WorkflowForm workflow={workflow} />);

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

  it("provides a cancel link back to the workflows index", () => {
    render(<WorkflowForm />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/workflows"
    );
  });
});
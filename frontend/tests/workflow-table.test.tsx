import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { WorkflowTable } from "@/components/hr/workflow-table";
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
    { id: 3, order: 3, approver_role: "registrar" },
  ],
};

const anyCategoryWorkflow: Workflow = {
  ...workflow,
  id: 2,
  name: "University-wide approval",
  employee_category: "",
  department: "",
  state: "draft",
  effective_from: null,
  stages: [
    { id: 4, order: 1, approver_role: "registrar" },
    { id: 5, order: 2, approver_role: "dvc" },
  ],
};

describe("WorkflowTable", () => {
  it("renders workflow rows with scope and sequence", () => {
    render(<WorkflowTable workflows={[workflow]} />);

    expect(screen.getByText("Academic approval")).toBeInTheDocument();
    expect(
      screen.getByText("Academic / Faculty of Science")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Supervisor → Head of Department → Registrar")
    ).toBeInTheDocument();
  });

  it("renders the effective-from date and state badge", () => {
    render(<WorkflowTable workflows={[workflow]} />);

    expect(screen.getByText("2026-09-01")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows a dash and Draft state when effective date is blank", () => {
    render(<WorkflowTable workflows={[anyCategoryWorkflow]} />);

    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("shows Any category when scope is blank", () => {
    render(<WorkflowTable workflows={[anyCategoryWorkflow]} />);

    expect(screen.getByText("Any category")).toBeInTheDocument();
    expect(
      screen.getByText("Registrar → Deputy Vice-Chancellor")
    ).toBeInTheDocument();
  });

  it("links each row to the edit page", () => {
    render(<WorkflowTable workflows={[workflow]} />);

    const link = screen.getByRole("link", { name: "Academic approval" });
    expect(link.getAttribute("href")).toBe(
      "/dashboard/hr-admin/workflows/1/edit"
    );
  });

  it("renders an empty state when there are no workflows", () => {
    render(<WorkflowTable workflows={[]} />);

    expect(screen.getByText("No workflows found")).toBeInTheDocument();
  });

  it("renders a single role as its own sequence", () => {
    render(
      <WorkflowTable
        workflows={[
          {
            ...workflow,
            id: 3,
            name: "Short approval",
            state: "scheduled",
            effective_from: "2026-12-01",
            stages: [{ id: 9, order: 1, approver_role: "hr" }],
          },
        ]}
      />
    );

    expect(screen.getByText("Human Resources")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });
});
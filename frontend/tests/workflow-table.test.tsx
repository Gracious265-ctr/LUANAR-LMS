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
  sections: [
    {
      id: 1,
      name: "Direct supervisor",
      order: 1,
      approver_role: "supervisor",
      approver_role_label: "Supervisor",
      description: "",
      is_active: true,
      members: [],
      member_count: 0,
    },
    {
      id: 2,
      name: "Department head",
      order: 2,
      approver_role: "hod",
      approver_role_label: "Head of Department",
      description: "",
      is_active: true,
      members: [],
      member_count: 0,
    },
    {
      id: 3,
      name: "Registrar's office",
      order: 3,
      approver_role: "registrar",
      approver_role_label: "Registrar",
      description: "",
      is_active: true,
      members: [],
      member_count: 0,
    },
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
  sections: [
    {
      id: 4,
      name: "Registrar's office",
      order: 1,
      approver_role: "registrar",
      approver_role_label: "Registrar",
      description: "",
      is_active: true,
      members: [],
      member_count: 0,
    },
    {
      id: 5,
      name: "Deputy Vice-Chancellor",
      order: 2,
      approver_role: "dvc",
      approver_role_label: "Deputy Vice-Chancellor",
      description: "",
      is_active: true,
      members: [],
      member_count: 0,
    },
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
            sections: [
              {
                id: 9,
                name: "Human Resources",
                order: 1,
                approver_role: "hr",
                approver_role_label: "Human Resources",
                description: "",
                is_active: true,
                members: [],
                member_count: 0,
              },
            ],
          },
        ]}
      />
    );

    expect(screen.getByText("Human Resources")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows the stored label for a role this build has no entry for", () => {
    render(
      <WorkflowTable
        workflows={[
          {
            ...workflow,
            id: 4,
            name: "Late-joined role",
            sections: [
              {
                id: 10,
                name: "Chief Auditor",
                order: 1,
                approver_role: "chief_auditor",
                approver_role_label: "Chief Auditor",
                description: "",
                is_active: true,
                members: [],
                member_count: 0,
              },
            ],
          },
        ]}
      />
    );

    // HR added the role after this build shipped; the chain still reads.
    expect(screen.getByText("Chief Auditor")).toBeInTheDocument();
  });
});

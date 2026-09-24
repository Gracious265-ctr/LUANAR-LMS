import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { AuditEntriesTable } from "@/components/hr/audit-entries-table";
import { AuditActionPill } from "@/components/hr/audit-meta";
import type { AuditEntry } from "@/lib/audit";

const entry: AuditEntry = {
  id: 1,
  actor: 2,
  actor_name: "Aisha HR",
  action: "employee.created",
  target_type: "employeeprofile",
  target_id: "7",
  target_summary: "Jane Grey (Chemistry)",
  detail: {
    before: null,
    after: { department: "Chemistry" },
  },
  reason: "",
  prev_state: "",
  new_state: "",
  created_at: "2026-09-20T09:30:00Z",
};

describe("AuditEntriesTable", () => {
  it("renders actor, action, target, and changes", () => {
    render(<AuditEntriesTable entries={[entry]} />);

    expect(screen.getByText("Aisha HR")).toBeInTheDocument();
    expect(screen.getByText("Employee created")).toBeInTheDocument();
    expect(screen.getByText("Employee")).toBeInTheDocument();
    expect(screen.getByText("Jane Grey (Chemistry)")).toBeInTheDocument();
    expect(screen.getByText("department: Chemistry")).toBeInTheDocument();
  });

  it("renders an empty state when there are no entries", () => {
    render(<AuditEntriesTable entries={[]} />);

    expect(screen.getByText("No audit entries")).toBeInTheDocument();
  });

  it("links an employee target to its edit page", () => {
    render(<AuditEntriesTable entries={[entry]} />);

    const link = screen.getByRole("link", { name: "Edit" });
    expect(link).toHaveAttribute("href", "/dashboard/hr-admin/employees/7");
  });
});

describe("AuditActionPill", () => {
  it("falls back to the raw action for unknown codes", () => {
    render(<AuditActionPill action="custom.event" />);
    expect(screen.getByText("custom.event")).toBeInTheDocument();
  });
});
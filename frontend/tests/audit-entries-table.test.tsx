import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { AuditEntriesTable } from "@/components/hr/audit-entries-table";
import type { AuditEntry } from "@/lib/audit";

const baseEntry: AuditEntry = {
  id: 1,
  actor: 1,
  actor_name: "Aisha HR",
  action: "updated",
  target_type: "workflow",
  target_id: "3",
  target_summary: "Academic staff workflow",
  detail: { before: { days: 20 }, after: { days: 25 } },
  reason: "",
  created_at: "2026-09-18T12:00:00Z",
};

describe("AuditEntriesTable", () => {
  it("renders actor, action, target, changed details, and time", () => {
    render(<AuditEntriesTable entries={[baseEntry]} />);

    expect(screen.getByText("Aisha HR")).toBeInTheDocument();
    expect(screen.getByText("Updated")).toBeInTheDocument();
    expect(screen.getByText("Workflow")).toBeInTheDocument();
    expect(screen.getByText("Academic staff workflow")).toBeInTheDocument();
    expect(screen.getByText("days: 20 → 25")).toBeInTheDocument();
  });

  it("renders a reason when the entry has no field changes", () => {
    render(
      <AuditEntriesTable
        entries={[
          {
            ...baseEntry,
            action: "rejected",
            detail: null,
            reason: "Wording does not match policy.",
          },
        ]}
      />
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(
      screen.getByText("Wording does not match policy.")
    ).toBeInTheDocument();
  });

  it("shows created values when before is null", () => {
    render(
      <AuditEntriesTable
        entries={[
          {
            ...baseEntry,
            action: "created",
            detail: { before: null, after: { name: "Academic leave" } },
          },
        ]}
      />
    );

    expect(screen.getByText("Created")).toBeInTheDocument();
    expect(screen.getByText("name: Academic leave")).toBeInTheDocument();
  });

  it("renders an empty state when there are no entries", () => {
    render(<AuditEntriesTable entries={[]} />);

    expect(screen.getByText("No audit entries")).toBeInTheDocument();
  });
});
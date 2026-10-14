import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { AuditEntriesTable } from "@/components/hr/audit-entries-table";
<<<<<<< HEAD
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
=======
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
    // A chain has no screen of its own, so it reads as a chain and offers no
    // edit link: the team that owns it is where those steps are changed.
    expect(screen.getByText("Approval chain")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /edit/i })
    ).not.toBeInTheDocument();
    expect(screen.getByText("Academic staff workflow")).toBeInTheDocument();
    expect(screen.getByText("Days: 20 → 25")).toBeInTheDocument();
  });

  it("renders a flat detail payload without throwing", () => {
    /* `detail` is a free-form JSON bag. `document_generated` and
       `stage_skipped` write a flat payload, not a {before, after} diff, and
       reading those as a diff threw on Object.keys(undefined), taking the whole
       audit page down. Regression test for that crash. */
    const flat: AuditEntry = {
      ...baseEntry,
      action: "document_generated",
      target_type: "application",
      target_id: "app-1",
      target_summary: "LUANAR-2026-0001",
      detail: {
        document_id: "11",
        file_name: "approved-leave.pdf",
        file_size: 2438,
      },
    };

    expect(() => render(<AuditEntriesTable entries={[flat]} />)).not.toThrow();
    expect(screen.getByText(/approved-leave\.pdf/)).toBeInTheDocument();
    expect(screen.queryByText(/document_id/)).not.toBeInTheDocument();
  });

  it("renders a stage_skipped payload and does not repeat its reason", () => {
    const skipped: AuditEntry = {
      ...baseEntry,
      action: "stage_skipped",
      target_type: "application",
      target_summary: "LUANAR-2026-0002",
      detail: {
        reason: "applicant_is_the_approver",
        applicant_stage_orders: [1],
        skipped_stages: [{ order: 1, role: "supervisor" }],
      },
      reason: "",
    };

    expect(() => render(<AuditEntriesTable entries={[skipped]} />)).not.toThrow();
    const cell = screen.getByText(/applicant is also the approver/);
    expect(cell.textContent?.match(/applicant is also the approver/g)).toHaveLength(1);
  });

  it("falls back to the reason when detail is an empty object", () => {
    render(
      <AuditEntriesTable
        entries={[{ ...baseEntry, detail: {}, reason: "Nothing changed." }]}
      />
    );

    expect(screen.getByText("Nothing changed.")).toBeInTheDocument();
  });

  it("survives a detail whose after is null", () => {
    const odd: AuditEntry = {
      ...baseEntry,
      detail: { before: { a: 1 }, after: null },
      reason: "Recorded without a diff.",
    };

    expect(() => render(<AuditEntriesTable entries={[odd]} />)).not.toThrow();
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
    expect(screen.getByText("Name: Academic leave")).toBeInTheDocument();
  });

it("links editable targets to their edit page", () => {
    render(
      <AuditEntriesTable
        entries={[
          { ...baseEntry, target_type: "leaverule", target_id: "7" },
          { ...baseEntry, id: 2, target_type: "employee", target_id: "42" },
          {
            ...baseEntry,
            id: 3,
            target_type: "financialyear",
            target_id: "abc",
          },
        ]}
      />
    );

    const links = screen.getAllByRole("link", { name: "Edit" });
    expect(links).toHaveLength(3);
    expect(links[0]).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/leave-rules/7/edit"
    );
    expect(links[1]).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/employees/42"
    );
    expect(links[2]).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/calendar/financial-years/abc/edit"
    );
  });

  it("shows no edit link for read-only targets", () => {
    render(
      <AuditEntriesTable
        entries={[
          {
            ...baseEntry,
            target_type: "application",
            target_id: "app-1",
          },
          {
            ...baseEntry,
            id: 2,
            target_type: "reassignment",
            target_id: "5",
          },
        ]}
      />
    );

    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
>>>>>>> feature/plans-teams
  });

  it("renders an empty state when there are no entries", () => {
    render(<AuditEntriesTable entries={[]} />);

    expect(screen.getByText("No audit entries")).toBeInTheDocument();
  });
<<<<<<< HEAD

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
=======
>>>>>>> feature/plans-teams
});
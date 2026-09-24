import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ApplicationHistoryView } from "@/components/hr/application-history-view";
import type { ApplicationDetail } from "@/lib/audit";

const application: ApplicationDetail = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual",
  start_date: "2026-10-01",
  end_date: "2026-10-05",
  calculated_days: 5,
  reason: "Family visit",
  submitted_at: "2026-09-18T12:00:00Z",
  current_approver: 5,
  current_approver_name: "Bob HOD",
  documents: [
    {
      id: "doc-1",
      file_path: "supporting/doc.txt",
      file_url: "https://storage.example/doc.txt",
      file_name: "supporting-letter.txt",
      file_size: 2048,
      content_type: "text/plain",
      uploaded_at: "2026-09-18T12:00:00Z",
    },
  ],
  reassignments: [
    {
      id: 1,
      application: "app-1",
      reference_number: "LUANAR-2026-0001",
      employee: 8,
      employee_name: "Sam Staff",
      from_approver: 5,
      from_approver_name: "Bob HOD",
      to_approver: 10,
      to_approver_name: "Dana Dean",
      reason: "Bob unavailable during the window.",
      decided_by: 1,
      decided_by_name: "Aisha HR",
      created_at: "2026-09-19T08:00:00Z",
    },
  ],
  audit_entries: [
    {
      id: 1,
      actor: 3,
      actor_name: "Jane Approver",
      action: "leave_application.submitted",
      target_type: "leaveapplication",
      target_id: "app-1",
      target_summary: "LUANAR-2026-0001",
      detail: { before: null, after: {} },
      reason: "",
      prev_state: "draft",
      new_state: "submitted",
      created_at: "2026-09-18T12:00:00Z",
    },
  ],
};

describe("ApplicationHistoryView", () => {
  it("renders the summary, document, reassignment, and audit trail", () => {
    render(<ApplicationHistoryView application={application} />);

    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Annual")).toBeInTheDocument();
    expect(screen.getByText("supporting-letter.txt")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "https://storage.example/doc.txt"
    );
    expect(screen.getByText("Dana Dean")).toBeInTheDocument();
    expect(
      screen.getByText("Bob unavailable during the window.")
    ).toBeInTheDocument();
    expect(screen.getAllByText("Submitted").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Jane Approver")).toBeInTheDocument();
  });

  it("shows empty states when there are no documents or events", () => {
    render(
      <ApplicationHistoryView
        application={{
          ...application,
          documents: [],
          reassignments: [],
          audit_entries: [],
        }}
      />
    );

    expect(
      screen.getByText("No supporting documents were uploaded for this application.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("This application has not been reassigned.")
    ).toBeInTheDocument();
    expect(screen.getByText("No recorded events for this application.")).toBeInTheDocument();
  });
});
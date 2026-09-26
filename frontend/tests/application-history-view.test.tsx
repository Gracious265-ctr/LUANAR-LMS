import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ApplicationHistoryView } from "@/components/hr/application-history-view";
import type { ApplicationDetail } from "@/lib/audit";
import type { TimelineEntry } from "@/lib/leave-history";

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
  reassignments: [],
  audit_entries: [],
};

const entries: TimelineEntry[] = [
  {
    id: 1,
    kind: "submission",
    action: "leave_application.submitted",
    action_label: "Submitted for approval",
    occurred_at: "2026-09-18T12:00:00Z",
    actor: { id: 3, name: "Jane Approver" },
    target_type: "leaveapplication",
    state_transition: { from: "draft", to: "submitted" },
    summary: "",
    metadata: {},
    stage_order: null,
    resubmission_number: null,
  },
  {
    id: 2,
    kind: "reassignment",
    action: "application.reassigned",
    action_label: "Reassigned by Aisha HR",
    occurred_at: "2026-09-19T08:00:00Z",
    actor: { id: 1, name: "Aisha HR" },
    target_type: "leaveapplication",
    state_transition: { from: "", to: "" },
    summary: "Reassigned to Dana Dean",
    metadata: {},
    stage_order: null,
    resubmission_number: null,
  },
];

describe("ApplicationHistoryView", () => {
  it("renders the summary, documents, and the unified timeline", () => {
    render(<ApplicationHistoryView application={application} entries={entries} />);

    expect(screen.getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Annual")).toBeInTheDocument();
    expect(screen.getByText("supporting-letter.txt")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "https://storage.example/doc.txt"
    );
    expect(
      screen.getByText("Reassigned by Aisha HR")
    ).toBeInTheDocument();
    expect(screen.getByText("Reassigned to Dana Dean")).toBeInTheDocument();
    expect(screen.getByText("Submitted for approval")).toBeInTheDocument();
  });

  it("shows empty states when there are no documents or timeline events", () => {
    render(
      <ApplicationHistoryView
        application={{ ...application, documents: [] }}
        entries={[]}
      />
    );

    expect(
      screen.getByText("No supporting documents were uploaded for this application.")
    ).toBeInTheDocument();
    expect(screen.getByText("No recorded events for this application.")).toBeInTheDocument();
    expect(screen.queryByText("This application has not been reassigned.")).toBeNull();
  });
});
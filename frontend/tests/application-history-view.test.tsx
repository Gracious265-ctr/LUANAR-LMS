import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ApplicationHistoryView } from "@/components/hr/application-history-view";
import type { ApplicationDetail } from "@/lib/audit";
import type { Reassignment } from "@/lib/reassignments";

const reassignment: Reassignment = {
  id: 1,
  application: "app-10",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  from_approver: 3,
  from_approver_name: "Jane Dean",
  to_approver: 5,
  to_approver_name: "Bob HOD",
  reason: "Dean on leave; reassigned to HOD cover.",
  decided_by: 1,
  decided_by_name: "Aisha HR",
  created_at: "2026-09-19T09:00:00Z",
};

const application: ApplicationDetail = {
  id: "10",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual Leave",
  start_date: "2026-10-05",
  end_date: "2026-10-09",
  calculated_days: 5,
  reason: "Family visit.",
  submitted_at: "2026-09-18T12:00:00Z",
  current_approver: 5,
  current_approver_name: "Bob HOD",
  documents: [
    {
      id: "doc-1",
      file_url: "/media/docs/doc.pdf",
      file_name: "Travel itinerary.pdf",
      file_size: 1024,
      content_type: "application/pdf",
      uploaded_at: "2026-09-18T11:30:00Z",
    },
  ],
  reassignments: [reassignment],
  audit_entries: [
    {
      id: 1,
      actor: 8,
      actor_name: "Sam Staff",
      action: "submitted",
      target_type: "application",
      target_id: "10",
      target_summary: "LUANAR-2026-0001",
      detail: { before: { status: "draft" }, after: { status: "submitted" } },
      reason: "",
      created_at: "2026-09-18T12:00:00Z",
    },
    {
      id: 2,
      actor: 1,
      actor_name: "Aisha HR",
      action: "reassigned",
      target_type: "reassignment",
      target_id: "1",
      target_summary: "Jane Dean \u2192 Bob HOD",
      detail: null,
      reason: "Dean on leave; reassigned to HOD cover.",
      created_at: "2026-09-19T09:00:00Z",
    },
  ],
};

describe("ApplicationHistoryView", () => {
  it("renders the application summary", () => {
    render(<ApplicationHistoryView application={application} />);

    expect(screen.getByText("Application summary")).toBeInTheDocument();
    expect(screen.getByText("LUANAR-2026-0001")).toBeInTheDocument();
    expect(screen.getAllByText("Sam Staff").length).toBeGreaterThan(0);
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
    expect(screen.getAllByText("Bob HOD").length).toBeGreaterThan(0);
    expect(screen.getByText("Family visit.")).toBeInTheDocument();
  });

  it("lists uploaded documents with an open link", () => {
    render(<ApplicationHistoryView application={application} />);

    expect(screen.getByText("Travel itinerary.pdf")).toBeInTheDocument();
    const openLink = screen.getByRole("link", { name: "Open" });
    expect(openLink).toHaveAttribute("href", "/media/docs/doc.pdf");
  });

  it("renders the reassignment history", () => {
    render(<ApplicationHistoryView application={application} />);

    const reassignmentSection = screen
      .getByText("Reassignment history")
      .closest("div");
    expect(reassignmentSection).not.toBeNull();
    expect(
      within(reassignmentSection as HTMLElement).getByText("Bob HOD")
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Dean on leave; reassigned to HOD cover.").length
    ).toBeGreaterThan(0);
  });

  it("renders the audit trail in the given (oldest-first) order", () => {
    render(<ApplicationHistoryView application={application} />);

    const items = screen.getAllByRole("listitem");
    const submitted = items.find((item) =>
      within(item).queryByText("Submitted")
    );
    const reassigned = items.find((item) =>
      within(item).queryByText("Reassigned")
    );

    expect(submitted).toBeDefined();
    expect(reassigned).toBeDefined();
    expect(items.indexOf(submitted as HTMLElement)).toBeLessThan(
      items.indexOf(reassigned as HTMLElement)
    );
  });
});
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReassignmentsSection } from "@/components/hr/ReassignmentsSection";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import type { Employee } from "@/lib/employees";
import type { PendingApplication } from "@/lib/reassignments";
import { reassignApplication } from "@/lib/reassignments-client";

import { selectOption } from "./helpers/select";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/hr-admin/reassignments" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/reassignments-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/reassignments-client")>();
  return { ...actual, reassignApplication: vi.fn() };
});

const unassigned: PendingApplication = {
  id: "app-1",
  reference_number: "LUANAR-2026-0001",
  employee: 8,
  employee_name: "Sam Staff",
  leave_type_name: "Annual",
  start_date: "2026-10-01",
  end_date: "2026-10-05",
  calculated_days: 5,
  reason: "Family visit",
  submitted_at: "2026-09-18T10:00:00Z",
  current_approver: null,
  current_approver_name: "",
  acting_approver: null,
  acting_approver_name: "",
  is_delegated: false,
};

const delegated: PendingApplication = {
  ...unassigned,
  id: "app-2",
  reference_number: "LUANAR-2026-0002",
  current_approver: 3,
  current_approver_name: "Jane Dean",
  acting_approver: 5,
  acting_approver_name: "Bob HOD",
  is_delegated: true,
};

const employees: Employee[] = [
  makeEmployee({
    id: 3,
    user_id: 3,
    full_name: "Jane Dean",
    approver_roles: ["dean"],
  }),
  makeEmployee({
    id: 5,
    user_id: 5,
    full_name: "Bob HOD",
    approver_roles: ["hod"],
  }),
  makeEmployee({ id: 8, user_id: 8, full_name: "Sam Staff", approver_roles: [] }),
];

function renderSection(overrides: Partial<Parameters<typeof ReassignmentsSection>[0]> = {}) {
  return render(
    <ReassignmentsSection
      applications={[unassigned, delegated]}
      employees={employees}
      {...overrides}
    />
  );
}

describe("ReassignmentsSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathnameRef.current = "/hr-admin/reassignments";
    searchParamsRef.current = new URLSearchParams();
    vi.mocked(reassignApplication).mockResolvedValue({
      id: 1,
      application: "app-1",
      reference_number: "LUANAR-2026-0001",
      employee: 8,
      employee_name: "Sam Staff",
      from_approver: null,
      from_approver_name: "",
      to_approver: 3,
      to_approver_name: "Jane Dean",
      reason: "Urgent case",
      decided_by: 1,
      decided_by_name: "Aisha HR",
      created_at: "2026-09-18T12:00:00Z",
    });
  });

  it("renders the queue with no overlay open", () => {
    renderSection();

    expect(screen.getByText("LUANAR-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("LUANAR-2026-0002")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("turns the row action into a button that targets the row id", () => {
    renderSection();

    fireEvent.click(
      screen.getByRole("button", { name: "Reassign LUANAR-2026-0001" })
    );

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/reassignments?reassign=app-1"
    );
  });

  it("seeds the form from the row already on screen, with no fetch", () => {
    searchParamsRef.current = new URLSearchParams("reassign=app-1");
    renderSection();

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText("LUANAR-2026-0001 — Sam Staff (Annual)")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reassign application" })
    ).toBeInTheDocument();
  });

  it("reports an id that matches no pending row instead of a blank form", () => {
    searchParamsRef.current = new URLSearchParams("reassign=app-gone");
    renderSection();

    expect(screen.getByText(/no longer in the pending queue/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Replacement approver")).toBeNull();
    expect(screen.queryByLabelText("Reassignment reason")).toBeNull();
  });

  it("reassigns, closes, and refetches without navigating away", async () => {
    searchParamsRef.current = new URLSearchParams("reassign=app-1");
    renderSection();

    await selectOption(
      screen.getByLabelText("Replacement approver"),
      "Jane Dean"
    );
    fireEvent.change(screen.getByLabelText("Reassignment reason"), {
      target: { value: "Urgent case" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Reassign application" })
    );

    await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    expect(reassignApplication).toHaveBeenCalledWith({
      application: "app-1",
      to_approver: 3,
      reason: "Urgent case",
    });
    // The lone JSDOM history entry takes close's replace fallback; either way
    // the point is that it did not `push` the user off the queue.
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/hr-admin/reassignments"
    );
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  it("closes on cancel without writing anything", () => {
    searchParamsRef.current = new URLSearchParams("reassign=app-1");
    renderSection();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // Cancel is a button here, not a link: the overlay owns dismissal.
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/hr-admin/reassignments"
    );
    expect(reassignApplication).not.toHaveBeenCalled();
  });

  it("replaces the form with a banner when the people fetch failed", () => {
    searchParamsRef.current = new URLSearchParams("reassign=app-1");
    renderSection({
      employees: [],
      employeesError: "Unable to load people for the approver list.",
    });

    expect(
      screen.getByText("Unable to load people for the approver list.")
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Replacement approver")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Reassign application" })
    ).toBeNull();
  });

  it("shows the queue's own failure instead of an empty table", () => {
    renderSection({
      applications: [],
      error: "Unable to load pending applications. Please try again.",
    });

    expect(
      screen.getByText("Unable to load pending applications. Please try again.")
    ).toBeInTheDocument();
    expect(screen.queryByText("No pending applications")).toBeNull();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Entitlement } from "@/lib/entitlements";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import type { LeaveRule, LeaveType } from "@/lib/leave-rules";
import {
  createApproverRole,
  updateApproverRole,
} from "@/lib/approver-roles-client";
import {
  createLeaveRule,
  updateLeaveRule,
} from "@/lib/leave-rules-client";

import { pickDate } from "./helpers/date";

import { EntitlementsSection } from "@/components/hr/EntitlementsSection";
import { LeaveRulesSection } from "@/components/hr/LeaveRulesSection";
import { RolesSection } from "@/components/hr/RolesSection";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/organisation/roles" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/leave-rules-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-rules-client")>();
  return { ...actual, createLeaveRule: vi.fn(), updateLeaveRule: vi.fn() };
});

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return { ...actual, createApproverRole: vi.fn(), updateApproverRole: vi.fn() };
});

const entitlements: Entitlement[] = [
  {
    id: 3,
    grade_start: "G",
    grade_end: "H",
    days: 21,
    effective_from: "2026-01-01",
    leave_type: null,
  },
  {
    id: 4,
    grade_start: "E",
    grade_end: "F",
    days: 30,
    effective_from: "2026-01-01",
    leave_type: null,
  },
];

const leaveTypes: LeaveType[] = [
  { id: 1, name: "Annual leave", code: "annual" },
  { id: 2, name: "Maternity leave", code: "maternity" },
];

const rules: LeaveRule[] = [
  {
    id: 7,
    leave_type: 1,
    leave_type_code: "annual",
    leave_type_name: "Annual leave",
    max_duration_days: 30,
    min_notice_days: 14,
    eligibility: "",
    requires_supporting_document: false,
    consumes_annual_entitlement: true,
    effective_from: "2026-01-01",
  },
];

const roles: ApproverRole[] = [
  {
    id: 11,
    code: "hod",
    label: "Head of department",
    description: "",
    is_active: true,
    history_scope: "none",
    handles_cancellation: false,
    is_institution_wide: true,
    is_in_use: false,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 12,
    code: "dean",
    label: "Dean of faculty",
    description: "",
    is_active: true,
    history_scope: "none",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: false,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const noAssignments: Record<number, RoleAssignment[]> = {};

/** EntitlementForm posts with fetch rather than a typed client. */
function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify(entitlements[0]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
  );
}

describe("HR admin registry overlays — wave 1", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    vi.stubGlobal("history", { ...window.history, length: 2 });
    vi.mocked(createLeaveRule).mockResolvedValue(rules[0]);
    vi.mocked(updateLeaveRule).mockResolvedValue(rules[0]);
    vi.mocked(createApproverRole).mockResolvedValue(roles[0]);
    vi.mocked(updateApproverRole).mockResolvedValue(roles[0]);
  });

  describe("EntitlementsSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/hr-admin/entitlements";
    });

    it("renders the table with no overlay open", () => {
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      expect(screen.getByText("G–H")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("keeps the row name a real link to the old edit route", () => {
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      expect(screen.getByRole("link", { name: "G–H" })).toHaveAttribute(
        "href",
        "/hr-admin/entitlements/3/edit"
      );
    });

    it("opens create from the button and the new route", () => {
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      fireEvent.click(screen.getByRole("button", { name: "New entitlement" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/hr-admin/entitlements?entitlement=new"
      );
    });

    it("seeds the form from the row already on screen, with no fetch", () => {
      const fetchSpy = vi.fn();
      vi.stubGlobal("fetch", fetchSpy);
      searchParamsRef.current = new URLSearchParams("entitlement=4");
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      expect(screen.getByLabelText("Annual days")).toHaveValue(30);
      expect(screen.getByLabelText("Grade start")).toHaveValue("E");
      // The entitlement still comes from the row already on screen. The
      // leave-type picker is the one thing the table cannot carry, so that one
      // lookup is expected; a fetch for the entitlement itself is not.
      const urls = fetchSpy.mock.calls.map(([input]) => String(input));
      expect(urls.filter((url) => url.includes("/entitlements"))).toEqual([]);
    });

    it("explains a deep link to a rule that no longer exists", () => {
      searchParamsRef.current = new URLSearchParams("entitlement=999");
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      expect(
        screen.getByText(/no longer in the list/i)
      ).toBeInTheDocument();
      expect(screen.queryByLabelText("Annual days")).toBeNull();
    });

    it("uses the entitlement param, not another section's", () => {
      searchParamsRef.current = new URLSearchParams("rule=7&entitlement=3");
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      expect(screen.getByLabelText("Annual days")).toHaveValue(21);
    });

    it("refetches and closes after a save without navigating away", async () => {
      stubFetch();
      searchParamsRef.current = new URLSearchParams("entitlement=3");
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(routerMock.back).toHaveBeenCalledTimes(1);
      expect(routerMock.push).not.toHaveBeenCalled();
    });
  });

  describe("LeaveRulesSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/hr-admin/leave-rules";
    });

    it("renders the table and a custom heading", () => {
      render(
        <LeaveRulesSection
          rules={rules}
          leaveTypes={leaveTypes}
          today="2026-06-01"
          heading="Current rules"
        />
      );

      expect(screen.getByText("Current rules")).toBeInTheDocument();
      expect(screen.getByText("Annual leave")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("keeps the row name a real link to the old edit route", () => {
      render(
        <LeaveRulesSection rules={rules} leaveTypes={leaveTypes} today="2026-06-01" />
      );

      expect(screen.getByRole("link", { name: "Annual leave" })).toHaveAttribute(
        "href",
        "/hr-admin/leave-rules/7/edit"
      );
    });

    it("opens the edit overlay from the row pencil", () => {
      render(
        <LeaveRulesSection rules={rules} leaveTypes={leaveTypes} today="2026-06-01" />
      );

      fireEvent.click(screen.getByRole("button", { name: "Edit Annual leave rule" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/hr-admin/leave-rules?rule=7"
      );
    });

    it("seeds the edit form from the row", () => {
      searchParamsRef.current = new URLSearchParams("rule=7");
      render(
        <LeaveRulesSection rules={rules} leaveTypes={leaveTypes} today="2026-06-01" />
      );

      expect(screen.getByLabelText("Maximum duration (days)")).toHaveValue(30);
      expect(screen.getByLabelText("Minimum notice (days)")).toHaveValue(14);
    });

    it("explains a rule hidden by the page's filters, and offers to show all", () => {
      searchParamsRef.current = new URLSearchParams(
        "effective=current&leave_type=2&rule=7"
      );
      render(
        <LeaveRulesSection
          rules={[]}
          leaveTypes={leaveTypes}
          today="2026-06-01"
          clearFiltersHref="/hr-admin/leave-rules"
        />
      );

      expect(screen.getByText(/not in the current view/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Show all rules" }));

      expect(routerMock.push).toHaveBeenCalledWith("/hr-admin/leave-rules");
    });

    it("omits the escape hatch when there is nowhere to clear to", () => {
      searchParamsRef.current = new URLSearchParams("rule=7");
      render(
        <LeaveRulesSection
          rules={[]}
          leaveTypes={leaveTypes}
          today="2026-06-01"
        />
      );

      expect(
        screen.queryByRole("button", { name: "Show all rules" })
      ).toBeNull();
    });

    it("keeps the other filters when the overlay opens", () => {
      searchParamsRef.current = new URLSearchParams(
        "effective=current&leave_type=2&rule=7"
      );
      render(
        <LeaveRulesSection rules={rules} leaveTypes={leaveTypes} today="2026-06-01" />
      );

      expect(screen.getByLabelText("Maximum duration (days)")).toHaveValue(30);
    });

    it("reports a create back to the host and refetches", async () => {
      searchParamsRef.current = new URLSearchParams("rule=new");
      render(
        <LeaveRulesSection rules={rules} leaveTypes={leaveTypes} today="2026-06-01" />
      );

      // A create needs its required fields. The leave type is a native `select`
      // so that a type created from this same form appears in it; the browser
      // can enforce `required` on it, and the date picker is still not.
      fireEvent.change(screen.getByLabelText("Leave type"), {
        target: { value: "1" },
      });
      fireEvent.change(screen.getByLabelText("Maximum duration (days)"), {
        target: { value: "21" },
      });
      pickDate(screen.getByLabelText("Effective from"), "2026-07-01");

      fireEvent.click(screen.getByRole("button", { name: "Create rule" }));

      await waitFor(() =>
        expect(createLeaveRule).toHaveBeenCalledWith(
          expect.objectContaining({ max_duration_days: 21 })
        )
      );
      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(routerMock.push).not.toHaveBeenCalled();
    });
  });

  describe("RolesSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/organisation/roles";
    });

    it("renders the table with the holders it was given", () => {
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      expect(screen.getByText("Head of department")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("opens the edit overlay from the row pencil", () => {
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      fireEvent.click(screen.getByRole("button", { name: "Edit Dean of faculty" }));

      expect(routerMock.push).toHaveBeenCalledWith("/organisation/roles?role=12");
    });

    it("seeds the edit form from the row", () => {
      searchParamsRef.current = new URLSearchParams("role=11");
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      expect(screen.getByLabelText("Name")).toHaveValue("Head of department");
    });

    it("explains a deep link to a role that no longer exists", () => {
      searchParamsRef.current = new URLSearchParams("role=999");
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      expect(screen.getByText(/no longer in the list/i)).toBeInTheDocument();
    });

    it("reports a create back to the host and refetches", async () => {
      searchParamsRef.current = new URLSearchParams("role=new");
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      // Only the name is asked for, and it is `required`: jsdom enforces
      // constraint validation on a click-driven submit, so a blank name
      // silently blocks the handler rather than reaching the client. The code
      // is derived from it, so there is nothing to type.
      fireEvent.change(screen.getByLabelText("Name"), {
        target: { value: "Registrar" },
      });

      fireEvent.click(screen.getByRole("button", { name: "Create role" }));

      await waitFor(() =>
        expect(createApproverRole).toHaveBeenCalledWith(
          expect.objectContaining({ label: "Registrar" })
        )
      );
      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(routerMock.push).not.toHaveBeenCalled();
    });

    it("reports an edit back to the host", async () => {
      searchParamsRef.current = new URLSearchParams("role=11");
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

      await waitFor(() => expect(updateApproverRole).toHaveBeenCalled());
      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    });
  });
});

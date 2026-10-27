import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Entitlement } from "@/lib/entitlements";
import type { ApproverRole, RoleAssignment } from "@/lib/approver-roles";
import {
  createApproverRole,
  updateApproverRole,
} from "@/lib/approver-roles-client";

import { EntitlementsSection } from "@/components/hr/EntitlementsSection";
import { RolesSection } from "@/components/hr/RolesSection";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/dashboard/hr-admin/roles" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

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

/**
 * EntitlementForm posts with fetch rather than a typed client, and reads the
 * leave-type registry through one — so the registry endpoint has to answer
 * with a bare array here, exactly as the API does, or the picker tries to
 * `.filter` an entitlement.
 */
function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const isLeaveConfig = String(input).includes("leave-config");
      return new Response(
        JSON.stringify(isLeaveConfig ? [] : entitlements[0]),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    })
  );
}

describe("HR admin registry overlays — wave 1", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    vi.stubGlobal("history", { ...window.history, length: 2 });
    vi.mocked(createApproverRole).mockResolvedValue(roles[0]);
    vi.mocked(updateApproverRole).mockResolvedValue(roles[0]);
  });

  describe("EntitlementsSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/dashboard/hr-admin/entitlements";
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
        "/dashboard/hr-admin/entitlements/3/edit"
      );
    });

    it("opens create from the button and the new route", () => {
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      fireEvent.click(screen.getByRole("button", { name: "New entitlement" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/entitlements?entitlement=new"
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
      searchParamsRef.current = new URLSearchParams("role=11&entitlement=3");
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

    it("narrows the rules to the search text", () => {
      render(<EntitlementsSection entitlements={entitlements} today="2026-06-01" />);

      fireEvent.change(
        screen.getByRole("searchbox", { name: "Search entitlement rules" }),
        { target: { value: "30" } }
      );

      expect(screen.getByText("E–F")).toBeInTheDocument();
      expect(screen.queryByText("G–H")).toBeNull();
    });
  });

  describe("RolesSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/dashboard/hr-admin/roles";
    });

    it("renders the table with the holders it was given", () => {
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      expect(screen.getByText("Head of department")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("opens the edit overlay from the row pencil", () => {
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      fireEvent.click(screen.getByRole("button", { name: "Edit Dean of faculty" }));

      expect(routerMock.push).toHaveBeenCalledWith("/dashboard/hr-admin/roles?role=12");
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

    it("narrows the registry to the search text", () => {
      render(<RolesSection roles={roles} assignments={noAssignments} />);

      fireEvent.change(
        screen.getByRole("searchbox", { name: "Search approver roles" }),
        { target: { value: "dean" } }
      );

      expect(screen.getByText("Dean of faculty")).toBeInTheDocument();
      expect(screen.queryByText("Head of department")).toBeNull();
    });

    it("narrows the registry to retired roles", () => {
      const withRetired = [
        ...roles,
        {
          ...roles[0],
          id: 99,
          code: "legacy",
          label: "Legacy role",
          is_active: false,
        },
      ];
      render(<RolesSection roles={withRetired} assignments={noAssignments} />);

      fireEvent.click(screen.getByRole("button", { name: "Retired only" }));

      expect(screen.getByText("Legacy role")).toBeInTheDocument();
      expect(screen.queryByText("Head of department")).toBeNull();
      expect(screen.queryByText("Dean of faculty")).toBeNull();
    });
  });
});

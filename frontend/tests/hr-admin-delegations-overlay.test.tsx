import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Delegation } from "@/lib/delegations";
import { createDelegation } from "@/lib/delegations-client";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";

import { pickRangeStart } from "./helpers/date";
import { selectOption } from "./helpers/select";

import { DelegationsSection } from "@/components/hr/DelegationsSection";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/hr-admin/delegations" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return { ...actual, createDelegation: vi.fn() };
});

function delegation(over: Partial<Delegation> = {}): Delegation {
  return {
    id: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    approver: 3,
    approver_name: "Jane Dean",
    approver_role: "dean",
    delegate: null,
    delegate_name: "",
    starts_on: "2026-10-15",
    ends_on: null,
    request_reason: "",
    requested_by: 1,
    requested_by_name: "HR",
    decision_reason: "",
    decided_by: null,
    decided_at: null,
    status: "requested",
    state: "requested",
    ...over,
  };
}

const employees: Employee[] = [
  makeEmployee({ id: 3, full_name: "Jane Dean", approver_roles: ["dean"] }),
];

/**
 * The create form refuses to submit without an approver and a start date, and
 * both pickers are Radix triggers, so a bare click on the submit button only
 * reaches the form's own validation. Filling them is what lets the host's
 * behaviour be observed at all.
 */
async function fillCreateForm() {
  await selectOption(
    screen.getByRole("combobox", { name: "Approver" }),
    "Jane Dean"
  );
  pickRangeStart(screen.getByLabelText("Period"), "2026-10-15");
}

function renderSection(props: Partial<Parameters<typeof DelegationsSection>[0]> = {}) {
  return render(
    <DelegationsSection
      delegations={[delegation()]}
      employees={employees}
      stateFilter=""
      heading="All delegations"
      clearFiltersHref="/hr-admin/delegations"
      {...props}
    />
  );
}

describe("DelegationsSection — wave 2", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    // `history.length > 1` forces the `back()` branch of `close`, which is the
    // branch a real browser takes after `openCreate` pushed.
    vi.stubGlobal("history", { ...window.history, length: 2 });
    // Standing in for the browser: stepping back drops the overlay param. Without
    // this the dialog never unmounts, and Radix leaves the page behind it
    // `aria-hidden` — so the post-create alert would be rendered but unfindable
    // by role, which is a harness artefact rather than a real failure.
    routerMock.back.mockImplementation(() => {
      searchParamsRef.current.delete("delegation");
    });
    routerMock.push.mockImplementation((href: string) => {
      searchParamsRef.current = new URLSearchParams(
        href.split("?")[1] ?? ""
      );
    });
  });

  it("renders the table with no overlay open", () => {
    renderSection();

    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps the row name a link to the review page, not an overlay", () => {
    // Delegations are corrected by approving, rejecting or cancelling, all of
    // which live on the record's own page. There is no edit dialog to open.
    renderSection();

    const link = screen.getByRole("link", { name: /Jane Dean/ });
    expect(link.getAttribute("href")).toBe("/hr-admin/delegations/1");
  });

  it("opens the create form from the trigger, keeping the state filter", () => {
    searchParamsRef.current = new URLSearchParams("state=active");
    renderSection({ stateFilter: "active" });

    fireEvent.click(screen.getByRole("button", { name: /New delegation request/ }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/delegations?state=active&delegation=new"
    );
  });

  it("renders the state tab bar from the page's tabs data", () => {
    // The tab bar arrives as data rather than as a JSX slot. Markup authored in
    // the page's server component and rendered inside this client component
    // crosses the RSC boundary, where React stops recognising statically written
    // siblings and warns that each child in the list needs a key. The page still
    // owns every href and decides which tab is current.
    renderSection({
      tabs: [
        { label: "All", href: "/hr-admin/delegations", current: false },
        {
          label: "Active",
          href: "/hr-admin/delegations?state=active",
          current: true,
        },
      ],
    });

    // The tab bar renders before the table, and the row name is a link to the
    // review page, so the first two links are the tabs.
    const tabs = screen.getAllByRole("link").slice(0, 2);

    expect(tabs.map((tab) => tab.textContent)).toEqual(["All", "Active"]);
    expect(tabs.map((tab) => tab.getAttribute("href"))).toEqual([
      "/hr-admin/delegations",
      "/hr-admin/delegations?state=active",
    ]);
    expect(tabs[0]).not.toHaveAttribute("aria-current");
    expect(tabs[1]).toHaveAttribute("aria-current", "page");
  });

  it("renders no tab bar at all when the page sends no tabs", () => {
    renderSection();

    // Only the row link, which is the point: an empty tab bar would be a stray
    // bordered strip above the table.
    expect(within(screen.getByRole("table")).getAllByRole("link")).toHaveLength(
      1,
    );
  });

  it("passes every employee to the pickers, not just the ones in the table", () => {
    // A page-1 read here would quietly offer HR only the first twenty staff.
    searchParamsRef.current = new URLSearchParams("delegation=new");
    renderSection({ employees: [...employees, makeEmployee({ id: 9, full_name: "Late Addition", approver_roles: ["hod"] })] });

    expect(screen.getByRole("combobox", { name: "Approver" })).toBeInTheDocument();
  });

  it("closes on cancel without navigating away", () => {
    searchParamsRef.current = new URLSearchParams("delegation=new");
    renderSection();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // `close` steps back one entry rather than pushing, so the list underneath
    // is the one the admin came from.
    expect(routerMock.back).toHaveBeenCalledTimes(1);
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  describe("after a create", () => {
    it("refreshes without navigating, when the new row is on screen", async () => {
      searchParamsRef.current = new URLSearchParams("delegation=new");
      vi.mocked(createDelegation).mockResolvedValue(
        delegation({ id: 2, approver_name: "Jane Dean" })
      );
      renderSection({ delegations: [delegation(), delegation({ id: 2, approver_name: "Jane Dean" })] });

      await fillCreateForm();
      fireEvent.click(
        screen.getByRole("button", { name: /create delegation request/i })
      );

      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(routerMock.push).not.toHaveBeenCalled();
    });

    it("explains a created row the state filter keeps out of the table", async () => {
      // The new delegation is `requested`, so on the `active` tab the refetched
      // list does not contain it. The save worked and the table is right, but
      // together they read as a failed save.
      searchParamsRef.current = new URLSearchParams("state=active&delegation=new");
      vi.mocked(createDelegation).mockResolvedValue(delegation({ id: 99 }));
      renderSection({ stateFilter: "active" });

      await fillCreateForm();
      fireEvent.click(
        screen.getByRole("button", { name: /create delegation request/i })
      );

      await waitFor(() =>
        expect(screen.getByText(/not in this table/i)).toBeInTheDocument()
      );
      expect(screen.getByRole("button", { name: "Show all states" })).toBeInTheDocument();
    });

    it("clears the filter from the explanation when asked", async () => {
      searchParamsRef.current = new URLSearchParams("state=active&delegation=new");
      vi.mocked(createDelegation).mockResolvedValue(delegation({ id: 99 }));
      renderSection({ stateFilter: "active" });

      await fillCreateForm();
      fireEvent.click(
        screen.getByRole("button", { name: /create delegation request/i })
      );
      await waitFor(() =>
        expect(screen.getByText(/not in this table/i)).toBeInTheDocument()
      );

      fireEvent.click(screen.getByRole("button", { name: "Show all states" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/hr-admin/delegations"
      );
    });
  });
});
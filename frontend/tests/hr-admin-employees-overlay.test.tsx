import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";

import { EmployeesSection } from "@/components/hr/EmployeesSection";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/hr-admin/employees" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

const saved: Employee = makeEmployee({ id: 21, full_name: "Ada Newly" });

function renderSection(
  props: Partial<Parameters<typeof EmployeesSection>[0]> = {}
) {
  return render(
    <EmployeesSection
      employees={[makeEmployee({ id: 1, full_name: "Jane Dean" })]}
      totalCount={57}
      gradeOptions={["A", "B", "G"]}
      search=""
      {...props}
    />
  );
}

/**
 * `EmployeeForm` posts with plain `fetch`, so this drives the whole save. The
 * role is read-only and the team comes from the roster, so the three identity
 * fields are the whole of it.
 */
function submitCreateForm() {
  fireEvent.change(screen.getByLabelText("First name"), {
    target: { value: "Ada" },
  });
  fireEvent.change(screen.getByLabelText("Last name"), {
    target: { value: "Newly" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "ada.newly@test.luanar" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create employee" }));
}

/** A `POST` the form accepts, answering with the employee the API created. */
function stubCreateResponse() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(saved), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    )
  );
}

describe("EmployeesSection — wave 2", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    vi.stubGlobal("history", { ...window.history, length: 2 });
    // Stands in for the browser: stepping back drops the overlay param. Without
    // it the dialog never unmounts and Radix leaves the page `aria-hidden`, so
    // the post-save alert would render but be unfindable by role.
    routerMock.back.mockImplementation(() => {
      searchParamsRef.current.delete("employee");
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the table with no overlay open", () => {
    renderSection();

    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps the row name a link to the profile page, not an overlay", () => {
    // The profile page is a record of one person with their team, grade history
    // and document trail, not a short form.
    renderSection();

    expect(
      screen.getByRole("link", { name: /Jane Dean/ }).getAttribute("href")
    ).toBe("/hr-admin/employees/1");
  });

  it("says which slice of the staff list is on screen when unfiltered", () => {
    // The table has no pager, so "21 employees" on its own would read as the
    // whole staff.
    renderSection();

    expect(screen.getByText("Showing 1 of 57.")).toBeInTheDocument();
  });

  it("keeps the search filter when opening the create form", () => {
    searchParamsRef.current = new URLSearchParams("search=dean");
    renderSection({ search: "dean" });

    fireEvent.click(screen.getByRole("button", { name: /New employee/ }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/employees?search=dean&employee=new"
    );
  });

  it("hands cancel back to the overlay rather than leaving the page", () => {
    searchParamsRef.current = new URLSearchParams("employee=new");
    renderSection();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(routerMock.back).toHaveBeenCalledTimes(1);
  });

  it("refreshes without navigating when the new employee is on this page", async () => {
    searchParamsRef.current = new URLSearchParams("employee=new");
    stubCreateResponse();
    renderSection({
      employees: [makeEmployee({ id: 1, full_name: "Jane Dean" }), saved],
      totalCount: 58,
    });

    submitCreateForm();

    await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    expect(routerMock.push).not.toHaveBeenCalled();
    expect(screen.queryByText(/not on this page/i)).toBeNull();
  });

  describe("when the save lands off this page", () => {
    it("blames pagination, not the search, when none is active", async () => {
      // A 21st employee is on page two of a table with no pager. Blaming the
      // search here would offer a fix that changes nothing.
      searchParamsRef.current = new URLSearchParams("employee=new");
      stubCreateResponse();
      renderSection({ employees: [makeEmployee({ id: 1 })], totalCount: 57 });

      submitCreateForm();

      await waitFor(() =>
        expect(screen.getByText(/not on this page/i)).toBeInTheDocument()
      );
      expect(screen.getByText(/first 1 of 57 employees/i)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
    });

    it("blames the search and offers to clear it when one is active", async () => {
      searchParamsRef.current = new URLSearchParams("search=dean&employee=new");
      stubCreateResponse();
      renderSection({
        employees: [makeEmployee({ id: 1 })],
        totalCount: 1,
        search: "dean",
      });

      submitCreateForm();

      await waitFor(() =>
        expect(screen.getByText(/not on this page/i)).toBeInTheDocument()
      );
      expect(screen.getByText(/filtered to "dean"/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Clear search" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/hr-admin/employees"
      );
    });
  });

  it("replaces the table on a list error but keeps the create trigger", () => {
    // The dialog needs its option data, not the table, so a failed list read
    // must not also remove the one action that still works.
    renderSection({ error: "Unable to load employees. Please try again." });

    expect(
      screen.getByText("Unable to load employees. Please try again.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New employee/ })).toBeInTheDocument();
    expect(screen.queryByText("Jane Dean")).toBeNull();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FinancialYear, PublicHoliday } from "@/lib/financial-years";
import {
  createFinancialYear,
  createPublicHoliday,
  updateFinancialYear,
} from "@/lib/financial-years-client";
import type { Department } from "@/lib/departments";
import {
  createDepartment,
  retireDepartment,
  updateDepartment,
} from "@/lib/departments-client";
import type { LeaveType } from "@/lib/leave-rules";
import { createLeaveType, updateLeaveType } from "@/lib/leave-rules-client";

import { DepartmentsSection } from "@/components/hr/DepartmentsSection";
import { FinancialYearsSection } from "@/components/hr/FinancialYearsSection";
import { HolidaysSection } from "@/components/hr/HolidaysSection";
import { LeaveTypesSection } from "@/components/hr/LeaveTypesSection";

import { pickDate, pickDateRange } from "./helpers/date";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/dashboard/hr-admin/calendar" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/leave-rules-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/leave-rules-client")>();
  return { ...actual, createLeaveType: vi.fn(), updateLeaveType: vi.fn() };
});

vi.mock("@/lib/departments-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/departments-client")>();
  return {
    ...actual,
    createDepartment: vi.fn(),
    updateDepartment: vi.fn(),
    retireDepartment: vi.fn(),
  };
});

vi.mock("@/lib/financial-years-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/financial-years-client")>();
  return {
    ...actual,
    createFinancialYear: vi.fn(),
    updateFinancialYear: vi.fn(),
    createPublicHoliday: vi.fn(),
  };
});

const leaveTypes: LeaveType[] = [
  { id: 1, name: "Annual leave", code: "annual" },
  { id: 2, name: "Maternity leave", code: "maternity" },
];

const holidays: PublicHoliday[] = [
  { id: 4, name: "Independence Day", date: "2026-03-04" },
];

const departments: Department[] = [
  {
    id: 3,
    name: "ICT",
    is_active: true,
    team_count: 2,
    employee_count: 5,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 4,
    name: "Physics",
    is_active: false,
    team_count: 0,
    employee_count: 0,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const years: FinancialYear[] = [
  { id: 8, start_date: "2026-07-01", end_date: "2027-06-30", is_active: true },
  { id: 9, start_date: "2027-07-01", end_date: "2028-06-30", is_active: false },
];

describe("HR admin form overlays", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathnameRef.current = "/dashboard/hr-admin/calendar";
    searchParamsRef.current = new URLSearchParams();
    vi.mocked(createLeaveType).mockResolvedValue(leaveTypes[0]);
    vi.mocked(updateLeaveType).mockResolvedValue(leaveTypes[1]);
    vi.mocked(createPublicHoliday).mockResolvedValue(holidays[0]);
    vi.mocked(createFinancialYear).mockResolvedValue(years[0]);
    vi.mocked(updateFinancialYear).mockResolvedValue(years[1]);
    vi.mocked(createDepartment).mockResolvedValue(departments[0]);
    vi.mocked(updateDepartment).mockResolvedValue(departments[0]);
    vi.mocked(retireDepartment).mockResolvedValue({
      ...departments[0],
      is_active: false,
    });
  });

  describe("LeaveTypesSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/dashboard/hr-admin/leave-types";
    });

    it("renders the table with no overlay open", () => {
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(screen.getByText("Annual leave")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("keeps the row name a real link to the old edit route", () => {
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(
        screen.getByRole("link", { name: "Maternity leave" }).getAttribute("href")
      ).toBe("/dashboard/hr-admin/leave-types/2/edit");
    });

    it("turns the pencil into a button that targets the row id", () => {
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      fireEvent.click(screen.getByRole("button", { name: "Edit Maternity leave" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/leave-types?leaveType=2"
      );
    });

    it("opens a create form from the trigger", () => {
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      fireEvent.click(screen.getByRole("button", { name: /New leave type/ }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/leave-types?leaveType=new"
      );
    });

    it("seeds edit mode from the row already on screen, with no fetch", () => {
      searchParamsRef.current = new URLSearchParams("leaveType=2");
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByLabelText("Name")).toHaveValue("Maternity leave");
      expect(screen.getByLabelText("Code")).toHaveValue("maternity");
    });

    it("shows a create form for the new target rather than an edit form", () => {
      searchParamsRef.current = new URLSearchParams("leaveType=new");
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(screen.getByLabelText("Name")).toHaveValue("");
      expect(
        screen.getByRole("button", { name: "Create leave type" })
      ).toBeInTheDocument();
    });

    it("reports an id that matches no row instead of rendering a blank edit form", () => {
      searchParamsRef.current = new URLSearchParams("leaveType=999");
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(screen.getByText(/no longer in the list/)).toBeInTheDocument();
      expect(screen.queryByLabelText("Name")).toBeNull();
    });

    it("switches target without leaking the previous row's values", () => {
      const { rerender } = render(<LeaveTypesSection leaveTypes={leaveTypes} />);
      searchParamsRef.current = new URLSearchParams("leaveType=2");
      rerender(<LeaveTypesSection leaveTypes={leaveTypes} />);
      expect(screen.getByLabelText("Name")).toHaveValue("Maternity leave");

      searchParamsRef.current = new URLSearchParams("leaveType=1");
      rerender(<LeaveTypesSection leaveTypes={leaveTypes} />);

      expect(screen.getByLabelText("Name")).toHaveValue("Annual leave");
    });

    it("refetches and closes after a create, without navigating away", async () => {
      searchParamsRef.current = new URLSearchParams("leaveType=new");
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      fireEvent.change(screen.getByLabelText("Name"), {
        target: { value: "Study leave" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Create leave type" })
      );

      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(createLeaveType).toHaveBeenCalledWith({ name: "Study leave" });
      // The lone JSDOM history entry takes close's replace fallback; either way
      // the point is that it did not `push` the user off the list.
      expect(routerMock.replace).toHaveBeenCalledWith(
        "/dashboard/hr-admin/leave-types"
      );
      expect(routerMock.push).not.toHaveBeenCalled();
    });

    it("updates the existing row rather than creating a second one", () => {
      searchParamsRef.current = new URLSearchParams("leaveType=2");
      render(<LeaveTypesSection leaveTypes={leaveTypes} />);

      fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

      expect(updateLeaveType).toHaveBeenCalledWith(2, {
        name: "Maternity leave",
        code: "maternity",
      });
      expect(createLeaveType).not.toHaveBeenCalled();
    });
  });

  describe("DepartmentsSection", () => {
    beforeEach(() => {
      pathnameRef.current = "/dashboard/hr-admin/departments";
    });

    it("renders the table with no overlay open", () => {
      render(<DepartmentsSection departments={departments} />);

      expect(screen.getByRole("button", { name: "New department" })).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).toBeNull();
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("keeps the row name a real link to the old edit route", () => {
      render(<DepartmentsSection departments={departments} />);

      expect(screen.getByRole("link", { name: "ICT" })).toHaveAttribute(
        "href",
        "/dashboard/hr-admin/departments/3/edit"
      );
    });

    it("turns the pencil into a button that targets the row id", () => {
      render(<DepartmentsSection departments={departments} />);

      // The point of the change: the pencil stops being a navigation and starts
      // being a dialog, so it must push the overlay param and not a route.
      fireEvent.click(screen.getByRole("button", { name: "Edit ICT" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/departments?department=3"
      );
    });

    it("opens a create form from the trigger", () => {
      render(<DepartmentsSection departments={departments} />);

      fireEvent.click(screen.getByRole("button", { name: "New department" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/departments?department=new"
      );
    });

    it("seeds edit mode from the row already on screen, with no fetch", () => {
      searchParamsRef.current = new URLSearchParams("department=3");
      render(<DepartmentsSection departments={departments} />);

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByLabelText("Name")).toHaveValue("ICT");
      // The counts come from the same row, so the dialog can say what the
      // department owns without a second request.
      expect(screen.getByText(/2 teams · 5 employees/)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Save changes" })
      ).toBeInTheDocument();
    });

    it("still edits a retired row, because the list carries retired rows too", () => {
      searchParamsRef.current = new URLSearchParams("department=4");
      render(<DepartmentsSection departments={departments} />);

      // Retiring keeps a department on the list, so a link to one must not be
      // mistaken for a missing row.
      expect(screen.queryByText(/no longer in the list/)).toBeNull();
      expect(screen.getByLabelText("Name")).toHaveValue("Physics");
    });

    it("shows a create form for the new target rather than an edit form", () => {
      searchParamsRef.current = new URLSearchParams("department=new");
      render(<DepartmentsSection departments={departments} />);

      expect(screen.getByLabelText("Name")).toHaveValue("");
      expect(
        screen.getByRole("button", { name: "Create department" })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Save changes" })
      ).toBeNull();
    });

    it("reports an id that matches no row instead of rendering a blank edit form", () => {
      searchParamsRef.current = new URLSearchParams("department=99");
      render(<DepartmentsSection departments={departments} />);

      expect(screen.getByText(/no longer in the list/)).toBeInTheDocument();
      expect(screen.queryByLabelText("Name")).toBeNull();
    });

    it("switches target without leaking the previous row's values", () => {
      searchParamsRef.current = new URLSearchParams("department=3");
      const { rerender } = render(
        <DepartmentsSection departments={departments} />
      );

      searchParamsRef.current = new URLSearchParams("department=4");
      rerender(<DepartmentsSection departments={departments} />);

      expect(screen.getByLabelText("Name")).toHaveValue("Physics");
    });

    it("refetches and closes after a create, without navigating away", async () => {
      searchParamsRef.current = new URLSearchParams("department=new");
      render(<DepartmentsSection departments={departments} />);

      fireEvent.change(screen.getByLabelText("Name"), {
        target: { value: "Mathematics" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Create department" })
      );

      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(createDepartment).toHaveBeenCalledWith({ name: "Mathematics" });
      // The lone JSDOM history entry takes close's replace fallback; either way
      // the point is that it did not `push` the user off the list.
      expect(routerMock.replace).toHaveBeenCalledWith(
        "/dashboard/hr-admin/departments"
      );
      expect(routerMock.push).not.toHaveBeenCalled();
    });

    it("updates the existing row rather than creating a second one", () => {
      searchParamsRef.current = new URLSearchParams("department=3");
      render(<DepartmentsSection departments={departments} />);

      fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

      expect(updateDepartment).toHaveBeenCalledWith(3, { name: "ICT" });
      expect(createDepartment).not.toHaveBeenCalled();
    });

    it("reports a retirement through the same close-and-refresh path", async () => {
      searchParamsRef.current = new URLSearchParams("department=3");
      render(<DepartmentsSection departments={departments} />);

      fireEvent.click(
        screen.getByRole("button", { name: "Retire department" })
      );

      await waitFor(() => expect(retireDepartment).toHaveBeenCalledWith(3));
      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(routerMock.push).not.toHaveBeenCalled();
    });

    it("closes on cancel without writing anything", () => {
      searchParamsRef.current = new URLSearchParams("department=3");
      render(<DepartmentsSection departments={departments} />);

      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

      // Cancel is a button here, not a link: the overlay owns dismissal.
      expect(routerMock.replace).toHaveBeenCalledWith(
        "/dashboard/hr-admin/departments"
      );
      expect(updateDepartment).not.toHaveBeenCalled();
      expect(retireDepartment).not.toHaveBeenCalled();
    });

    it("keeps the host's own query intact when the overlay opens", () => {
      searchParamsRef.current = new URLSearchParams("q=ICT");
      render(<DepartmentsSection departments={departments} />);

      fireEvent.click(screen.getByRole("button", { name: "Edit ICT" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/departments?q=ICT&department=3"
      );
    });
  });

  describe("HolidaysSection", () => {
    it("opens a create form without disturbing the year filter", () => {
      searchParamsRef.current = new URLSearchParams("year=2026");
      render(<HolidaysSection holidays={holidays} yearFilter="2026" />);

      fireEvent.click(screen.getByRole("button", { name: /New holiday/ }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/calendar?year=2026&holiday=new"
      );
    });

    it("explains a filtered-out deep link and offers to show all years", () => {
      searchParamsRef.current = new URLSearchParams("year=2026&holiday=99");
      render(<HolidaysSection holidays={holidays} yearFilter="2026" />);

      expect(screen.getByText(/not in the 2026 view/)).toBeInTheDocument();
      expect(screen.queryByLabelText("Name")).toBeNull();

      fireEvent.click(screen.getByRole("button", { name: "Show all years" }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/calendar?year=2026"
      );
    });

    it("reports a genuinely missing row without blaming the filter", () => {
      searchParamsRef.current = new URLSearchParams("holiday=99");
      render(<HolidaysSection holidays={holidays} yearFilter="" />);

      expect(screen.getByText(/no longer in the list/)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Show all years" })
      ).toBeNull();
    });

    it("still edits a row that the filter happens to include", () => {
      searchParamsRef.current = new URLSearchParams("year=2026&holiday=4");
      render(<HolidaysSection holidays={holidays} yearFilter="2026" />);

      expect(screen.getByRole("heading", { name: "Edit Independence Day" })).toBeInTheDocument();
      expect(screen.getByLabelText("Name")).toHaveValue("Independence Day");
    });

    it("explains a newly created holiday that the active filter hides", async () => {
      // The save succeeded, but `?year` is applied server-side, so the row the
      // admin just created is absent from the refreshed list. Saying nothing
      // makes a working save look like a failure.
      searchParamsRef.current = new URLSearchParams("year=2026&holiday=new");
      vi.mocked(createPublicHoliday).mockResolvedValue({
        id: 9,
        name: "Founders Day",
        date: "2027-01-15",
      });
      render(<HolidaysSection holidays={holidays} yearFilter="2026" />);

      fireEvent.change(screen.getByLabelText("Name"), {
        target: { value: "Founders Day" },
      });
      pickDate(screen.getByLabelText("Date"), "2027-01-15");
      fireEvent.click(screen.getByRole("button", { name: /save|add|create/i }));

      await waitFor(() => expect(createPublicHoliday).toHaveBeenCalled());
      // The list handed back after the refresh still lacks the new row, which
      // is exactly what a filtered create produces.
      await waitFor(() =>
        expect(screen.getByText(/not in this table/i)).toBeInTheDocument()
      );
      expect(screen.getByText(/filtered to 2026/)).toBeInTheDocument();
    });

    it("says nothing about the filter when the new row is in view", async () => {
      searchParamsRef.current = new URLSearchParams("year=2026&holiday=new");
      vi.mocked(createPublicHoliday).mockResolvedValue({
        id: 5,
        name: "Republic Day",
        date: "2026-11-14",
      });
      render(
        <HolidaysSection
          holidays={[...holidays, { id: 5, name: "Republic Day", date: "2026-11-14" }]}
          yearFilter="2026"
        />
      );

      fireEvent.change(screen.getByLabelText("Name"), {
        target: { value: "Republic Day" },
      });
      pickDate(screen.getByLabelText("Date"), "2026-11-14");
      fireEvent.click(screen.getByRole("button", { name: /save|add|create/i }));

      await waitFor(() => expect(createPublicHoliday).toHaveBeenCalled());
      expect(screen.queryByText(/not in this table/i)).toBeNull();
    });

    it("renders the filter in the slot the section provides", () => {
      render(
        <HolidaysSection
          holidays={holidays}
          yearFilter=""
          filter={<span>filter goes here</span>}
        />
      );

      // Before the table, so the control stays attached to what it narrows.
      const filter = screen.getByText("filter goes here");
      const name = screen.getByText("Independence Day");
      expect(filter.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING)
        .toBeTruthy();
    });
  });

  describe("FinancialYearsSection", () => {
    // The hazard is retiring a live period, so the warning belongs on the rows
    // where ticking the box does that: an inactive period, or a new one.
    it("warns that activating an inactive period retires the active one", () => {
      searchParamsRef.current = new URLSearchParams("financialYear=9");
      render(<FinancialYearsSection years={years} />);

      expect(
        screen.getByText(/activating this period deactivates the one that is active now/)
      ).toBeInTheDocument();
    });

    it("warns when a new period would be created active", () => {
      searchParamsRef.current = new URLSearchParams("financialYear=new");
      render(<FinancialYearsSection years={years} />);

      expect(
        screen.getByText(/creating this one active deactivates the period that is active now/)
      ).toBeInTheDocument();
    });

    it("omits the warning on the active period, which has nothing to deactivate", () => {
      // The reverse of the naive test: this row's checkbox is already ticked,
      // so the warning would be noise rather than a warning.
      searchParamsRef.current = new URLSearchParams("financialYear=8");
      render(<FinancialYearsSection years={years} />);

      // Scoped to the dialog description: the form's own help text under the
      // checkbox explains the same rule and is always present, so the assertion
      // has to be about the description alone.
      const description = screen
        .getByRole("dialog")
        .querySelector("[data-slot='dialog-description']");
      expect(description?.textContent).toBe(
        "Update the period. Periods must not overlap each other."
      );
    });

    it("keeps the year filter untouched when opening a financial-year overlay", () => {
      searchParamsRef.current = new URLSearchParams("year=2026");
      render(<FinancialYearsSection years={years} />);

      fireEvent.click(screen.getByRole("button", { name: /New financial year/ }));

      expect(routerMock.push).toHaveBeenCalledWith(
        "/dashboard/hr-admin/calendar?year=2026&financialYear=new"
      );
    });

    it("does not open on the other overlay's key", () => {
      searchParamsRef.current = new URLSearchParams("holiday=new");
      render(<FinancialYearsSection years={years} />);

      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("creates a period and refetches", async () => {
      searchParamsRef.current = new URLSearchParams("financialYear=new");
      render(<FinancialYearsSection years={years} />);

      // The form requires a closed period, so both ends have to be picked.
      pickDateRange(screen.getByLabelText("Period"), "2027-01-01", "2027-06-30");
      fireEvent.click(
        screen.getByRole("button", { name: "Create financial year" })
      );

      await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
      expect(createFinancialYear).toHaveBeenCalledWith(
        expect.objectContaining({ start_date: "2027-01-01", end_date: "2027-06-30" })
      );
    });
  });
});

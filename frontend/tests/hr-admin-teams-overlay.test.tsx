import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApproverRole } from "@/lib/approver-roles";
import type { Department } from "@/lib/departments";

import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { createTeam, listEligibleApprovers } from "@/lib/teams-client";

import { TeamsSection } from "@/components/hr/TeamsSection";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/dashboard/hr-admin/teams" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return {
    ...actual,
    createTeam: vi.fn(),
    updateTeam: vi.fn(),
    listEligibleApprovers: vi.fn(),
  };
});

// `code` rather than `key`: the chain seeds a new step with `roles[0].code`,
// so a role fixture without one leaves the select on no value and the submit
// never gets past the "every step needs a role" check.
const roles: ApproverRole[] = [
  {
    id: 1,
    code: "hod",
    label: "Head of Department",
    description: "",
    is_active: true,
    history_scope: "team",
    handles_cancellation: false,
    is_institution_wide: false,
    is_in_use: true,
    usage: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// Eligibility is per department and per role, so the picker reads the server
// rather than filtering a staff list the browser already holds.
const departments: Department[] = [
  {
    id: 1,
    name: "Physics",
    is_active: true,
    team_count: 0,
    employee_count: 1,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const campusList = [makeCampus()];

function renderSection(
  props: Partial<Parameters<typeof TeamsSection>[0]> = {},
) {
  return render(
    <TeamsSection
      teams={[makeTeam()]}
      campuses={campusList}
      roles={roles}
      departments={departments}
      departmentsError=""
      rolesError=""
      {...props}
    />,
  );
}

/**
 * A create crosses both pages: page one says what the team is, page two who
 * decides, and only the second one writes. The approver picker stays disabled
 * until the department and the step's role are both known, because eligibility
 * is the server's answer for that pair rather than a filter over a staff list.
 */
async function fillCreateForm() {
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Physics" },
  });
  fireEvent.change(screen.getByLabelText("Department"), {
    target: { value: "1" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Continue to approval steps" }),
  );

  fireEvent.click(screen.getByRole("button", { name: "Add step" }));
  // A step is named by its role, so picking the role is the whole instruction.
  fireEvent.change(screen.getByLabelText("Step 1 role"), {
    target: { value: "hod" },
  });

  const approver = screen.getByLabelText("Step 1 approver");
  await waitFor(() => expect(approver).not.toBeDisabled());
  fireEvent.change(approver, { target: { value: "3" } });
}

describe("TeamsSection — wave 2", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
    vi.mocked(listEligibleApprovers).mockResolvedValue([
      {
        id: 3,
        full_name: "Jane Dean",
        email: "jane.dean@luanar.ac.mw",
        designation: "Dean",
      },
    ]);
    vi.stubGlobal("history", { ...window.history, length: 2 });
    // Stands in for the browser: stepping back drops the overlay param. Without
    // it the dialog never unmounts and Radix leaves the page `aria-hidden`.
    routerMock.back.mockImplementation(() => {
      searchParamsRef.current.delete("team");
    });
    routerMock.push.mockImplementation((href: string) => {
      searchParamsRef.current = new URLSearchParams(href.split("?")[1] ?? "");
    });
  });

  it("renders the table with no overlay open", () => {
    renderSection();

    expect(screen.getByText("Bunda College Faculty")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps the row name a link to the edit page, not an overlay", () => {
    // What the edit form leaves out is the point of it: the per-section roster
    // is managed on the team's own page.
    renderSection();

    expect(
      screen
        .getByRole("link", { name: /Bunda College Faculty/ })
        .getAttribute("href"),
    ).toBe("/dashboard/hr-admin/teams/4");
  });

  it("renders the retired/in-force toggle from the page's filters data", () => {
    // The toggle arrives as data rather than as a JSX slot. Markup authored in
    // the page's server component and rendered inside this client component
    // crosses the RSC boundary, where React stops recognising statically written
    // siblings and warns that each child in the list needs a key. The page
    // still owns every href and decides which tab is current.
    renderSection({
      filters: [
        {
          label: "In force and draft",
          href: "/dashboard/hr-admin/teams",
          current: false,
        },
        {
          label: "Including retired",
          href: "/dashboard/hr-admin/teams?retired=1",
          current: true,
        },
      ],
    });

    const links = within(
      screen.getByRole("group", { name: /Filter teams by status/ }),
    ).getAllByRole("link");

    expect(links.map((link) => link.textContent)).toEqual([
      "In force and draft",
      "Including retired",
    ]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/dashboard/hr-admin/teams",
      "/dashboard/hr-admin/teams?retired=1",
    ]);
    expect(links[0]).not.toHaveAttribute("aria-current");
    expect(links[1]).toHaveAttribute("aria-current", "page");
  });

  it("renders no toggle at all when the page sends no filters", () => {
    renderSection();

    expect(
      screen.queryByRole("group", { name: /Filter teams by status/ }),
    ).toBeNull();
  });

  it("keeps the retired filter when opening the create form", () => {
    searchParamsRef.current = new URLSearchParams("status=retired");
    renderSection({ teams: [] });

    fireEvent.click(screen.getByRole("button", { name: /New team/ }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/dashboard/hr-admin/teams?status=retired&team=new",
    );
  });

  it("hands cancel back to the overlay rather than leaving the page", () => {
    searchParamsRef.current = new URLSearchParams("team=new");
    renderSection();

    // Page one is where the dialog opens, so this is the cancel that has to
    // hand control back to the overlay rather than following the standalone
    // page's link away from it.
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(routerMock.back).toHaveBeenCalledTimes(1);
  });

  it("refreshes without navigating once a draft is saved", async () => {
    searchParamsRef.current = new URLSearchParams("team=new");
    vi.mocked(createTeam).mockResolvedValue(
      makeTeam({ id: 7, name: "Physics", status: "draft" }),
    );
    renderSection({
      teams: [
        makeTeam(),
        makeTeam({ id: 7, name: "Physics", status: "draft" }),
      ],
    });

    await fillCreateForm();
    fireEvent.click(screen.getByRole("button", { name: /^Create team$/ }));

    await waitFor(() => expect(createTeam).toHaveBeenCalled());
    await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  it("raises no 'not in this table' warning for a saved draft", async () => {
    // A new team is a draft and the list read excludes only retired teams, so a
    // draft shows under both filters. Unlike delegations and employees there is
    // no state the save could hide it from, so the warning would be dead code.
    searchParamsRef.current = new URLSearchParams("team=new");
    vi.mocked(createTeam).mockResolvedValue(
      makeTeam({ id: 7, name: "Physics", status: "draft" }),
    );
    renderSection({
      teams: [
        makeTeam(),
        makeTeam({ id: 7, name: "Physics", status: "draft" }),
      ],
    });

    await fillCreateForm();
    fireEvent.click(screen.getByRole("button", { name: /^Create team$/ }));

    await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    expect(screen.queryByText(/not in this table/i)).toBeNull();
  });

  it("replaces the table on a list error but keeps the create trigger", () => {
    // The dialog needs its option data, not the table, so a failed list read
    // must not also remove the one action that still works.
    renderSection({ error: "Unable to load teams. Please try again." });

    expect(
      screen.getByText("Unable to load teams. Please try again."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /New team/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Bunda College Faculty")).toBeNull();
  });

  it("still opens the dialog when the roles read failed", () => {
    // Option data that failed to load is the form's problem to report, not a
    // reason to hide the entry point. The roles belong to the chain, so the
    // error surfaces on page two rather than blocking the way to it.
    searchParamsRef.current = new URLSearchParams("team=new");
    renderSection({
      teams: [],
      rolesError: "Unable to load approver roles. Please try again.",
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.queryByText("Unable to load approver roles. Please try again."),
    ).toBeNull();

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Physics" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Continue to approval steps" }),
    );

    expect(
      screen.getAllByText("Unable to load approver roles. Please try again.")
        .length,
    ).toBeGreaterThan(0);
  });
});

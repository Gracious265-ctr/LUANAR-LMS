import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";

import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { createTeam } from "@/lib/teams-client";

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
  return { ...actual, createTeam: vi.fn(), updateTeam: vi.fn() };
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

const employees: Employee[] = [
  makeEmployee({ id: 3, full_name: "Jane Dean", approver_roles: ["hod"] }),
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
      employees={employees}
      rolesError=""
      peopleError=""
      {...props}
    />,
  );
}

/**
 * A team is only valid with a chain, so the name alone is not enough to reach a
 * submit: one step needs a name, a role and somebody who holds that role.
 */
function fillCreateForm() {
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Physics" },
  });
  fireEvent.change(screen.getByLabelText("Step 1 name"), {
    target: { value: "Review" },
  });
  fireEvent.click(screen.getByLabelText("Jane Dean"));
}

describe("TeamsSection — wave 2", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsRef.current = new URLSearchParams();
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

    fillCreateForm();
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

    fillCreateForm();
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

  it("still opens the dialog when the roles or people read failed", () => {
    // Option data that failed to load is the form's problem to report, not a
    // reason to hide the entry point.
    searchParamsRef.current = new URLSearchParams("team=new");
    renderSection({
      teams: [],
      rolesError: "Unable to load approver roles. Please try again.",
      peopleError: "Unable to load employees. Please try again.",
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getAllByText("Unable to load approver roles. Please try again.")
        .length,
    ).toBeGreaterThan(0);
  });
});

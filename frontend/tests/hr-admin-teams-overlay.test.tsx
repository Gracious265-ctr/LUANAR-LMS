import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";

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
  pathnameRef: { current: "/organisation/teams" },
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
  };
});

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

const manager: Employee = {
  id: 3,
  user_id: 3,
  email: "jane.dean@luanar.ac.mw",
  first_name: "Jane",
  last_name: "Dean",
  full_name: "Jane Dean",
  role: "employee",
  approver_roles: [],
  designation: "Dean",
  category: "administration",
  grade: "",
  appointment_date: null,
  team: null,
  team_name: "",
  is_active: true,
};

const campusList = [makeCampus()];

function renderSection(
  props: Partial<Parameters<typeof TeamsSection>[0]> = {},
) {
  return render(
    <TeamsSection
      teams={[makeTeam()]}
      campuses={campusList}
      roles={roles}
      rolesError=""
      employees={[manager]}
      wideHolderUserIds={[]}
      {...props}
    />,
  );
}

/**
 * Walks the two-step create: the details, then the manager the team is handed
 * to. Only after both does the team get written.
 */
function completeCreateForm() {
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Physics" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText("Manager role"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText("Manager"), {
    target: { value: "3" },
  });
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
    ).toBe("/organisation/teams/4");
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
          label: "In force",
          href: "/organisation/teams",
          current: false,
        },
        {
          label: "Including retired",
          href: "/organisation/teams?retired=1",
          current: true,
        },
      ],
    });

    const links = within(
      screen.getByRole("group", { name: /Filter teams by status/ }),
    ).getAllByRole("link");

    expect(links.map((link) => link.textContent)).toEqual([
      "In force",
      "Including retired",
    ]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/organisation/teams",
      "/organisation/teams?retired=1",
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
      "/organisation/teams?status=retired&team=new",
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

    completeCreateForm();
    fireEvent.click(screen.getByRole("button", { name: /^Save team$/ }));

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

    completeCreateForm();
    fireEvent.click(screen.getByRole("button", { name: /^Save team$/ }));

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
    // reason to hide the entry point. Creating a team never reads the roles,
    // so the failure cannot block the way in.
    searchParamsRef.current = new URLSearchParams("team=new");
    renderSection({
      teams: [],
      rolesError: "Unable to load approver roles. Please try again.",
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.queryByText("Unable to load approver roles. Please try again."),
    ).toBeNull();
  });

  it("hides the create trigger from a caller who cannot create teams", () => {
    // A manager reads and operates their team but does not create teams, so the
    // list is still theirs while the one action the server would refuse is not.
    renderSection({ canCreate: false });

    expect(screen.queryByRole("button", { name: /New team/ })).toBeNull();
    expect(screen.getByText("Bunda College Faculty")).toBeInTheDocument();
  });

  it("does not open the create form for a manager even with the overlay param", () => {
    // `?team=new` is a URL a manager could type; gating only the button would
    // still let them open a form whose submit the server rejects.
    searchParamsRef.current = new URLSearchParams("team=new");
    renderSection({ canCreate: false });

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

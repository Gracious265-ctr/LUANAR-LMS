import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  WideHoldingPanel,
  type WideHolding,
  type WideScope,
} from "@/components/hr/wide-holding-panel";
import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import {
  createCampusRoleAssignment,
  createRoleAssignment,
  createTeamRoleAssignment,
  removeCampusRoleAssignment,
  removeRoleAssignment,
  removeTeamRoleAssignment,
} from "@/lib/approver-roles-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("@/lib/approver-roles-client")
  >();
  return {
    ...actual,
    createRoleAssignment: vi.fn(),
    removeRoleAssignment: vi.fn(),
    createTeamRoleAssignment: vi.fn(),
    removeTeamRoleAssignment: vi.fn(),
    createCampusRoleAssignment: vi.fn(),
    removeCampusRoleAssignment: vi.fn(),
  };
});

const registrar: ApproverRole = {
  id: 9,
  code: "registrar",
  label: "Registrar",
  description: "",
  is_active: true,
  history_scope: "institution",
  handles_cancellation: false,
  is_institution_wide: true,
  is_in_use: true,
  usage: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const supervisor: ApproverRole = {
  ...registrar,
  id: 1,
  code: "supervisor",
  label: "Supervisor",
  is_institution_wide: false,
};

const dean: ApproverRole = {
  ...registrar,
  id: 2,
  code: "dean",
  label: "Dean",
  is_institution_wide: false,
};

const ALL_ROLES = [registrar, supervisor, dean];

function makeEmployee(overrides: Partial<Employee> = {}): Employee {
  return {
    id: 3,
    user_id: 3,
    email: "jane.dean@test.luanar",
    first_name: "Jane",
    last_name: "Dean",
    full_name: "Jane Dean",
    role: "employee",
    approver_roles: [],
    designation: "Dean",
    category: "academic",
    grade: "L12",
    appointment_date: null,
    team: null,
    team_name: "",
    is_active: true,
    ...overrides,
  };
}

const jane = makeEmployee();
const bob = makeEmployee({
  id: 5,
  user_id: 5,
  email: "bob.lead@test.luanar",
  first_name: "Bob",
  last_name: "Lead",
  full_name: "Bob Lead",
});
const aliceAdmin = makeEmployee({
  id: 7,
  user_id: 7,
  email: "alice.admin@test.luanar",
  first_name: "Alice",
  last_name: "Admin",
  full_name: "Alice Admin",
  category: "administration",
});

const institutionHolding: WideHolding = {
  id: 77,
  role: 9,
  user: 3,
  user_name: "Jane Dean",
  role_label: "Registrar",
};

const supervisorHolding: WideHolding = {
  id: 78,
  role: 1,
  user: 3,
  user_name: "Jane Dean",
  role_label: "Supervisor",
};

const teams = [
  { id: 4, name: "Registry" },
  { id: 6, name: "Finance Office" },
];
const campuses = [{ id: 1, name: "Main Campus" }];

function renderPanel(
  scope: WideScope,
  props: Partial<Parameters<typeof WideHoldingPanel>[0]> = {}
) {
  return render(
    <WideHoldingPanel
      scope={scope}
      roles={ALL_ROLES}
      employees={[jane, bob]}
      holdings={[]}
      {...props}
    />
  );
}

/** Options currently visible in the person picker. */
function personOptions(): (string | null)[] {
  return Array.from(
    screen.getByLabelText("Person").querySelectorAll("option")
  ).map((option) => option.textContent);
}

function choose(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), {
    target: { value },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("WideHoldingPanel", () => {
  it("says which scope it is, and offers the roles from a drop down", () => {
    renderPanel("institution");

    expect(screen.getByText("Institution-wide")).toBeInTheDocument();

    const roleOptions = Array.from(
      screen.getByLabelText("Role").querySelectorAll("option")
    ).map((option) => option.textContent);
    expect(roleOptions).toContain("Registrar");
    expect(roleOptions).toContain("Supervisor");
    expect(roleOptions).toContain("Dean");
  });

  it("shows the holder with its role, and removes through the right collection", async () => {
    vi.mocked(removeRoleAssignment).mockResolvedValue(undefined);
    renderPanel("institution", { holdings: [institutionHolding] });

    expect(
      screen.getByText(
        (_, node) => node?.textContent === "Registrar · Jane Dean"
      )
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(removeRoleAssignment).toHaveBeenCalledWith(77)
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("says when nobody holds the role, and that the next scope is the fallback", () => {
    renderPanel("team", { scopeOptions: teams });

    expect(
      screen.getByText(/No holders here\. A stage whose role is unheld falls back/i)
    ).toBeInTheDocument();
  });

  it("removes a team-wide holding through the team collection", async () => {
    vi.mocked(removeTeamRoleAssignment).mockResolvedValue(undefined);
    renderPanel("team", {
      scopeOptions: teams,
      holdings: [supervisorHolding],
    });

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(removeTeamRoleAssignment).toHaveBeenCalledWith(78)
    );
  });

  it("removes a campus-wide holding through the campus collection", async () => {
    vi.mocked(removeCampusRoleAssignment).mockResolvedValue(undefined);
    renderPanel("campus", {
      scopeOptions: campuses,
      holdings: [supervisorHolding],
    });

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(removeCampusRoleAssignment).toHaveBeenCalledWith(78)
    );
  });

  it("writes an institution-wide holding from a chosen role, without asking for a scope", async () => {
    vi.mocked(createRoleAssignment).mockResolvedValue({
      id: 80,
      role: 9,
      user: 5,
    } as never);
    renderPanel("institution");

    // No scope picker: an institution-wide role has no scope to choose.
    expect(screen.queryByLabelText("Team")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Campus")).not.toBeInTheDocument();

    choose("Role", "9");
    choose("Person", "5");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    await waitFor(() =>
      expect(createRoleAssignment).toHaveBeenCalledWith({ role: 9, user: 5 })
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("asks which team a team-wide holding applies to", async () => {
    vi.mocked(createTeamRoleAssignment).mockResolvedValue({
      id: 81,
      team: 4,
      role: 1,
      user: 5,
    } as never);
    renderPanel("team", { scopeOptions: teams });

    // A role and person are chosen but no team: the scope is the half of the
    // holding that is still missing, and the message names it.
    choose("Role", "1");
    choose("Person", "5");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));
    expect(
      await screen.findByText("Choose the team this holding applies to.")
    ).toBeInTheDocument();
    expect(createTeamRoleAssignment).not.toHaveBeenCalled();

    choose("Team", "4");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    await waitFor(() =>
      expect(createTeamRoleAssignment).toHaveBeenCalledWith({
        team: 4,
        role: 1,
        user: 5,
      })
    );
  });

  it("writes a campus-wide holding against the campus chosen", async () => {
    vi.mocked(createCampusRoleAssignment).mockResolvedValue({
      id: 82,
      campus: 1,
      role: 1,
      user: 3,
    } as never);
    renderPanel("campus", { scopeOptions: campuses });

    choose("Role", "1");
    choose("Person", "3");
    choose("Campus", "1");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    await waitFor(() =>
      expect(createCampusRoleAssignment).toHaveBeenCalledWith({
        campus: 1,
        role: 1,
        user: 3,
      })
    );
  });

  it("writes a team-wide holding for the team whose page it sits on, with no picker", async () => {
    vi.mocked(createTeamRoleAssignment).mockResolvedValue({
      id: 83,
      team: 4,
      role: 1,
      user: 5,
    } as never);
    renderPanel("team", { scopeId: 4 });

    // The team is fixed by the page: there is nothing to choose, and the id
    // must travel with the write instead of being read from a select that
    // never rendered (which used to send pk 0 to the backend).
    expect(screen.queryByLabelText("Team")).not.toBeInTheDocument();

    choose("Role", "1");
    choose("Person", "5");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    await waitFor(() =>
      expect(createTeamRoleAssignment).toHaveBeenCalledWith({
        team: 4,
        role: 1,
        user: 5,
      })
    );
  });

  it("writes a campus-wide holding for the campus whose page it sits on, with no picker", async () => {
    vi.mocked(createCampusRoleAssignment).mockResolvedValue({
      id: 84,
      campus: 1,
      role: 1,
      user: 3,
    } as never);
    renderPanel("campus", { scopeId: 1 });

    expect(screen.queryByLabelText("Campus")).not.toBeInTheDocument();

    choose("Role", "1");
    choose("Person", "3");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    await waitFor(() =>
      expect(createCampusRoleAssignment).toHaveBeenCalledWith({
        campus: 1,
        role: 1,
        user: 3,
      })
    );
  });

  it("names the missing scope rather than sending pk 0 when none is known", async () => {
    // No fixed scope and no options: the guard has to catch it, because the
    // backend's answer to pk 0 is "Invalid pk \"0\" - object does not exist".
    renderPanel("team");

    choose("Role", "1");
    choose("Person", "5");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    expect(
      await screen.findByText("Choose the team this holding applies to.")
    ).toBeInTheDocument();
    expect(createTeamRoleAssignment).not.toHaveBeenCalled();
  });

  it("refuses to save without a role chosen", async () => {
    renderPanel("institution");

    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    expect(
      await screen.findByText("Choose a role to assign.")
    ).toBeInTheDocument();
    expect(createRoleAssignment).not.toHaveBeenCalled();
  });

  it("refuses to save with a role but nobody chosen", async () => {
    renderPanel("institution");

    choose("Role", "9");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    expect(
      await screen.findByText("Choose somebody to hold this role.")
    ).toBeInTheDocument();
    expect(createRoleAssignment).not.toHaveBeenCalled();
  });

  it("offers only people who do not already hold the chosen role here", () => {
    renderPanel("institution", { holdings: [institutionHolding] });

    // Jane holds Registrar here, so she is not a candidate for it.
    choose("Role", "9");
    expect(personOptions()).not.toContain("Jane Dean");
    expect(personOptions()).toContain("Bob Lead");

    // A role with nobody holding it here offers Jane again.
    choose("Role", "1");
    expect(personOptions()).toContain("Jane Dean");
  });

  it("hides the people list when nobody is left for the chosen role", () => {
    renderPanel("institution", {
      roles: [supervisor],
      employees: [jane],
      holdings: [supervisorHolding],
    });

    choose("Role", "1");

    expect(
      screen.getByText(/Every active matching employee already holds/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Person")).not.toBeInTheDocument();
  });

  it("does not offer an inactive employee", () => {
    renderPanel("institution", {
      employees: [jane, makeEmployee({ ...bob, is_active: false })],
    });

    choose("Role", "1");

    expect(personOptions()).toContain("Jane Dean");
    expect(personOptions()).not.toContain("Bob Lead");
  });

  it("does not offer a person who already holds a wide approver role elsewhere", () => {
    renderPanel("institution", { excludedUserIds: [5] });

    // Bob already holds a wide approver role somewhere, so he is no longer a
    // candidate in this section even though nothing here is his.
    choose("Role", "1");
    expect(personOptions()).toContain("Jane Dean");
    expect(personOptions()).not.toContain("Bob Lead");
  });

  it("hides the person list when every candidate already holds a wide approver role", () => {
    renderPanel("institution", {
      roles: [supervisor],
      employees: [jane, bob],
      excludedUserIds: [3, 5],
    });

    choose("Role", "1");

    expect(
      screen.getByText(/Every active matching employee already holds/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Person")).not.toBeInTheDocument();
  });

  it("offers only the fixed scope's category on a team page", () => {
    renderPanel("team", {
      scopeId: 4,
      requiredCategory: "administration",
      employees: [bob, aliceAdmin],
    });

    // The write refuses a team-wide holder who does not match the team's
    // category, so the picker offers only the half that can be saved.
    choose("Role", "1");
    expect(personOptions()).toContain("Alice Admin");
    expect(personOptions()).not.toContain("Bob Lead");
  });

  it("offers only academic employees on a fixed campus page", () => {
    renderPanel("campus", {
      scopeId: 1,
      requiredCategory: "academic",
      employees: [bob, aliceAdmin],
    });

    choose("Role", "1");
    expect(personOptions()).toContain("Bob Lead");
    expect(personOptions()).not.toContain("Alice Admin");
  });

  it("follows the chosen team's category for the person list", () => {
    renderPanel("team", {
      scopeOptions: [
        { id: 4, name: "Registry", category: "academic" },
        { id: 6, name: "Finance Office", category: "administration" },
      ],
      employees: [bob, aliceAdmin],
    });

    // An academic team offers academic employees only...
    choose("Role", "1");
    choose("Team", "4");
    expect(personOptions()).toContain("Bob Lead");
    expect(personOptions()).not.toContain("Alice Admin");

    // ...and switching to an administration team swaps the person list.
    choose("Team", "6");
    expect(personOptions()).toContain("Alice Admin");
    expect(personOptions()).not.toContain("Bob Lead");
  });

  it("restricts a campus holding to academic employees once a campus is chosen", () => {
    renderPanel("campus", {
      scopeOptions: [{ id: 1, name: "Main Campus", category: "academic" }],
      employees: [bob, aliceAdmin],
    });

    choose("Role", "1");
    choose("Campus", "1");

    expect(personOptions()).toContain("Bob Lead");
    expect(personOptions()).not.toContain("Alice Admin");
  });

  it("says when no roles may be held at this scope", () => {
    renderPanel("team", { scopeOptions: teams, roles: [] });

    expect(
      screen.getByText(/No roles may be held at this scope right now/i)
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Role")).not.toBeInTheDocument();
  });

  it("shows a refusal from the server and stays usable", async () => {
    vi.mocked(createRoleAssignment).mockRejectedValue(
      new Error("A holder for this role already exists.")
    );
    renderPanel("institution");

    choose("Role", "9");
    choose("Person", "5");
    fireEvent.click(screen.getByRole("button", { name: "Save holder" }));

    expect(
      await screen.findByText("A holder for this role already exists.")
    ).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
    // The panel is still the place to try again from.
    expect(screen.getByRole("button", { name: "Save holder" })).toBeEnabled();
  });
});
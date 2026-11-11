import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamManagerPanel } from "@/components/hr/team-manager-panel";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import { clearTeamManager, setTeamManager } from "@/lib/teams-client";
import { makeTeam } from "@/lib/teams/__fixtures__";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh }),
}));

vi.mock("@/lib/teams-client", () => ({
  setTeamManager: vi.fn(),
  clearTeamManager: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  listMemberCandidates: vi.fn(),
  listEligibleApprovers: vi.fn(),
}));

const teamWithoutManager = makeTeam({
  id: 4,
  name: "Bunda College Faculty",
  manager_user: null,
  manager_name: "",
});
const managedTeam = makeTeam({
  id: 4,
  name: "Bunda College Faculty",
  manager_user: 21,
  manager_name: "Mary Registrar",
});

const mary = makeEmployee({
  user_id: 21,
  full_name: "Mary Registrar",
  category: "academic",
});
const obi = makeEmployee({
  user_id: 22,
  full_name: "Obi Provost",
  // The other half of the institution: a manager need not share the team's
  // category, because they hold no team-scoped role.
  category: "administration",
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamManagerPanel", () => {
  it("says when nobody runs the team yet", () => {
    render(
      <TeamManagerPanel
        team={teamWithoutManager}
        employees={[mary, obi]}
        canManage
      />
    );

    expect(
      screen.getByText(/Nobody runs this team yet/)
    ).toBeInTheDocument();
  });

  it("names the current manager", () => {
    render(
      <TeamManagerPanel team={managedTeam} employees={[mary, obi]} canManage />
    );

    expect(screen.getByText("Mary Registrar")).toBeInTheDocument();
    expect(screen.getByText("Manager")).toBeInTheDocument();
  });

  it("lets HR name anybody as the manager, either half of the institution", async () => {
    vi.mocked(setTeamManager).mockResolvedValue({
      ...managedTeam,
      manager_user: 22,
      manager_name: "Obi Provost",
    });
    render(
      <TeamManagerPanel
        team={teamWithoutManager}
        employees={[mary, obi]}
        canManage
      />
    );

    fireEvent.change(screen.getByLabelText("Designate a manager"), {
      target: { value: "22" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Make manager" }));

    await waitFor(() => expect(setTeamManager).toHaveBeenCalledWith(4, 22));
    expect(
      await screen.findByText("Obi Provost now runs Bunda College Faculty.")
    ).toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
  });

  it("removes the manager without touching the team", async () => {
    vi.mocked(clearTeamManager).mockResolvedValue(teamWithoutManager);
    render(
      <TeamManagerPanel team={managedTeam} employees={[mary, obi]} canManage />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove manager" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, continue" }));

    await waitFor(() => expect(clearTeamManager).toHaveBeenCalledWith(4));
    expect(
      await screen.findByText(/no longer has a manager/)
    ).toBeInTheDocument();
  });

  it("shows the backend's reason when the write is refused", async () => {
    vi.mocked(setTeamManager).mockRejectedValue(
      new Error("Obi Provost is not an active user.")
    );
    render(
      <TeamManagerPanel
        team={teamWithoutManager}
        employees={[mary, obi]}
        canManage
      />
    );

    fireEvent.change(screen.getByLabelText("Designate a manager"), {
      target: { value: "22" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Make manager" }));

    expect(
      await screen.findByText("Obi Provost is not an active user.")
    ).toBeInTheDocument();
  });

  it("offers a non-HR viewer a read-only statement", () => {
    render(
      <TeamManagerPanel
        team={managedTeam}
        employees={[mary, obi]}
        canManage={false}
      />
    );

    expect(
      screen.queryByRole("button", { name: "Make manager" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Designate a manager")
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Only HR can change who manages a team.")
    ).toBeInTheDocument();
  });
});

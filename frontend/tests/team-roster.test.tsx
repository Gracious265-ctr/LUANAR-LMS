import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamRoster } from "@/components/hr/team-roster";
import { assignEmployeeTeam } from "@/lib/employees-client";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import { makeTeam } from "@/lib/teams/__fixtures__";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/employees-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/employees-client")>();
  return { ...actual, assignEmployeeTeam: vi.fn() };
});

const team = makeTeam({ id: 4, name: "Bunda College Faculty" });
const onTeam = makeEmployee({
  id: 11,
  full_name: "Ruth Member",
  email: "ruth@test.luanar",
  designation: "Lecturer",
  team: 4,
  team_name: "Bunda College Faculty",
});
const unassigned = makeEmployee({
  id: 12,
  full_name: "Sam Candidate",
  email: "sam@test.luanar",
  designation: "Assistant",
  team: null,
  team_name: "",
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamRoster", () => {
  it("lists the current members with a way to take each off the team", () => {
    render(<TeamRoster team={team} members={[onTeam]} candidates={[]} />);

    expect(screen.getByText("Ruth Member")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove Ruth Member from Bunda College Faculty" })
    ).toBeInTheDocument();
  });

  it("adds an unassigned employee to the team", async () => {
    vi.mocked(assignEmployeeTeam).mockResolvedValue(undefined);
    render(<TeamRoster team={team} members={[]} candidates={[unassigned]} />);

    fireEvent.change(screen.getByLabelText("Employee to add to this team"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add to team" }));

    await waitFor(() =>
      expect(assignEmployeeTeam).toHaveBeenCalledWith(12, 4)
    );
    expect(refresh).toHaveBeenCalled();
  });

  it("removes a member by clearing their team", async () => {
    vi.mocked(assignEmployeeTeam).mockResolvedValue(undefined);
    render(<TeamRoster team={team} members={[onTeam]} candidates={[]} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Remove Ruth Member from Bunda College Faculty",
      })
    );

    await waitFor(() =>
      expect(assignEmployeeTeam).toHaveBeenCalledWith(11, null)
    );
  });

  it("says so plainly when nobody has been placed yet and offers no one", () => {
    render(<TeamRoster team={team} members={[]} candidates={[]} />);

    expect(
      screen.getByText(/Nobody's leave routes through this team yet/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "No employees without a team" })
    ).toBeInTheDocument();
  });

  it("shows the backend's reason when a roster change is refused", async () => {
    vi.mocked(assignEmployeeTeam).mockRejectedValue(
      new Error("That employee is already on another team.")
    );
    render(<TeamRoster team={team} members={[]} candidates={[unassigned]} />);

    fireEvent.change(screen.getByLabelText("Employee to add to this team"), {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add to team" }));

    expect(
      await screen.findByText("That employee is already on another team.")
    ).toBeInTheDocument();
  });
});

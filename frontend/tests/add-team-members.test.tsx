import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AddTeamMembers } from "@/components/hr/add-team-members";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import { addTeamMembers } from "@/lib/team-members-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/team-members-client", () => ({
  addTeamMembers: vi.fn(),
  listTeamMembers: vi.fn(),
  removeTeamMember: vi.fn(),
}));

const team = { id: 4, name: "Bunda College Faculty", category: "academic" };

const sam = makeEmployee({
  id: 30,
  user_id: 99,
  full_name: "Sam Candidate",
  email: "sam@test.luanar",
  designation: "Assistant",
  category: "academic",
  team: null,
  team_name: "",
});
const pat = makeEmployee({
  id: 31,
  user_id: 100,
  full_name: "Pat Registrar",
  email: "pat@test.luanar",
  designation: "Registrar",
  // An institution-wide holder from the other half of the institution: the
  // backend offers them because a wide holding crosses the halves.
  category: "administration",
  team: null,
  team_name: "",
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(addTeamMembers).mockResolvedValue([]);
});

describe("AddTeamMembers", () => {
  it("lists the candidates and adds the chosen people in one write", async () => {
    render(<AddTeamMembers team={team} candidates={[sam, pat]} />);

    expect(screen.getByText("Sam Candidate")).toBeInTheDocument();
    expect(screen.getByText("Pat Registrar")).toBeInTheDocument();
    // The category crossing is named, so the manager can see why somebody from
    // the other half is on an academic team's list.
    expect(screen.getByText("Wide approver")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Sam Candidate" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Pat Registrar" }));
    expect(screen.getByText("2 people ready to add.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add 2 to team" }));

    await waitFor(() =>
      expect(addTeamMembers).toHaveBeenCalledWith(4, [99, 100])
    );
    expect(push).toHaveBeenCalledWith("/dashboard/teams/4?tab=members");
    expect(refresh).toHaveBeenCalled();
  });

  it("selects everyone shown, and clears that selection again", () => {
    render(<AddTeamMembers team={team} candidates={[sam, pat]} />);

    fireEvent.click(screen.getByRole("button", { name: "Select all shown" }));
    expect(screen.getByText("2 people ready to add.")).toBeInTheDocument();
    // Every chosen person is listed in the summary, with a way to drop them.
    expect(
      screen.getByRole("button", {
        name: "Remove Sam Candidate from the selection",
      })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear shown" }));
    expect(screen.getByText("Nobody chosen yet.")).toBeInTheDocument();
  });

  it("searches by name and keeps the choice while the list is narrowed", () => {
    render(<AddTeamMembers team={team} candidates={[sam, pat]} />);

    fireEvent.click(screen.getByRole("checkbox", { name: "Sam Candidate" }));
    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "pat" },
    });
    expect(
      screen.queryByRole("checkbox", { name: "Sam Candidate" })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Pat Registrar" })
    ).toBeInTheDocument();
    // The selection survives a search: it is the decision, not the filter.
    expect(screen.getByText("1 person ready to add.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search people"), {
      target: { value: "nobody" },
    });
    expect(screen.getByText("Nobody matches this search")).toBeInTheDocument();
  });

  it("shows the backend's reason and stays on the page when the add is refused", async () => {
    vi.mocked(addTeamMembers).mockRejectedValue(
      new Error("Sam Candidate is already on Registry Operations.")
    );
    render(<AddTeamMembers team={team} candidates={[sam]} />);

    fireEvent.click(screen.getByRole("checkbox", { name: "Sam Candidate" }));
    fireEvent.click(screen.getByRole("button", { name: "Add to team" }));

    expect(
      await screen.findByText(/already on Registry Operations/)
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("says so when nobody is available to add", () => {
    render(<AddTeamMembers team={team} candidates={[]} />);

    expect(screen.getByText("Nobody is available to add")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add to team" })).toBeDisabled();
  });
});

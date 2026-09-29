import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TeamTable } from "@/components/hr/team-table";
import { makeTeam } from "@/lib/teams/__fixtures__";

describe("TeamTable", () => {
  it("shows one row per team with the status, so two can be compared at a glance", () => {
    render(
      <TeamTable
        teams={[
          makeTeam({ id: 1, name: "Registry", status: "active", is_effective: true }),
          makeTeam({ id: 2, name: "Bunda Faculty", status: "draft" }),
          makeTeam({ id: 3, name: "Old Team", status: "inactive" }),
        ]}
      />
    );

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Registry")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Active")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Draft")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Retired")).toBeInTheDocument();
  });

  it("shows the effective window next to the status, because active is not the same as routing", () => {
    render(
      <TeamTable
        teams={[
          makeTeam({
            status: "active",
            is_effective: false,
            effective_from: "2026-07-01",
            effective_to: "2026-12-31",
          }),
        ]}
      />
    );

    expect(screen.getByText("01 Jul 2026 to 31 Dec 2026")).toBeInTheDocument();
  });

  it("says a step is unstaffed instead of leaving it to be counted", () => {
    render(
      <TeamTable
        teams={[
          makeTeam({
            sections: [
              {
                id: 1,
                name: "Supervisor",
                order: 1,
                is_active: true,
                approver_role: "supervisor",
                approver_role_label: "Supervisor",
                member_count: 1,
                members: [],
              },
              {
                id: 2,
                name: "Head",
                order: 2,
                is_active: true,
                approver_role: "hod",
                approver_role_label: "Head of Department",
                member_count: 0,
                members: [],
              },
            ],
          }),
        ]}
      />
    );

    expect(screen.getByText("1 of 2 staffed")).toBeInTheDocument();
  });

  it("links each team to its own page rather than straight into an edit form", () => {
    render(<TeamTable teams={[makeTeam({ id: 7, name: "Registry" })]} />);

    expect(
      screen.getByRole("link", { name: "Registry" })
    ).toHaveAttribute("href", "/dashboard/hr-admin/teams/7");
  });

  it("invites a first team instead of rendering an empty table", () => {
    render(<TeamTable teams={[]} />);

    expect(screen.getByText("No teams found")).toBeInTheDocument();
    expect(
      screen.getByText(/Create a team to route its employees/)
    ).toBeInTheDocument();
  });
});

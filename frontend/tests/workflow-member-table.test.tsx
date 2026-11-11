import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkflowMemberTable } from "@/components/hr/workflow-member-table";
import type { WorkflowMember } from "@/lib/team-members";

function makeMember(overrides: Partial<WorkflowMember> = {}): WorkflowMember {
  return {
    id: 1,
    workflow: 12,
    workflow_name: "Academic approval",
    user: 41,
    user_name: "Grace Banda",
    user_email: "grace@luanar.test",
    designation: "Lecturer",
    team: 4,
    team_name: "Bunda College Faculty",
    added_by: 7,
    created_at: "2026-11-02T09:00:00Z",
    ...overrides,
  };
}

describe("WorkflowMemberTable", () => {
  it("renders one row per member in a table with the roster columns", () => {
    render(
      <WorkflowMemberTable
        members={[
          makeMember(),
          makeMember({
            id: 2,
            user: 42,
            user_name: "John Phiri",
            user_email: "john@luanar.test",
            designation: "Dean",
          }),
        ]}
      />
    );

    const table = screen.getByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((heading) => heading.textContent);
    expect(headers).toEqual(["Name", "Designation", "Email"]);

    const rows = within(table).getAllByRole("row");
    // One header row plus one row per member.
    expect(rows).toHaveLength(3);

    expect(within(rows[1]).getByText("Grace Banda")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Lecturer")).toBeInTheDocument();
    expect(
      within(rows[1]).getByRole("link", { name: "grace@luanar.test" })
    ).toHaveAttribute("href", "mailto:grace@luanar.test");

    expect(within(rows[2]).getByText("John Phiri")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Dean")).toBeInTheDocument();
  });

  it("prints the fields the workflow detail payload supplies", () => {
    // ``full_name``/``email`` were the old hand-rolled keys that left every
    // row blank; the table reads the member serializer's contract instead.
    render(<WorkflowMemberTable members={[makeMember()]} />);

    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.getByText("Grace Banda")).toBeInTheDocument();
    expect(screen.getByText("grace@luanar.test")).toBeInTheDocument();
  });

  it("uses an em dash when a member has no designation or email", () => {
    render(
      <WorkflowMemberTable
        members={[makeMember({ designation: "", user_email: "" })]}
      />
    );

    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("explains how to add members when the chain has none", () => {
    render(<WorkflowMemberTable members={[]} />);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(
      screen.getByText(/A team manager can add them from Edit steps/)
    ).toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamLifecycleActions } from "@/components/hr/team-lifecycle-actions";
import { makeTeam } from "@/lib/teams/__fixtures__";
import type { TeamReadiness } from "@/lib/teams";
import { deactivateTeam, validateTeam } from "@/lib/teams-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return {
    ...actual,
    deactivateTeam: vi.fn(),
    validateTeam: vi.fn(),
  };
});

const notReady: TeamReadiness = {
  team: "Bunda College Faculty",
  status: "active",
  ready: false,
  issues: [
    {
      code: "no_approver",
      field: "sections",
      message:
        'Nobody can act on the "Team leader" step (Team Leader). Add at least one active member, or a holder of the role.',
      section: 2,
      approver_role: "lead",
    },
    {
      code: "no_sections",
      field: "workflow",
      message: "This team has no approval chain, so nothing can be approved.",
      section: null,
      approver_role: null,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamLifecycleActions", () => {
  it("lists every reason a team cannot route, in one pass", async () => {
    vi.mocked(validateTeam).mockResolvedValue(notReady);
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(
      await screen.findByText(/Bunda College Faculty cannot route applications yet/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Nobody can act on the "Team leader" step/)).toBeInTheDocument();
    expect(
      screen.getByText("This team has no approval chain, so nothing can be approved.")
    ).toBeInTheDocument();
    expect(screen.getByText(/Fix 2 problems/)).toBeInTheDocument();
  });

  it("says so plainly when a team can route", async () => {
    vi.mocked(validateTeam).mockResolvedValue({
      team: "Bunda College Faculty",
      status: "active",
      ready: true,
      issues: [],
    });
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(
      await screen.findByText(/Bunda College Faculty is ready to route applications/)
    ).toBeInTheDocument();
  });

  it("offers no way to put a team into force", () => {
    // Creating the team already did that, so a second button would be a second
    // decision about something that is not a decision any more.
    render(<TeamLifecycleActions team={makeTeam({ status: "active" })} />);

    expect(
      screen.queryByRole("button", { name: /into force/i })
    ).not.toBeInTheDocument();
  });

  it("offers retirement for a team in force", async () => {
    vi.mocked(deactivateTeam).mockResolvedValue(makeTeam({ status: "inactive" }));
    render(
      <TeamLifecycleActions
        team={makeTeam({ status: "active", is_effective: true })}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Retire team" }));

    await waitFor(() => expect(deactivateTeam).toHaveBeenCalledWith(4));
    expect(refresh).toHaveBeenCalled();
  });

  it("does not offer to retire a team that is already retired", () => {
    render(<TeamLifecycleActions team={makeTeam({ status: "inactive" })} />);

    expect(
      screen.queryByRole("button", { name: "Retire team" })
    ).not.toBeInTheDocument();
  });

  it("reports a plain failure without pretending it knows the reasons", async () => {
    vi.mocked(validateTeam).mockRejectedValue(new Error("Network unreachable."));
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Network unreachable."
    );
  });
});
